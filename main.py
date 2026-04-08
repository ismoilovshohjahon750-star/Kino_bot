import logging
import sqlite3
from aiogram import Bot, Dispatcher, types, executor
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# --- KONFIGURATSIYA ---
API_TOKEN = '8026117592:AAE5-IOHe3o8bOdo0Vby8jVvIH2y9NOZN6E' # BotFather bergan tokenni yozing
ADMIN_ID = 8453381252   # O'zingizning ID raqamingiz

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# --- BAZA ---
conn = sqlite3.connect("kino_baza.db", check_same_thread=False)
cur = conn.cursor()
cur.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, status TEXT)")
cur.execute("CREATE TABLE IF NOT EXISTS movies (code TEXT PRIMARY KEY, file_id TEXT)")
cur.execute("CREATE TABLE IF NOT EXISTS channels (url TEXT PRIMARY KEY)")
conn.commit()

# --- HOLATLAR ---
class AdminStates(StatesGroup):
    wait_kino_code = State()
    wait_kino_file = State()
    wait_channel_url = State()

# --- TUGMALAR ---
def admin_main_kb():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("🎬 Kino qo'shish", callback_data="add_kino"),
        InlineKeyboardButton("🗑 Kino o'chirish", callback_data="del_kino_menu"),
        InlineKeyboardButton("📢 Kanal qo'shish", callback_data="add_chan"),
        InlineKeyboardButton("❌ Kanal o'chirish", callback_data="list_channels"),
        InlineKeyboardButton("👥 Foydalanuvchilar", callback_data="list_users")
    )
    return kb

# --- START VA KINO QIDIRISH ---
@dp.message_handler(commands=['start'])
async def start_cmd(message: types.Message):
    u_id = message.from_user.id
    uname = f"@{message.from_user.username}" if message.from_user.username else "Noma'lum"
    cur.execute("INSERT OR IGNORE INTO users VALUES (?, ?, ?)", (u_id, uname, 'active'))
    conn.commit()
    await message.answer("Xush kelibsiz! Kino kodini yuboring.")

@dp.message_handler(lambda m: m.text.isdigit())
async def get_movie(message: types.Message):
    # Block tekshiruvi
    cur.execute("SELECT status FROM users WHERE user_id=?", (message.from_user.id,))
    user = cur.fetchone()
    if user and user[0] == 'blocked':
        return await message.answer("Siz bloklangansiz!")

    # Kino qidirish
    cur.execute("SELECT file_id FROM movies WHERE code=?", (message.text,))
    movie = cur.fetchone()
    if movie:
        await bot.send_video(message.chat.id, movie[0], caption=f"Kino kodi: {message.text}")
    else:
        await message.answer("Bunday kodli kino topilmadi.")

# --- ADMIN PANEL ---
@dp.message_handler(commands=['admin'], user_id=ADMIN_ID)
async def admin_start(message: types.Message):
    await message.answer("🛠 Admin boshqaruv paneli:", reply_markup=admin_main_kb())

# --- KINO QO'SHISH BOSQICHMA-BOSQICH ---
@dp.callback_query_handler(text="add_kino", user_id=ADMIN_ID)
async def start_add_kino(call: types.CallbackQuery):
    await AdminStates.wait_kino_code.set()
    await call.message.edit_text("🔢 Kino uchun kod yuboring (masalan: 123):")

@dp.message_handler(state=AdminStates.wait_kino_code, user_id=ADMIN_ID)
async def process_kino_code(message: types.Message, state: FSMContext):
    await state.update_data(kino_code=message.text)
    await AdminStates.wait_kino_file.set()
    await message.answer("📹 Endi kinoni (videoni) yuboring:")

@dp.message_handler(content_types=['video'], state=AdminStates.wait_kino_file, user_id=ADMIN_ID)
async def process_kino_file(message: types.Message, state: FSMContext):
    data = await state.get_data()
    code = data['kino_code']
    cur.execute("INSERT OR REPLACE INTO movies VALUES (?, ?)", (code, message.video.file_id))
    conn.commit()
    await state.finish()
    await message.answer(f"✅ Kino saqlandi! Kodi: {code}", reply_markup=admin_main_kb())

# --- KANAL QO'SHISH ---
@dp.callback_query_handler(text="add_chan", user_id=ADMIN_ID)
async def start_add_chan(call: types.CallbackQuery):
    await AdminStates.wait_channel_url.set()
    await call.message.edit_text("🔗 Kanal linkini yuboring:\n\nTG bo'lsa: @kanal_user\nBoshqa bo'lsa: https://link...")

@dp.message_handler(state=AdminStates.wait_channel_url, user_id=ADMIN_ID)
async def process_chan_url(message: types.Message, state: FSMContext):
    cur.execute("INSERT OR IGNORE INTO channels VALUES (?)", (message.text,))
    conn.commit()
    await state.finish()
    await message.answer("✅ Kanal qo'shildi!", reply_markup=admin_main_kb())

# --- FOYDALANUVCHILARNI BOSHQARISH (Siz aytgan tizim) ---
@dp.callback_query_handler(text="list_users", user_id=ADMIN_ID)
async def list_users(call: types.CallbackQuery):
    cur.execute("SELECT user_id, username, status FROM users")
    users = cur.fetchall()
    kb = InlineKeyboardMarkup(row_width=1)
    for u_id, uname, status in users:
        icon = "🔴" if status == "blocked" else "🟢"
        kb.add(InlineKeyboardButton(f"{icon} {uname}", callback_data=f"manage_u:{u_id}"))
    kb.add(InlineKeyboardButton("⬅️ Orqaga", callback_data="back_admin"))
    await call.message.edit_text("Foydalanuvchini tanlang:", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith("manage_u:"), user_id=ADMIN_ID)
async def manage_user(call: types.CallbackQuery):
    u_id = call.data.split(":")[1]
    cur.execute("SELECT username, status FROM users WHERE user_id=?", (u_id,))
    user = cur.fetchone()
    kb = InlineKeyboardMarkup(row_width=2)
    if user[1] == "active":
        kb.add(InlineKeyboardButton("🚫 Bloklash", callback_data=f"ask_block:{u_id}"))
    else:
        kb.add(InlineKeyboardButton("✅ Blokdan ochish", callback_data=f"unblock:{u_id}"))
    kb.add(InlineKeyboardButton("⬅️ Orqaga", callback_data="list_users"))
    await call.message.edit_text(f"👤 {user[0]}\nHolati: {user[1]}", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith("ask_block:"), user_id=ADMIN_ID)
async def ask_block(call: types.CallbackQuery):
    u_id = call.data.split(":")[1]
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("✅ HA", callback_data=f"confirm_b:{u_id}"),
        InlineKeyboardButton("❌ YO'Q", callback_data=f"manage_u:{u_id}")
    )
    await call.message.edit_text("⚠️ Rostdan ham bloklaysizmi?", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith("confirm_b:"), user_id=ADMIN_ID)
async def confirm_b(call: types.CallbackQuery):
    u_id = call.data.split(":")[1]
    cur.execute("UPDATE users SET status='blocked' WHERE user_id=?", (u_id,))
    conn.commit()
    await call.answer("Bloklandi!")
    await list_users(call)

@dp.callback_query_handler(text="back_admin", user_id=ADMIN_ID)
async def back_admin(call: types.CallbackQuery):
    await call.message.edit_text("🛠 Admin boshqaruv paneli:", reply_markup=admin_main_kb())

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
                    
