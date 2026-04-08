import logging
import sqlite3
from aiogram import Bot, Dispatcher, types, executor
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# --- KONFIGURATSIYA ---
API_TOKEN = 'BOT_TOKEN'
ADMIN_ID = 8453381252 # Rasmda ko'ringan ID

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

class AdminStates(StatesGroup):
    wait_kino_code = State()
    wait_kino_file = State()
    wait_channel_url = State()
    wait_del_kino = State()

# --- ASOSIY ADMIN PANEL TUGMALARI ---
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

# --- ADMIN BUYRUQLARI ---
@dp.message_handler(commands=['admin'], user_id=ADMIN_ID)
async def admin_start(message: types.Message):
    await message.answer("🛠 **Admin boshqaruv paneli:**", reply_markup=admin_main_kb(), parse_mode="Markdown")

# --- FOYDALANUVCHILARNI BOSHQARISH ---
@dp.callback_query_handler(text="list_users", user_id=ADMIN_ID)
async def show_users(call: types.CallbackQuery):
    cur.execute("SELECT user_id, username, status FROM users")
    users = cur.fetchall()
    kb = InlineKeyboardMarkup(row_width=1)
    for u_id, uname, status in users:
        icon = "🔴" if status == "blocked" else "🟢"
        kb.add(InlineKeyboardButton(f"{icon} {uname} (ID: {u_id})", callback_data=f"user_info:{u_id}"))
    kb.add(InlineKeyboardButton("⬅️ Orqaga", callback_data="back_to_admin"))
    await call.message.edit_text("👥 Foydalanuvchini tanlang:", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith("user_info:"), user_id=ADMIN_ID)
async def user_manage(call: types.CallbackQuery):
    u_id = call.data.split(":")[1]
    cur.execute("SELECT username, status FROM users WHERE user_id=?", (u_id,))
    user = cur.fetchone()
    
    kb = InlineKeyboardMarkup(row_width=2)
    if user[1] == "active":
        kb.add(InlineKeyboardButton("🚫 Bloklash", callback_data=f"confirm_block:{u_id}"))
    else:
        kb.add(InlineKeyboardButton("✅ Blokdan ochish", callback_data=f"unblock:{u_id}"))
    kb.add(InlineKeyboardButton("⬅️ Orqaga", callback_data="list_users"))
    
    status_text = "Faol ✅" if user[1] == "active" else "Bloklangan 🚫"
    await call.message.edit_text(f"👤 Foydalanuvchi: {user[0]}\n🆔 ID: {u_id}\n📊 Holati: {status_text}", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith("confirm_block:"), user_id=ADMIN_ID)
async def confirm_block(call: types.CallbackQuery):
    u_id = call.data.split(":")[1]
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("Ha, bloklansin", callback_data=f"do_block:{u_id}"),
        InlineKeyboardButton("Yo'q", callback_data=f"user_info:{u_id}")
    )
    await call.message.edit_text("⚠️ Haqiqatdan ham bloklamoqchimisiz?", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith("do_block:"), user_id=ADMIN_ID)
async def do_block(call: types.CallbackQuery):
    u_id = call.data.split(":")[1]
    cur.execute("UPDATE users SET status='blocked' WHERE user_id=?", (u_id,))
    conn.commit()
    await call.answer("Foydalanuvchi bloklandi 🚫")
    await show_users(call)

@dp.callback_query_handler(lambda c: c.data.startswith("unblock:"), user_id=ADMIN_ID)
async def do_unblock(call: types.CallbackQuery):
    u_id = call.data.split(":")[1]
    cur.execute("UPDATE users SET status='active' WHERE user_id=?", (u_id,))
    conn.commit()
    await call.answer("Blokdan ochildi ✅")
    await show_users(call)

# --- KANALLARNI O'CHIRISH ---
@dp.callback_query_handler(text="list_channels", user_id=ADMIN_ID)
async def show_channels(call: types.CallbackQuery):
    cur.execute("SELECT url FROM channels")
    chans = cur.fetchall()
    kb = InlineKeyboardMarkup(row_width=1)
    for (url,) in chans:
        kb.add(InlineKeyboardButton(f"❌ {url}", callback_data=f"del_ch_conf:{url}"))
    kb.add(InlineKeyboardButton("⬅️ Orqaga", callback_data="back_to_admin"))
    await call.message.edit_text("🗑 O'chirish uchun kanalni tanlang:", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith("del_ch_conf:"), user_id=ADMIN_ID)
async def del_ch_confirm(call: types.CallbackQuery):
    url = call.data.split("del_ch_conf:")[1]
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("Ha, o'chirilsin", callback_data=f"do_del_ch:{url}"),
        InlineKeyboardButton("Yo'q", callback_data="list_channels")
    )
    await call.message.edit_text(f"⚠️ {url} kanalini o'chirasizmi?", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith("do_del_ch:"), user_id=ADMIN_ID)
async def do_del_ch(call: types.CallbackQuery):
    url = call.data.split("do_del_ch:")[1]
    cur.execute("DELETE FROM channels WHERE url=?", (url,))
    conn.commit()
    await call.answer("Kanal o'chirildi ✅")
    await show_channels(call)

# --- ORQAGA QAYTISH ---
@dp.callback_query_handler(text="back_to_admin", user_id=ADMIN_ID)
async def back_to_admin(call: types.CallbackQuery):
    await call.message.edit_text("🛠 **Admin boshqaruv paneli:**", reply_markup=admin_main_kb(), parse_mode="Markdown")

# --- QOLGAN FUNKSIYALAR (OLDINGI KODDAGI KABI) ---
# ... (Kino qo'shish va kanal qo'shish funksiyalari o'zgarmaydi)

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
                                    
