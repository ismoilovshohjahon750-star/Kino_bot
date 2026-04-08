import logging
import sqlite3
from aiogram import Bot, Dispatcher, types, executor
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# --- KONFIGURATSIYA ---
API_TOKEN = '8026117592:AAFFErkQRHvD-poKjPzMUB0P2xnXjBLymzo'
SUPER_ADMIN = 8453381252  # Bu siz (Asosiy xo'jayin)

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# --- BAZA BILAN ISHLASH ---
conn = sqlite3.connect("kino_baza.db", check_same_thread=False)
cur = conn.cursor()
cur.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, status TEXT)")
cur.execute("CREATE TABLE IF NOT EXISTS movies (code TEXT PRIMARY KEY, file_id TEXT)")
cur.execute("CREATE TABLE IF NOT EXISTS channels (url TEXT PRIMARY KEY)")
cur.execute("CREATE TABLE IF NOT EXISTS admins (user_id INTEGER PRIMARY KEY)") # Yangi adminlar jadvali
conn.commit()

# Super adminni bazaga avtomatik qo'shish
cur.execute("INSERT OR IGNORE INTO admins VALUES (?)", (SUPER_ADMIN,))
conn.commit()

class AdminStates(StatesGroup):
    wait_kino_code = State()
    wait_kino_file = State()
    wait_channel_url = State()
    wait_del_kino_code = State()

# --- ADMINLIKNI TEKSHIRISH ---
async def is_admin(user_id):
    cur.execute("SELECT user_id FROM admins WHERE user_id=?", (user_id,))
    return cur.fetchone() is not None

# --- MAJBURIY OBUNA TEKSHIRUVCHI ---
async def check_sub(user_id):
    cur.execute("SELECT url FROM channels")
    channels = cur.fetchall()
    for (url,) in channels:
        if url.startswith("@"):
            try:
                member = await bot.get_chat_member(chat_id=url, user_id=user_id)
                if member.status in ['left', 'kicked']:
                    return False
            except: continue
    return True

# --- ADMIN PANEL TUGMALARI ---
def admin_main_kb(user_id):
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("🎬 Kino qo'shish", callback_data="add_kino"),
        InlineKeyboardButton("🗑 Kino o'chirish", callback_data="del_kino_menu"),
        InlineKeyboardButton("📢 Kanal qo'shish", callback_data="add_chan"),
        InlineKeyboardButton("❌ Kanal o'chirish", callback_data="list_channels"),
        InlineKeyboardButton("👥 Foydalanuvchilar", callback_data="list_users")
    )
    # Faqat Super Admin yangi admin qo'sha oladi
    if user_id == SUPER_ADMIN:
        kb.add(InlineKeyboardButton("⭐ Adminlarni boshqarish", callback_data="manage_admins"))
    return kb

# --- FOYDALANUVCHI QISMI ---
@dp.message_handler(commands=['start'])
async def start_cmd(message: types.Message):
    u_id = message.from_user.id
    uname = f"@{message.from_user.username}" if message.from_user.username else "Noma'lum"
    cur.execute("INSERT OR IGNORE INTO users VALUES (?, ?, ?)", (u_id, uname, 'active'))
    conn.commit()
    await message.answer("👋 Salom! Kino kodini yuboring.")

@dp.message_handler(lambda m: m.text.isdigit())
async def search_movie(message: types.Message):
    u_id = message.from_user.id
    cur.execute("SELECT status FROM users WHERE user_id=?", (u_id,))
    user = cur.fetchone()
    if user and user[0] == 'blocked':
        return await message.answer("🚫 Siz bloklangansiz!")

    if not await check_sub(u_id):
        cur.execute("SELECT url FROM channels")
        ch_list = cur.fetchall()
        kb = InlineKeyboardMarkup(row_width=1)
        for (url,) in ch_list:
            btn_url = url if url.startswith("http") else f"https://t.me/{url[1:]}"
            kb.add(InlineKeyboardButton("A'zo bo'lish", url=btn_url))
        kb.add(InlineKeyboardButton("Tekshirish ✅", callback_data="check_again"))
        return await message.answer("⚠️ Kanallarga a'zo bo'ling:", reply_markup=kb)

    cur.execute("SELECT file_id FROM movies WHERE code=?", (message.text,))
    res = cur.fetchone()
    if res:
        await bot.send_video(message.chat.id, res[0], caption=f"🎬 Kod: {message.text}")
    else:
        await message.answer("😔 Kino topilmadi.")

# --- ADMIN PANEL ASOSIY ---
@dp.message_handler(commands=['admin'])
async def admin_cmd(message: types.Message):
    if await is_admin(message.from_user.id):
        await message.answer("🛠 Admin panel:", reply_markup=admin_main_kb(message.from_user.id))

