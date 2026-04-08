import logging
import sqlite3
from aiogram import Bot, Dispatcher, types, executor
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# --- KONFIGURATSIYA ---
API_TOKEN = 'BOT_TOKENINGIZNI_SHU_YERGA_YOZING'
ADMIN_ID = 12345678  # O'zingizning Telegram ID'ingizni yozing

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# --- MA'LUMOTLAR BAZASI ---
conn = sqlite3.connect("kino_baza.db", check_same_thread=False)
cur = conn.cursor()
cur.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, status TEXT)")
cur.execute("CREATE TABLE IF NOT EXISTS movies (code TEXT PRIMARY KEY, file_id TEXT)")
cur.execute("CREATE TABLE IF NOT EXISTS channels (url TEXT PRIMARY KEY)")
conn.commit()

# --- HOLATLAR (STATES) ---
class AdminStates(StatesGroup):
    wait_kino_code = State()
    wait_kino_file = State()
    wait_channel_url = State()

# --- FUNKSIYALAR ---
async def check_sub(user_id):
    cur.execute("SELECT url FROM channels")
    channels = cur.fetchall()
    for (url,) in channels:
        if url.startswith("@"):
            try:
                member = await bot.get_chat_member(chat_id=url, user_id=user_id)
                if member.status in ['left', 'kicked', 'null']:
                    return False
            except:
                continue
    return True

# --- ADMIN PANEL TUGMALARI ---
def admin_kb():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("Kino qo'shish", callback_data="add_kino"),
        InlineKeyboardButton("Kino o'chirish", callback_data="del_kino"),
        InlineKeyboardButton("Kanal qo'shish", callback_data="add_chan"),
        InlineKeyboardButton("Kanal o'chirish", callback_data="del_chan"),
        InlineKeyboardButton("Foydalanuvchilar", callback_data="user_list")
    )
    return kb

# --- START BOSGANDA ---
@dp.message_handler(commands=['start'])
async def start_cmd(message: types.Message):
    u_id = message.from_user.id
    uname = f"@{message.from_user.username}" if message.from_user.username else "Noma'lum"
    
    cur.execute("INSERT OR IGNORE INTO users (user_id, username, status) VALUES (?, ?, ?)", (u_id, uname, 'active'))
    conn.commit()
    
    await message.answer(f"Xush kelibsiz! Kino kodini yuboring.")

# --- ADMIN KOMANDASI ---
@dp.message_handler(commands=['admin'], user_id=ADMIN_ID)
async def admin_main(message: types.Message):
    await message.answer("Admin boshqaruv paneli:", reply_markup=admin_kb())

# --- KINO QIDIRISH (ASOSIY QISM) ---
@dp.message_handler(lambda m: m.text.isdigit())
async def search_movie(message: types.Message):
    u_id = message.from_user.id
    
    # Block tekshiruvi
    cur.execute("SELECT status FROM users WHERE user_id=?", (u_id,))
    user_status = cur.fetchone()
    if user_status and user_status[0] == 'blocked':
        return await message.answer("Siz botdan chetlatilgansiz!")

    # Obuna tekshiruvi
    is_ok = await check_sub(u_id)
    if not is_ok:
        cur.execute("SELECT url FROM channels")
        ch_list = cur.fetchall()
        kb = InlineKeyboardMarkup(row_width=1)
        for (url,) in ch_list:
            btn_url = url if url.startswith("http") else f"https://t.me/{url[1:]}"
            kb.add(InlineKeyboardButton("A'zo bo'lish", url=btn_url))
        kb.add(InlineKeyboardButton("Tekshirish ✅", callback_data="check_again"))
        return await message.answer("Botdan foydalanish uchun kanallarga a'zo bo'ling!", reply_markup=kb)

    # Kino yuborish
    cur.execute("SELECT file_id FROM movies WHERE code=?", (message.text,))
    res = cur.fetchone()
    if res:
        await bot.send_video(message.chat.id, res[0], caption=f"Kino kodi: {message.text}")
    else:
        await message.answer("Bunday kodli kino topilmadi.")

# --- ADMIN ISHLARI (CALLBACKS) ---
@dp.callback_query_handler(user_id=ADMIN_ID)
async def admin_callbacks(call: types.CallbackQuery):
    if call.data == "add_kino":
        await AdminStates.wait_kino_code.set()
        await call.message.answer("Kino uchun kod kiriting:")
    
    elif call.data == "user_list":
        cur.execute("SELECT username, user_id, status FROM users")
        users = cur.fetchall()
        text = "Foydalanuvchilar:\n\n"
        for u in users:
            text += f"{u[0]} | ID: {u[1]} | {u[2]}\n"
        await call.message.answer(text[:4000])

    elif call.data == "add_chan":
        await AdminStates.wait_channel_url.set()
        await call.message.answer("Kanal linkini yuboring (TG bo'lsa @ bilan, bo'lmasa https:// bilan):")

# --- KINO QO'SHISH DAVOMI ---
@dp.message_handler(state=AdminStates.wait_kino_code, user_id=ADMIN_ID)
async def set_kino_code(message: types.Message, state: FSMContext):
    await state.update_data(c=message.text)
    await AdminStates.wait_kino_file.set()
    await message.answer("Endi videoni o'zini yuboring:")

@dp.message_handler(content_types=['video'], state=AdminStates.wait_kino_file, user_id=ADMIN_ID)
async def set_kino_file(message: types.Message, state: FSMContext):
    data = await state.get_data()
    cur.execute("INSERT OR REPLACE INTO movies VALUES (?, ?)", (data['c'], message.video.file_id))
    conn.commit()
    await state.finish()
    await message.answer("Kino saqlandi ✅")

# --- KANAL QO'SHISH DAVOMI ---
@dp.message_handler(state=AdminStates.wait_channel_url, user_id=ADMIN_ID)
async def set_chan_url(message: types.Message, state: FSMContext):
    cur.execute("INSERT OR IGNORE INTO channels VALUES (?)", (message.text,))
    conn.commit()
    await state.finish()
    await message.answer("Kanal qo'shildi ✅")

# --- BLOKLASH (Admin shunchaki /block ID yozadi) ---
@dp.message_handler(commands=['block'], user_id=ADMIN_ID)
async def block_user(message: types.Message):
    target = message.get_args()
    cur.execute("UPDATE users SET status='blocked' WHERE user_id=?", (target,))
    conn.commit()
    await message.answer(f"Foydalanuvchi {target} bloklandi.")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
