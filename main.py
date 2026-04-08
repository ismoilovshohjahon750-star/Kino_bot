import logging
import sqlite3
from aiogram import Bot, Dispatcher, types, executor
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# --- KONFIGURATSIYA ---
API_TOKEN = '8026117592:AAFFErkQRHvD-poKjPzMUB0P2xnXjBLymzo'  # BotFather'dan olingan token
ADMIN_ID = 8453381252    # Sizning ID raqamingiz

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
conn.commit()

# --- HOLATLAR ---
class AdminStates(StatesGroup):
    wait_kino_code = State()
    wait_kino_file = State()
    wait_channel_url = State()
    wait_del_kino_code = State()

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
            except:
                continue
    return True

# --- ADMIN PANEL TUGMALARI ---
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

# --- FOYDALANUVCHI QISMI ---
@dp.message_handler(commands=['start'])
async def start_cmd(message: types.Message):
    u_id = message.from_user.id
    uname = f"@{message.from_user.username}" if message.from_user.username else "Noma'lum"
    cur.execute("INSERT OR IGNORE INTO users VALUES (?, ?, ?)", (u_id, uname, 'active'))
    conn.commit()
    await message.answer("👋 Salom! Kino kodini yuboring.")

@dp.callback_query_handler(text="check_again")
async def check_again(call: types.CallbackQuery):
    if await check_sub(call.from_user.id):
        await call.message.edit_text("✅ Rahmat! Endi kino kodini yuborishingiz mumkin.")
    else:
        await call.answer("❌ Hali ham hamma kanallarga a'zo emassiz!", show_alert=True)

@dp.message_handler(lambda m: m.text.isdigit())
async def search_movie(message: types.Message):
    u_id = message.from_user.id
    cur.execute("SELECT status FROM users WHERE user_id=?", (u_id,))
    user = cur.fetchone()
    if user and user[0] == 'blocked':
        return await message.answer("🚫 Siz botdan bloklangansiz!")

    # Obunani tekshirish
    if not await check_sub(u_id):
        cur.execute("SELECT url FROM channels")
        ch_list = cur.fetchall()
        kb = InlineKeyboardMarkup(row_width=1)
        for (url,) in ch_list:
            btn_url = url if url.startswith("http") else f"https://t.me/{url[1:]}"
            kb.add(InlineKeyboardButton("A'zo bo'lish", url=btn_url))
        kb.add(InlineKeyboardButton("Tekshirish ✅", callback_data="check_again"))
        return await message.answer("⚠️ Botdan foydalanish uchun quyidagi kanallarga a'zo bo'ling:", reply_markup=kb)

    cur.execute("SELECT file_id FROM movies WHERE code=?", (message.text,))
    res = cur.fetchone()
    if res:
        await bot.send_video(message.chat.id, res[0], caption=f"🎬 Kino kodi: {message.text}")
    else:
        await message.answer("😔 Kechirasiz, bu kod bilan kino topilmadi.")

# --- ADMIN PANEL FUNKSIYALARI ---
@dp.message_handler(commands=['admin'], user_id=ADMIN_ID)
async def admin_panel(message: types.Message):
    await message.answer("🛠 Admin boshqaruv paneli:", reply_markup=admin_main_kb())

# 1. Kino qo'shish
@dp.callback_query_handler(text="add_kino", user_id=ADMIN_ID)
async def add_kino_step1(call: types.CallbackQuery):
    await AdminStates.wait_kino_code.set()
    await call.message.edit_text("🔢 Kino uchun yangi kod yuboring:")

@dp.message_handler(state=AdminStates.wait_kino_code, user_id=ADMIN_ID)
async def add_kino_step2(message: types.Message, state: FSMContext
