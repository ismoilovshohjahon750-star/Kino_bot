import logging
import asyncio
import aiosqlite
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.client.default import DefaultBotProperties

# ⚙️ KONFIGURATSIYA
TOKEN = '8026117592:AAHJ8dRIT638-mjtzmAdXBbeuCx_YFOlxQs'
ADMIN_ID = 8453381252
DB_NAME = "milliarder.db"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode='HTML'))
dp = Dispatcher()

# 📝 HOLATLAR (FSM)
class AdminStates(StatesGroup):
    kino_kodi = State()
    kino_vidosi = State()
    reklama_yuborish = State()
    kanal_qoshish = State()

# 🛡 OBUNANI TEKSHIRISH FUNKSIYASI
async def check_sub(user_id):
    if user_id == ADMIN_ID:
        return True
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT id FROM channels") as cur:
            channels = await cur.fetchall()
    
    if not channels:
        return True
        
    for (ch_id,) in channels:
        try:
            member = await bot.get_chat_member(chat_id=ch_id, user_id=user_id)
            if member.status not in ['member', 'administrator', 'creator']:
                return False
        except Exception as e:
            logging.error(f"Xatolik: {ch_id} kanalida foydalanuvchini tekshirib bo'lmadi: {e}")
            continue
    return True

# 🎹 ADMIN KLAVIATURASI
def admin_panel_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🎬 Kino qo'shish"), KeyboardButton(text="📊 Statistika")],
        [KeyboardButton(text="📢 Kanallarni boshqarish")],
        [KeyboardButton(text="✉️ Reklama tarqatish"), KeyboardButton(text="🏠 Bosh menyu")]
    ], resize_keyboard=True)

