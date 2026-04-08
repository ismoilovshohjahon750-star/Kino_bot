import logging
import sqlite3
from aiogram import Bot, Dispatcher, types, executor
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup

# --- KONFIGURATSIYA ---
API_TOKEN = '8026117592:AAFG0ueeWKImCiMX9HkH97qyZBps-DiORUw'
SUPER_ADMIN = 8453381252 

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
cur.execute("CREATE TABLE IF NOT EXISTS admins (user_id INTEGER PRIMARY KEY)")
conn.commit()

# Super adminni bazaga qo'shish
cur.execute("INSERT OR IGNORE INTO admins VALUES (?)", (SUPER_ADMIN,))
conn.commit()

# --- HOLATLAR ---
class AdminStates(StatesGroup):
    wait_kino_code = State()
    wait_kino_file = State()
    wait_channel_url = State()
    wait_del_kino = State()
    wait_del_chan = State()
    wait_new_admin = State()

# --- ADMINLIKNI TEKSHIRISH ---
async def is_admin(user_id):
    cur.execute("SELECT user_id FROM admins WHERE user_id=?", (user_id,))
    return cur.fetchone() is not None

# --- FOYDALANUVCHI QISMI ---
@dp.message_handler(commands=['start'])
async def start_cmd(message: types.Message):
    u_id = message.from_user.id
    uname = f"@{message.from_user.username}" if message.from_user.username else "Noma'lum"
    cur.execute("INSERT OR IGNORE INTO users VALUES (?, ?, ?)", (u_id, uname, 'active'))
    conn.commit()
    await message.answer("👋 Salom! Kino kodini raqamlar bilan yuboring.")

# --- ADMIN PANEL KOMANDASI ---
@dp.message_handler(commands=['admin'])
async def admin_help(message: types.Message):
    if await is_admin(message.from_user.id):
        text = (
            "🛠 **Admin Buyruqlari:**\n\n"
            "🎬 **Kinolar:**\n"
            "/addkino - Kino qo'shish\n"
            "/delkino - Kinoni o'chirish\n\n"
            "📢 **Kanallar:**\n"
            "/addchan - Kanal qo'shish\n"
            "/delchan - Kanalni o'chirish\n\n"
            "👥 **Boshqaruv:**\n"
            "/users - Foydalanuvchilar\n"
            "/admins - Adminlar ro'yxati\n"
        )
        if message.from_user.id == SUPER_ADMIN:
            text += "/addadmin - Yangi admin qo'shish\n"
        await message.answer(text, parse_mode="Markdown")

# --- KINO BOSHQARUV KOMANDALARI ---
@dp.message_handler(commands=['addkino'])
async def add_kino_start(message: types.Message):
    if await is_admin(message.from_user.id):
        await AdminStates.wait_kino_code.set()
        await message.answer("🔢 Kino uchun kod yuboring:")

@dp.message_handler(state=AdminStates.wait_kino_code)
async def process_code(message: types.Message, state: FSMContext):
    await state.update_data(code=message.text)
    await AdminStates.wait_kino_file.set()
    await message.answer("📹 Endi videoni yuboring:")

@dp.message_handler(content_types=['video'], state=AdminStates.wait_kino_file)
async def process_video(message: types.Message, state: FSMContext):
    data = await state.get_data()
    cur.execute("INSERT OR REPLACE INTO movies VALUES (?, ?)", (data['code'], message.video.file_id))
    conn.commit()
    await state.finish()
    await message.answer(f"✅ Kino {data['code']} kodi bilan saqlandi.")

@dp.message_handler(commands=['delkino'])
async def del_kino_start(message: types.Message):
    if await is_admin(message.from_user.id):
        await AdminStates.wait_del_kino.set()
        await message.answer("🗑 O'chiriladigan kino kodini yuboring:")

@dp.message_handler(state=AdminStates.wait_del_kino)
async def process_del_k(message: types.Message, state: FSMContext):
    cur.execute("DELETE FROM movies WHERE code=?", (message.text,))
    conn.commit()
    await state.finish()
    await message.answer(f"✅ Kod {message.text} o'chirildi.")

# --- KANAL BOSHQARUV KOMANDALARI ---
@dp.message_handler(commands=['addchan'])
async def add_chan_start(message: types.Message):
    if await is_admin(message.from_user.id):
        await AdminStates.wait_channel_url.set()
        await message.answer("🔗 Kanal linki yoki @username yuboring:")

@dp.message_handler(state=AdminStates.wait_channel_url)
async def process_add_ch(message: types.Message, state: FSMContext):
    cur.execute("INSERT OR IGNORE INTO channels VALUES (?)", (message.text,))
    conn.commit()
    await state.finish()
    await message.answer("✅ Kanal qo'shildi.")

@dp.message_handler(commands=['delchan'])
async def del_chan_start(message: types.Message):
    if await is_admin(message.from_user.id):
        cur.execute("SELECT url FROM channels")
        chans = cur.fetchall()
        if not chans:
            return await message.answer("Ro'yxat bo'sh.")
        text = "O'chirish uchun linkni yuboring:\n\n" + "\n".join([c[0] for c in chans])
        await AdminStates.wait_del_chan.set()
        await message.answer(text)

@dp.message_handler(state=AdminStates.wait_del_chan)
async def process_del_ch(message: types.Message, state: FSMContext):
    cur.execute("DELETE FROM channels WHERE url=?", (message.text,))
    conn.commit()
    await state.finish()
    await message.answer("✅ Kanal o'chirildi.")

# --- ADMIN QO'SHISH (SUPER ADMIN) ---
@dp.message_handler(commands=['addadmin'])
async def add_admin_cmd(message: types.Message):
    if message.from_user.id == SUPER_ADMIN:
        await AdminStates.wait_new_admin.set()
        await message.answer("🆔 Yangi admin Telegram ID raqamini yuboring:")

@dp.message_handler(state=AdminStates.wait_new_admin)
async def process_new_adm(message: types.Message, state: FSMContext):
    if message.text.isdigit():
        cur.execute("INSERT OR IGNORE INTO admins VALUES (?)", (int(message.text),))
        conn.commit()
        await message.answer("⭐ Yangi admin qo'shildi.")
    else:
        await message.answer("❌ ID faqat raqamlardan iborat bo'lishi kerak.")
    await state.finish()

# --- KINO QIDIRISH (FOYDALANUVCHILAR) ---
@dp.message_handler(lambda m: m.text.isdigit())
async def find_movie(message: types.Message):
    cur.execute("SELECT file_id FROM movies WHERE code=?", (message.text,))
    res = cur.fetchone()
    if res:
        await bot.send_video(message.chat.id, res[0], caption=f"🎬 Kod: {message.text}")
    else:
        await message.answer("😔 Kino topilmadi.")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
    