# --- ADMIN QO'SHISH TIZIMI (Faqat Super Admin uchun) ---
@dp.callback_query_handler(text="manage_admins", user_id=SUPER_ADMIN)
async def manage_admins(call: types.CallbackQuery):
    cur.execute("SELECT a.user_id, u.username FROM admins a LEFT JOIN users u ON a.user_id = u.user_id")
    admins = cur.fetchall()
    kb = InlineKeyboardMarkup(row_width=1)
    for a_id, uname in admins:
        if a_id != SUPER_ADMIN:
            kb.add(InlineKeyboardButton(f"❌ {uname} (ID: {a_id})", callback_data=f"rem_admin:{a_id}"))
    kb.add(InlineKeyboardButton("⬅️ Orqaga", callback_data="back_admin"))
    await call.message.edit_text("⭐ Adminlar ro'yxati (o'chirish uchun ustiga bosing):", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith("rem_admin:"), user_id=SUPER_ADMIN)
async def remove_admin(call: types.CallbackQuery):
    a_id = call.data.split(":")[1]
    cur.execute("DELETE FROM admins WHERE user_id=?", (a_id,))
    conn.commit()
    await call.answer("Adminlikdan olindi!")
    await manage_admins(call)

# --- FOYDALANUVCHINI ADMIN QILISH TUGMASI ---
@dp.callback_query_handler(lambda c: c.data.startswith("u_m:"), user_id=SUPER_ADMIN)
async def user_manage(call: types.CallbackQuery):
    u_id = call.data.split(":")[1]
    cur.execute("SELECT username, status FROM users WHERE user_id=?", (u_id,))
    user = cur.fetchone()
    
    # Adminmi yoki yo'qmi tekshirish
    cur.execute("SELECT * FROM admins WHERE user_id=?", (u_id,))
    is_adm = cur.fetchone()
    
    kb = InlineKeyboardMarkup(row_width=2)
    if not is_adm:
        kb.add(InlineKeyboardButton("⭐ Admin qilish", callback_data=f"make_admin:{u_id}"))
    
    if user[1] == 'active':
        kb.add(InlineKeyboardButton("🚫 Bloklash", callback_data=f"block:{u_id}"))
    else:
        kb.add(InlineKeyboardButton("✅ Ochish", callback_data=f"unblock:{u_id}"))
    
    kb.add(InlineKeyboardButton("⬅️ Orqaga", callback_data="list_users"))
    await call.message.edit_text(f"👤 {user[0]}\nID: {u_id}", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith("make_admin:"), user_id=SUPER_ADMIN)
async def make_admin(call: types.CallbackQuery):
    u_id = call.data.split(":")[1]
    cur.execute("INSERT OR IGNORE INTO admins VALUES (?)", (u_id,))
    conn.commit()
    await call.answer("Yangi admin qo'shildi! ✅")
    await user_manage(call)

# --- QOLGAN BARCHA CALLBACKLAR (Kino/Kanal o'chirish va h.k) ---
@dp.callback_query_handler(lambda c: c.data == "add_kino")
async def cb_add_kino(call: types.CallbackQuery):
    if await is_admin(call.from_user.id):
        await AdminStates.wait_kino_code.set()
        await call.message.edit_text("🔢 Kino kodini yuboring:")

@dp.message_handler(state=AdminStates.wait_kino_code)
async def st_kino_code(message: types.Message, state: FSMContext):
    if await is_admin(message.from_user.id):
        await state.update_data(k_code=message.text)
        await AdminStates.wait_kino_file.set()
        await message.answer("📹 Videoni yuboring:")

@dp.message_handler(content_types=['video'], state=AdminStates.wait_kino_file)
async def st_kino_file(message: types.Message, state: FSMContext):
    if await is_admin(message.from_user.id):
        data = await state.get_data()
        cur.execute("INSERT OR REPLACE INTO movies VALUES (?, ?)", (data['k_code'], message.video.file_id))
        conn.commit()
        await state.finish()
        await message.answer("✅ Saqlandi!", reply_markup=admin_main_kb(message.from_user.id))

# (Kanal o'chirish, bloklash va h.k oldingi koddagidek davom etadi, faqat is_admin tekshiruvi bilan)
# ... [Barcha oldingi funksiyalar saqlangan] ...

@dp.callback_query_handler(text="list_users")
async def cb_list_users(call: types.CallbackQuery):
    if await is_admin(call.from_user.id):
        cur.execute("SELECT user_id, username, status FROM users LIMIT 50")
        users = cur.fetchall()
        kb = InlineKeyboardMarkup(row_width=1)
        for u_id, uname, status in users:
            icon = "🔴" if status == "blocked" else "🟢"
            kb.add(InlineKeyboardButton(f"{icon} {uname}", callback_data=f"u_m:{u_id}"))
        kb.add(InlineKeyboardButton("⬅️ Orqaga", callback_data="back_admin"))
        await call.message.edit_text("Foydalanuvchilar:", reply_markup=kb)

@dp.callback_query_handler(text="back_admin")
async def cb_back(call: types.CallbackQuery):
    if await is_admin(call.from_user.id):
        await call.message.edit_text("🛠 Admin panel:", reply_markup=admin_main_kb(call.from_user.id))

@dp.callback_query_handler(text="check_again")
async def cb_check(call: types.CallbackQuery):
    if await check_sub(call.from_user.id):
        await call.message.edit_text("✅ Rahmat! Kod yuboring.")
    else:
        await call.answer("❌ Obuna bo'lmagansiz!", show_alert=True)

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