# 🚀 START BUYRUG'I
@dp.message(Command("start"))
async def start_handler(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR IGNORE INTO users (id) VALUES (?)", (user_id,))
        await db.commit()

    if not await check_sub(user_id):
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute("SELECT id FROM channels") as cur:
                channels = await cur.fetchall()
        
        inline_kb = []
        for (ch_id,) in channels:
            # @ belgisini olib tashlab to'g'ri link yasash
            link = f"https://t.me/{ch_id.replace('@', '')}"
            inline_kb.append([InlineKeyboardButton(text=f"Obuna bo'lish: {ch_id}", url=link)])
        
        inline_kb.append([InlineKeyboardButton(text="✅ Tekshirish", callback_data="check_sub")])
        
        return await message.answer(
            "<b>Botdan foydalanish uchun kanallarimizga obuna bo'ling!</b>", 
            reply_markup=InlineKeyboardMarkup(inline_keyboard=inline_kb)
        )
    
    await message.answer("👋 Salom! Kino kodini yuboring.")

# 🔄 OBUNANI QAYTA TEKSHIRISH (CALLBACK)
@dp.callback_query(F.data == "check_sub")
async def check_cb(call: CallbackQuery):
    if await check_sub(call.from_user.id):
        await call.message.delete()
        await call.message.answer("✅ Rahmat! Obuna tasdiqlandi. Endi kino kodini yuborishingiz mumkin.")
    else:
        await call.answer("❌ Hali hamma kanallarga obuna bo'lmagansiz!", show_alert=True)

# 🛠 ADMIN PANELGA KIRISH
@dp.message(Command("admin"))
async def admin_cmd(message: Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer("🛠 <b>Admin panelga xush kelibsiz!</b>", reply_markup=admin_panel_kb())

@dp.message(F.text == "🏠 Bosh menyu")
async def home(message: Message):
    await message.answer("Siz bosh menyudasiz. Kino kodini yuboring.", reply_markup=ReplyKeyboardRemove())

# 📊 STATISTIKA
@dp.message(F.text == "📊 Statistika", F.from_user.id == ADMIN_ID)
async def stats(message: Message):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as u:
            u_cnt = (await u.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM movies") as m:
            m_cnt = (await m.fetchone())[0]
    await message.answer(f"📈 <b>Statistika:</b>\n\n👤 Foydalanuvchilar: {u_cnt}\n🎬 Kinolar: {m_cnt}")

# 📢 KANALLARNI BOSHQARISH
@dp.message(F.text == "📢 Kanallarni boshqarish", F.from_user.id == ADMIN_ID)
async def manage_channels(message: Message):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT id FROM channels") as cur:
            channels = await cur.fetchall()
    
    kb = []
    for (ch_id,) in channels:
        kb.append([InlineKeyboardButton(text=f"❌ O'chirish {ch_id}", callback_data=f"del_ch:{ch_id}")])
    
    kb.append([InlineKeyboardButton(text="➕ Kanal qo'shish", callback_data="add_ch")])
    await message.answer("<b>Majburiy obuna kanallari ro'yxati:</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data == "add_ch")
async def add_ch_call(call: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.kanal_qoshish)
    await call.message.answer("Kanalning @username sini yuboring (masalan: @kanal_nomi):")
    await call.answer()

@dp.message(AdminStates.kanal_qoshish)
async def save_channel(message: Message, state: FSMContext):
    if message.text.startswith("@"):
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("INSERT OR IGNORE INTO channels (id) VALUES (?)", (message.text,))
            await db.commit()
        await state.clear()
        await message.answer(f"✅ {message.text} muvaffaqiyatli qo'shildi!", reply_markup=admin_panel_kb())
    else:
        await message.answer("❌ Xato! Kanal usernami @ belgisi bilan boshlanishi kerak.")

@dp.callback_query(F.data.startswith("del_ch:"))
async def delete_channel(call: CallbackQuery):
    ch_id = call.data.split(":")[1]
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM channels WHERE id = ?", (ch_id,))
        await db.commit()
    await call.answer("Kanal o'chirildi", show_alert=True)
    await manage_channels(call.message)

# 🎬 KINO QO'SHISH
@dp.message(F.text == "🎬 Kino qo'shish", F.from_user.id == ADMIN_ID)
async def start_add_movie(message: Message, state: FSMContext):
    await state.set_state(AdminStates.kino_kodi)
    await message.answer("Kino uchun kod kiriting (masalan: 123):")

@dp.message(AdminStates.kino_kodi)
async def process_movie_code(message: Message, state: FSMContext):
    await state.update_data(code=message.text)
    await state.set_state(AdminStates.kino_vidosi)
    await message.answer("Endi ushbu kodga tegishli videoni yuboring:")

@dp.message(AdminStates.kino_vidosi, F.video)
async def process_movie_video(message: Message, state: FSMContext):
    data = await state.get_data()
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR REPLACE INTO movies (code, file_id) VALUES (?, ?)", (data['code'], message.video.file_id))
        await db.commit()
    await state.clear()
    await message.answer(f"✅ Kino saqlandi! Kod: {data['code']}", reply_markup=admin_panel_kb())

# ✉️ REKLAMA TARQATISH
@dp.message(F.text == "✉️ Reklama tarqatish", F.from_user.id == ADMIN_ID)
async def start_ads(message: Message, state: FSMContext):
    await state.set_state(AdminStates.reklama_yuborish)
    await message.answer("Reklama postini yuboring (rasm, video yoki matn):")

@dp.message(AdminStates.reklama_yuborish)
async def send_ads(message: Message, state: FSMContext):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT id FROM users") as cur:
            users = await cur.fetchall()
    
    count = 0
    await message.answer("🚀 Reklama tarqatish boshlandi...")
    for (uid,) in users:
        try:
            await message.copy_to(uid)
            count += 1
            await asyncio.sleep(0.05) # Telegram limitlaridan oshmaslik uchun
        except:
            continue
    
    await state.clear()
    await message.answer(f"✅ Reklama tugadi! {count} ta foydalanuvchiga yetkazildi.", reply_markup=admin_panel_kb())

# 🔍 KINO QIDIRISH
@dp.message(F.text.isdigit())
async def search_movie(message: Message):
    if not await check_sub(message.from_user.id):
        return await start_handler(message, None)
        
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT file_id FROM movies WHERE code = ?", (message.text,)) as cur:
            movie = await cur.fetchone()
            if movie:
                await message.answer_video(movie[0], caption=f"🎬 Kino kodi: {message.text}")
            else:
                await message.answer("😔 Kechirasiz, bu kod bilan hech narsa topilmadi.")

# 🏁 BOTNI ISHGA TUSHIRISH
async def main():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY)")
        await db.execute("CREATE TABLE IF NOT EXISTS movies (code TEXT PRIMARY KEY, file_id TEXT)")
        await db.execute("CREATE TABLE IF NOT EXISTS channels (id TEXT PRIMARY KEY)")
        await db.commit()
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot to'xtatildi")
