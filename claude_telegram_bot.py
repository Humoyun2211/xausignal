import logging
import os
import sqlite3
import aiohttp
from datetime import datetime
from groq import Groq
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)

# =============================================
# SOZLAMALAR
# =============================================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")
EXCHANGE_API_KEY = os.getenv("EXCHANGE_API_KEY")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

MODEL = "llama-3.3-70b-versatile"
MAX_TOKENS = 2048
MAX_HISTORY = 30
DB_PATH = "nova_ai.db"

SYSTEM_PROMPT = """Sen Nova AI — eng aqlli Telegram yordamchisan.
Quyidagilarni bajara olasan:
- Har qanday savolga javob berish
- Tarjima qilish (100+ til)
- Kod yozish va tushuntirish
- Moliya va XAU/USD tahlil
- Matn yozish va tahrirlash
- Matematik masalalar yechish

Qoidalar:
- Foydalanuvchi qaysi tilda yozsa, o'sha tilda javob ber
- Javoblar aniq, qisqa va foydali bo'lsin
- Emoji ishlatib xabarlarni chiroyli qil
- Doimo do'stona va professional bo'l"""

# =============================================
# LOGGING
# =============================================
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# =============================================
# DATABASE
# =============================================

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        name TEXT,
        username TEXT,
        joined TEXT,
        messages INTEGER DEFAULT 0,
        mode TEXT DEFAULT 'general',
        city TEXT DEFAULT 'Tashkent'
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS messages_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        message TEXT,
        timestamp TEXT
    )''')
    conn.commit()
    conn.close()


def db_get_user(user_id: int) -> dict:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return {
            "user_id": row[0], "name": row[1], "username": row[2],
            "joined": row[3], "messages": row[4], "mode": row[5], "city": row[6]
        }
    return None


def db_save_user(user_id: int, name: str, username: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    existing = db_get_user(user_id)
    if not existing:
        c.execute(
            "INSERT INTO users (user_id, name, username, joined, messages, mode, city) VALUES (?,?,?,?,?,?,?)",
            (user_id, name, username or "", datetime.now().strftime("%Y-%m-%d %H:%M"), 0, "general", "Tashkent")
        )
    else:
        c.execute("UPDATE users SET name=?, username=? WHERE user_id=?", (name, username or "", user_id))
    conn.commit()
    conn.close()


def db_increment_messages(user_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET messages = messages + 1 WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()


def db_update_mode(user_id: int, mode: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET mode=? WHERE user_id=?", (mode, user_id))
    conn.commit()
    conn.close()


def db_update_city(user_id: int, city: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET city=? WHERE user_id=?", (city, user_id))
    conn.commit()
    conn.close()


def db_get_stats() -> dict:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]
    c.execute("SELECT SUM(messages) FROM users")
    total_messages = c.fetchone()[0] or 0
    c.execute("SELECT name, messages FROM users ORDER BY messages DESC LIMIT 5")
    top_users = c.fetchall()
    conn.close()
    return {"total_users": total_users, "total_messages": total_messages, "top_users": top_users}


# =============================================
# AI VA XIZMATLAR
# =============================================
client = Groq(api_key=GROQ_API_KEY)
conversation_history: dict[int, list] = {}
bot_start_time = datetime.now()

MODE_PROMPTS = {
    "general": "Sen Nova AI — universal aqlli yordamchisan. Har qanday mavzuda gaplash.",
    "finance": "Sen moliya va trading ekspertisan. XAU/USD, valyuta, investitsiya haqida professional maslahat ber.",
    "coding": "Sen dasturlash ekspertisan. Kod yoz, debug qil, tushuntir. Python, JavaScript, va boshqa tillar.",
    "translate": "Sen professional tarjimonsan. 100+ tilda aniq va tabiiy tarjima qil.",
    "writer": "Sen professional yozuvchisan. Maqola, post, story, kreativ matnlar yoz.",
    "teacher": "Sen sabr-toqatli o'qituvchisan. Har qanday mavzuni oddiy va tushunarli tushuntir.",
}

MODE_NAMES = {
    "general": "💬 Umumiy",
    "finance": "📈 Moliya",
    "coding": "💻 Dasturlash",
    "translate": "🌐 Tarjimon",
    "writer": "✍️ Yozuvchi",
    "teacher": "📚 O'qituvchi",
}


def get_groq_response(user_id: int, user_message: str, mode: str = "general") -> str:
    if user_id not in conversation_history:
        conversation_history[user_id] = []

    conversation_history[user_id].append({"role": "user", "content": user_message})

    if len(conversation_history[user_id]) > MAX_HISTORY:
        conversation_history[user_id] = conversation_history[user_id][-MAX_HISTORY:]

    system = MODE_PROMPTS.get(mode, SYSTEM_PROMPT)
    messages = [{"role": "system", "content": system}] + conversation_history[user_id]

    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        max_tokens=MAX_TOKENS,
        temperature=0.7,
    )

    assistant_message = response.choices[0].message.content
    conversation_history[user_id].append({"role": "assistant", "content": assistant_message})
    return assistant_message


async def get_weather(city: str) -> str:
    try:
        url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={WEATHER_API_KEY}&units=metric&lang=ru"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                data = await resp.json()

        if data.get("cod") != 200:
            return f"❌ '{city}' shahri topilmadi."

        name = data["name"]
        country = data["sys"]["country"]
        temp = data["main"]["temp"]
        feels = data["main"]["feels_like"]
        humidity = data["main"]["humidity"]
        wind = data["wind"]["speed"]
        desc = data["weather"][0]["description"].capitalize()
        icon_map = {
            "Clear": "☀️", "Clouds": "☁️", "Rain": "🌧️",
            "Snow": "❄️", "Thunderstorm": "⛈️", "Drizzle": "🌦️",
            "Mist": "🌫️", "Fog": "🌫️"
        }
        main_weather = data["weather"][0]["main"]
        icon = icon_map.get(main_weather, "🌤️")

        return (
            f"{icon} *{name}, {country}*\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🌡 Harorat: *{temp:.1f}°C*\n"
            f"🤔 His qilinadi: {feels:.1f}°C\n"
            f"💧 Namlik: {humidity}%\n"
            f"💨 Shamol: {wind} m/s\n"
            f"📋 Holat: {desc}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🕐 {datetime.now().strftime('%H:%M, %d.%m.%Y')}"
        )
    except Exception as e:
        logger.error(f"Ob-havo xatosi: {e}")
        return "❌ Ob-havo ma'lumotini olishda xato."


async def get_currency() -> str:
    try:
        url = f"https://v6.exchangerate-api.com/v6/{EXCHANGE_API_KEY}/latest/USD"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                data = await resp.json()

        rates = data["conversion_rates"]
        uzs = rates.get("UZS", 0)
        rub = rates.get("RUB", 0)
        eur = rates.get("EUR", 0)
        gbp = rates.get("GBP", 0)
        jpy = rates.get("JPY", 0)

        return (
            f"💱 *Valyuta Kurslari*\n"
            f"_(1 USD ga nisbatan)_\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🇺🇿 UZS: *{uzs:,.0f}* so'm\n"
            f"🇷🇺 RUB: *{rub:.2f}* rubl\n"
            f"🇪🇺 EUR: *{eur:.4f}*\n"
            f"🇬🇧 GBP: *{gbp:.4f}*\n"
            f"🇯🇵 JPY: *{jpy:.2f}*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🕐 {datetime.now().strftime('%H:%M, %d.%m.%Y')}"
        )
    except Exception as e:
        logger.error(f"Valyuta xatosi: {e}")
        return "❌ Valyuta ma'lumotini olishda xato."


# =============================================
# KLAVIATURALAR
# =============================================

def main_inline_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("🔄 Yangi suhbat", callback_data="reset"),
            InlineKeyboardButton("📊 Statistika", callback_data="stats"),
        ],
        [
            InlineKeyboardButton("🌤 Ob-havo", callback_data="weather"),
            InlineKeyboardButton("💱 Valyuta", callback_data="currency"),
        ],
        [
            InlineKeyboardButton("🧠 Rejimlar", callback_data="modes"),
            InlineKeyboardButton("ℹ️ Haqida", callback_data="about"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def modes_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("💬 Umumiy", callback_data="mode_general"),
            InlineKeyboardButton("📈 Moliya", callback_data="mode_finance"),
        ],
        [
            InlineKeyboardButton("💻 Dasturlash", callback_data="mode_coding"),
            InlineKeyboardButton("🌐 Tarjimon", callback_data="mode_translate"),
        ],
        [
            InlineKeyboardButton("✍️ Yozuvchi", callback_data="mode_writer"),
            InlineKeyboardButton("📚 O'qituvchi", callback_data="mode_teacher"),
        ],
        [InlineKeyboardButton("⬅️ Orqaga", callback_data="back_main")],
    ]
    return InlineKeyboardMarkup(keyboard)


def weather_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("🏙 Shahrimni o'zgartirish", callback_data="set_city"),
        ],
        [InlineKeyboardButton("⬅️ Orqaga", callback_data="back_main")],
    ]
    return InlineKeyboardMarkup(keyboard)


def reply_keyboard():
    keyboard = [
        [KeyboardButton("🌤 Ob-havo"), KeyboardButton("💱 Valyuta")],
        [KeyboardButton("🧠 Rejimlar"), KeyboardButton("📊 Statistika")],
        [KeyboardButton("🔄 Yangi suhbat"), KeyboardButton("ℹ️ Haqida")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


# =============================================
# KOMANDALAR
# =============================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    conversation_history[user.id] = []
    db_save_user(user.id, user.first_name, user.username)
    logger.info(f"Start: {user.first_name} ({user.id})")

    welcome = (
        f"✨ *Xush kelibsiz, {user.first_name}!*\n\n"
        f"🤖 Men *Nova AI* — sizning aqlli yordamchingizman!\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"⚡ *Imkoniyatlarim:*\n\n"
        f"💬 Har qanday savolga javob\n"
        f"🌐 100+ tilda tarjima\n"
        f"💻 Kod yozish va debug\n"
        f"📈 Moliya va XAU/USD tahlil\n"
        f"🌤 Real vaqt ob-havo\n"
        f"💱 Valyuta kurslari\n"
        f"📝 Matn yozish\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 *Komandalar:*\n"
        f"/start /reset /help\n"
        f"/stats /about /mode\n"
        f"/weather /currency\n\n"
        f"_Savolingizni yozing yoki tugmalardan foydalaning_ 👇"
    )

    await update.message.reply_text(
        welcome,
        parse_mode="Markdown",
        reply_markup=reply_keyboard()
    )
    await update.message.reply_text(
        "🎛 *Boshqaruv paneli:*",
        parse_mode="Markdown",
        reply_markup=main_inline_keyboard()
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📋 *Yordam markazi*\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🔹 *Komandalar:*\n\n"
        "/start — Botni boshlash\n"
        "/reset — Yangi suhbat\n"
        "/weather — Ob-havo\n"
        "/currency — Valyuta kurslari\n"
        "/mode — Rejim tanlash\n"
        "/stats — Statistika\n"
        "/about — Bot haqida\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "💡 *Maslahatlar:*\n\n"
        "• Ob-havo: `/weather London`\n"
        "• Tarjima: `Tarjima qil: salom`\n"
        "• Kod: `Python da list yoz`\n"
        "• /reset — yangi mavzu uchun\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🌐 O'zbek 🇺🇿 | Rus 🇷🇺 | Ingliz 🇬🇧",
        parse_mode="Markdown",
        reply_markup=main_inline_keyboard()
    )


async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conversation_history[update.effective_user.id] = []
    await update.message.reply_text(
        "🔄 *Suhbat tarixi tozalandi!*\n\n"
        "✅ Yangi suhbat boshlashingiz mumkin.\n"
        "_Savolingizni yozing..._",
        parse_mode="Markdown",
        reply_markup=main_inline_keyboard()
    )


async def weather_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = db_get_user(user.id)
    city = " ".join(context.args) if context.args else (user_data["city"] if user_data else "Tashkent")

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    result = await get_weather(city)
    await update.message.reply_text(
        result,
        parse_mode="Markdown",
        reply_markup=weather_keyboard()
    )


async def currency_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    result = await get_currency()
    await update.message.reply_text(
        result,
        parse_mode="Markdown",
        reply_markup=main_inline_keyboard()
    )


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = db_get_user(user.id)
    history_count = len(conversation_history.get(user.id, []))
    mode = user_data["mode"] if user_data else "general"
    uptime = datetime.now() - bot_start_time

    await update.message.reply_text(
        f"📊 *Sizning statistikangiz*\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 Ism: *{user.first_name}*\n"
        f"🆔 ID: `{user.id}`\n"
        f"📅 Qo'shilgan: {user_data['joined'] if user_data else '-'}\n"
        f"💬 Jami xabarlar: *{user_data['messages'] if user_data else 0}*\n"
        f"🧠 Xotirada: {history_count} xabar\n"
        f"🎯 Rejim: {MODE_NAMES.get(mode, '💬 Umumiy')}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"⚡ Model: `{MODEL}`\n"
        f"🕐 Bot ishlayapti: {int(uptime.total_seconds()//3600)}s {int((uptime.total_seconds()%3600)//60)}d",
        parse_mode="Markdown",
        reply_markup=main_inline_keyboard()
    )


async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats = db_get_stats()
    uptime = datetime.now() - bot_start_time

    await update.message.reply_text(
        f"ℹ️ *Nova AI haqida*\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🤖 *Nova AI v3.0* — zamonaviy AI yordamchi\n\n"
        f"⚡ *Texnologiyalar:*\n"
        f"• AI: `{MODEL}`\n"
        f"• Platform: Groq AI\n"
        f"• Ob-havo: OpenWeatherMap\n"
        f"• Valyuta: ExchangeRate API\n"
        f"• Baza: SQLite\n\n"
        f"📊 *Umumiy statistika:*\n"
        f"• Foydalanuvchilar: {stats['total_users']}\n"
        f"• Jami xabarlar: {stats['total_messages']}\n"
        f"• Ishlash vaqti: {int(uptime.total_seconds()//3600)}s\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 Versiya: *3.0.0* | 2026",
        parse_mode="Markdown",
        reply_markup=main_inline_keyboard()
    )


async def mode_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🧠 *Rejim tanlang:*\n\n"
        "• 💬 Umumiy — Har qanday mavzu\n"
        "• 📈 Moliya — XAU/USD, investitsiya\n"
        "• 💻 Dasturlash — Kod yozish\n"
        "• 🌐 Tarjimon — Tarjima\n"
        "• ✍️ Yozuvchi — Matn yozish\n"
        "• 📚 O'qituvchi — O'qitish",
        parse_mode="Markdown",
        reply_markup=modes_keyboard()
    )


async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_ID:
        await update.message.reply_text("❌ Ruxsat yo'q!")
        return

    stats = db_get_stats()
    uptime = datetime.now() - bot_start_time

    top_text = ""
    for name, msgs in stats["top_users"]:
        top_text += f"• {name}: {msgs} xabar\n"

    await update.message.reply_text(
        f"👑 *Admin Panel*\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 Foydalanuvchilar: *{stats['total_users']}*\n"
        f"💬 Jami xabarlar: *{stats['total_messages']}*\n"
        f"🤖 Faol suhbatlar: *{len([h for h in conversation_history.values() if h])}*\n"
        f"🕐 Ishlash: {int(uptime.total_seconds()//3600)}s\n\n"
        f"🏆 *Top foydalanuvchilar:*\n{top_text}",
        parse_mode="Markdown"
    )


# =============================================
# CALLBACK HANDLER
# =============================================

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user

    if query.data == "reset":
        conversation_history[user.id] = []
        await query.edit_message_text(
            "🔄 *Suhbat tozalandi!*\n\n✅ Yangi suhbat boshlashingiz mumkin.",
            parse_mode="Markdown",
            reply_markup=main_inline_keyboard()
        )

    elif query.data == "stats":
        user_data = db_get_user(user.id)
        history_count = len(conversation_history.get(user.id, []))
        await query.edit_message_text(
            f"📊 *Statistika:*\n\n"
            f"👤 {user.first_name}\n"
            f"💬 Xabarlar: *{user_data['messages'] if user_data else 0}*\n"
            f"🧠 Xotirada: {history_count} xabar\n"
            f"🎯 Rejim: {MODE_NAMES.get(user_data['mode'] if user_data else 'general', '💬 Umumiy')}",
            parse_mode="Markdown",
            reply_markup=main_inline_keyboard()
        )

    elif query.data == "weather":
        user_data = db_get_user(user.id)
        city = user_data["city"] if user_data else "Tashkent"
        result = await get_weather(city)
        await query.edit_message_text(
            result,
            parse_mode="Markdown",
            reply_markup=weather_keyboard()
        )

    elif query.data == "currency":
        result = await get_currency()
        await query.edit_message_text(
            result,
            parse_mode="Markdown",
            reply_markup=main_inline_keyboard()
        )

    elif query.data == "modes":
        await query.edit_message_text(
            "🧠 *Rejim tanlang:*\n\n"
            "• 💬 Umumiy — Har qanday mavzu\n"
            "• 📈 Moliya — XAU/USD, investitsiya\n"
            "• 💻 Dasturlash — Kod yozish\n"
            "• 🌐 Tarjimon — Tarjima\n"
            "• ✍️ Yozuvchi — Matn yozish\n"
            "• 📚 O'qituvchi — O'qitish",
            parse_mode="Markdown",
            reply_markup=modes_keyboard()
        )

    elif query.data.startswith("mode_"):
        mode_key = query.data.replace("mode_", "")
        db_update_mode(user.id, mode_key)
        conversation_history[user.id] = []
        mode_name = MODE_NAMES.get(mode_key, "💬 Umumiy")
        await query.edit_message_text(
            f"✅ *{mode_name} rejimi faollashtirildi!*\n\n"
            f"_{MODE_PROMPTS.get(mode_key, '')}_\n\n"
            f"Suhbat tarixi tozalandi. Boshlang! 💪",
            parse_mode="Markdown",
            reply_markup=main_inline_keyboard()
        )

    elif query.data == "set_city":
        context.user_data["waiting_city"] = True
        await query.edit_message_text(
            "🏙 *Shahar nomini yozing:*\n\n"
            "_Masalan: Tashkent, Moscow, London_",
            parse_mode="Markdown"
        )

    elif query.data == "about":
        stats = db_get_stats()
        await query.edit_message_text(
            f"ℹ️ *Nova AI v3.0*\n\n"
            f"⚡ Groq AI | SQLite\n"
            f"👥 {stats['total_users']} foydalanuvchi\n"
            f"💬 {stats['total_messages']} xabar\n"
            f"📌 Versiya: 3.0.0",
            parse_mode="Markdown",
            reply_markup=main_inline_keyboard()
        )

    elif query.data == "back_main":
        await query.edit_message_text(
            "🎛 *Boshqaruv paneli:*",
            parse_mode="Markdown",
            reply_markup=main_inline_keyboard()
        )


# =============================================
# XABAR HANDLERI
# =============================================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_message = update.message.text

    # Shahar kiritish rejimi
    if context.user_data.get("waiting_city"):
        context.user_data["waiting_city"] = False
        db_update_city(user.id, user_message)
        result = await get_weather(user_message)
        await update.message.reply_text(
            f"✅ Shahar saqlandi: *{user_message}*\n\n{result}",
            parse_mode="Markdown",
            reply_markup=main_inline_keyboard()
        )
        return

    # Reply klaviatura tugmalari
    quick_actions = {
        "🌤 Ob-havo": weather_command,
        "💱 Valyuta": currency_command,
        "📊 Statistika": stats_command,
        "ℹ️ Haqida": about_command,
        "🧠 Rejimlar": mode_command,
    }

    if user_message in quick_actions:
        await quick_actions[user_message](update, context)
        return

    if user_message == "🔄 Yangi suhbat":
        conversation_history[user.id] = []
        await update.message.reply_text(
            "🔄 *Suhbat tozalandi!*",
            parse_mode="Markdown",
            reply_markup=main_inline_keyboard()
        )
        return

    # AI javob
    db_save_user(user.id, user.first_name, user.username)
    db_increment_messages(user.id)
    user_data = db_get_user(user.id)
    mode = user_data["mode"] if user_data else "general"

    logger.info(f"{user.first_name} ({user.id}) [{mode}]: {user_message[:50]}")

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    try:
        response = get_groq_response(user.id, user_message, mode)
        if len(response) > 4096:
            for i in range(0, len(response), 4096):
                await update.message.reply_text(response[i:i+4096])
        else:
            await update.message.reply_text(response)
    except Exception as e:
        logger.error(f"Xato ({user.id}): {e}")
        await update.message.reply_text(
            "❌ *Xato yuz berdi!*\n\nIltimos /reset bosing va qayta urining.",
            parse_mode="Markdown"
        )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Xato: {context.error}", exc_info=context.error)


# =============================================
# MAIN
# =============================================

def main():
    if not TELEGRAM_TOKEN:
        logger.error("TELEGRAM_TOKEN topilmadi!")
        return
    if not GROQ_API_KEY:
        logger.error("GROQ_API_KEY topilmadi!")
        return

    init_db()
    logger.info("✅ Database tayyor!")

    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("reset", reset_command))
    app.add_handler(CommandHandler("weather", weather_command))
    app.add_handler(CommandHandler("currency", currency_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("about", about_command))
    app.add_handler(CommandHandler("mode", mode_command))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error_handler)

    logger.info("🚀 Nova AI Bot ishga tushdi!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
