import logging
import os
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
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

MODEL = "llama-3.3-70b-versatile"
MAX_TOKENS = 2048
MAX_HISTORY = 30

SYSTEM_PROMPT = """Sen XAUUSD Signal botining aqlli AI yordamchisan.
Ismingiz: Nova AI
Quyidagilarni bajara olasan:
- Har qanday savolga javob berish
- Tarjima qilish
- Kod yozish va tushuntirish
- Tahlil va maslahat berish
- Matematik masalalar
- XAU/USD va moliya haqida ma'lumot berish

Qoidalar:
- Foydalanuvchi qaysi tilda yozsa, o'sha tilda javob ber
- Javoblar aniq, qisqa va foydali bo'lsin
- Emoji ishlatib, xabarlarni chiroyli qil
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
# MA'LUMOTLAR
# =============================================
client = Groq(api_key=GROQ_API_KEY)
conversation_history: dict[int, list] = {}
user_stats: dict[int, dict] = {}
user_modes: dict[int, str] = {}  # foydalanuvchi rejimlari
bot_start_time = datetime.now()


# =============================================
# YORDAMCHI FUNKSIYALAR
# =============================================

def get_user_stats(user_id: int) -> dict:
    if user_id not in user_stats:
        user_stats[user_id] = {
            "messages": 0,
            "joined": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "name": "",
            "username": ""
        }
    return user_stats[user_id]


def update_stats(user_id: int, user):
    stats = get_user_stats(user_id)
    stats["messages"] += 1
    stats["name"] = user.first_name
    stats["username"] = f"@{user.username}" if user.username else "Yo'q"


def get_groq_response(user_id: int, user_message: str) -> str:
    if user_id not in conversation_history:
        conversation_history[user_id] = []

    conversation_history[user_id].append({
        "role": "user",
        "content": user_message
    })

    if len(conversation_history[user_id]) > MAX_HISTORY:
        conversation_history[user_id] = conversation_history[user_id][-MAX_HISTORY:]

    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + conversation_history[user_id]

    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        max_tokens=MAX_TOKENS,
        temperature=0.7,
        top_p=0.9,
    )

    assistant_message = response.choices[0].message.content
    conversation_history[user_id].append({
        "role": "assistant",
        "content": assistant_message
    })

    return assistant_message


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
            InlineKeyboardButton("🧠 Rejimlar", callback_data="modes"),
            InlineKeyboardButton("ℹ️ Haqida", callback_data="about"),
        ],
        [
            InlineKeyboardButton("📞 Yordam", callback_data="help"),
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
        [
            InlineKeyboardButton("⬅️ Orqaga", callback_data="back_main"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def reply_keyboard():
    keyboard = [
        [KeyboardButton("🔄 Yangi suhbat"), KeyboardButton("📊 Statistika")],
        [KeyboardButton("🧠 Rejimlar"), KeyboardButton("ℹ️ Haqida")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


# =============================================
# START
# =============================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    conversation_history[user.id] = []
    get_user_stats(user.id)
    user_stats[user.id]["name"] = user.first_name
    user_modes[user.id] = "general"

    logger.info(f"Start: {user.first_name} ({user.id})")

    welcome_text = (
        f"✨ *Xush kelibsiz, {user.first_name}!*\n\n"
        f"🤖 Men *Nova AI* — sizning aqlli yordamchingizman!\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💡 *Nima qila olaman?*\n\n"
        f"• 💬 Har qanday savolga javob\n"
        f"• 🌐 Tarjima (100+ til)\n"
        f"• 💻 Kod yozish va debug\n"
        f"• 📈 Moliya va XAU/USD\n"
        f"• 📝 Matn yozish\n"
        f"• 🧮 Matematik masalalar\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 *Komandalar:*\n"
        f"/start — Boshlash\n"
        f"/reset — Yangi suhbat\n"
        f"/help — Yordam\n"
        f"/stats — Statistika\n"
        f"/about — Haqida\n"
        f"/mode — Rejim tanlash\n\n"
        f"_Savolingizni yozing yoki pastdagi tugmalardan foydalaning_ 👇"
    )

    await update.message.reply_text(
        welcome_text,
        parse_mode="Markdown",
        reply_markup=reply_keyboard()
    )

    await update.message.reply_text(
        "🎛 *Boshqaruv paneli:*",
        parse_mode="Markdown",
        reply_markup=main_inline_keyboard()
    )


# =============================================
# KOMANDALAR
# =============================================

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "📋 *Yordam markazi*\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🔹 *Asosiy komandalar:*\n\n"
        "/start — Botni boshlash\n"
        "/reset — Suhbat tarixini tozalash\n"
        "/help — Ushbu yordam\n"
        "/stats — Sizning statistikangiz\n"
        "/about — Bot haqida\n"
        "/mode — Rejim tanlash\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "💡 *Maslahatlar:*\n\n"
        "• Savolni to'liq va aniq yozing\n"
        "• Tarjima uchun: _'Tarjima qil: [matn]'_\n"
        "• Kod uchun: _'Python da qanday...'_\n"
        "• /reset bilan yangi mavzu boshlang\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🌐 *Qo'llab-quvvatlanadigan tillar:*\n"
        "O'zbek 🇺🇿 | Rus 🇷🇺 | Ingliz 🇬🇧 va boshqalar"
    )
    await update.message.reply_text(
        help_text,
        parse_mode="Markdown",
        reply_markup=main_inline_keyboard()
    )


async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    conversation_history[user.id] = []
    await update.message.reply_text(
        "🔄 *Suhbat tarixi tozalandi!*\n\n"
        "✅ Yangi suhbat boshlashingiz mumkin.\n"
        "_Savolingizni yozing..._",
        parse_mode="Markdown",
        reply_markup=main_inline_keyboard()
    )


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    stats = get_user_stats(user.id)
    history_count = len(conversation_history.get(user.id, []))
    mode = user_modes.get(user.id, "general")
    uptime = datetime.now() - bot_start_time

    mode_names = {
        "general": "💬 Umumiy",
        "finance": "📈 Moliya",
        "coding": "💻 Dasturlash",
        "translate": "🌐 Tarjimon",
        "writer": "✍️ Yozuvchi",
        "teacher": "📚 O'qituvchi"
    }

    stats_text = (
        f"📊 *Sizning statistikangiz*\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 Ism: *{user.first_name}*\n"
        f"🆔 ID: `{user.id}`\n"
        f"📅 Qo'shilgan: {stats['joined']}\n"
        f"💬 Jami xabarlar: *{stats['messages']}*\n"
        f"🧠 Xotirada: {history_count} xabar\n"
        f"🎯 Joriy rejim: {mode_names.get(mode, '💬 Umumiy')}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🤖 *Bot holati:*\n"
        f"⚡ Model: `{MODEL}`\n"
        f"🕐 Ishlash: {int(uptime.total_seconds()//3600)}s {int((uptime.total_seconds()%3600)//60)}d\n"
        f"👥 Foydalanuvchilar: {len(user_stats)}"
    )

    await update.message.reply_text(
        stats_text,
        parse_mode="Markdown",
        reply_markup=main_inline_keyboard()
    )


async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    about_text = (
        "ℹ️ *Nova AI haqida*\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🤖 *Nova AI* — zamonaviy sun'iy intellekt yordamchisi\n\n"
        "⚡ *Texnologiyalar:*\n"
        f"• Model: `{MODEL}`\n"
        "• Platform: Groq AI\n"
        "• Framework: python-telegram-bot\n\n"
        "🎯 *Imkoniyatlar:*\n"
        "• Tez va aniq javoblar\n"
        "• Ko'p tilli muloqot\n"
        "• Suhbat xotirasi\n"
        "• 6 xil rejim\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "📌 Versiya: *3.0.0*\n"
        "🔄 Yangilangan: 2026"
    )
    await update.message.reply_text(
        about_text,
        parse_mode="Markdown",
        reply_markup=main_inline_keyboard()
    )


async def mode_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🧠 *Rejim tanlang:*\n\n"
        "Har bir rejim botni o'sha sohaga moslaydi:",
        parse_mode="Markdown",
        reply_markup=modes_keyboard()
    )


async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_ID:
        await update.message.reply_text("❌ Ruxsat yo'q!")
        return

    total_messages = sum(s.get("messages", 0) for s in user_stats.values())
    uptime = datetime.now() - bot_start_time

    admin_text = (
        f"👑 *Admin Panel*\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 Foydalanuvchilar: *{len(user_stats)}*\n"
        f"💬 Jami xabarlar: *{total_messages}*\n"
        f"🤖 Faol suhbatlar: *{len([h for h in conversation_history.values() if h])}*\n"
        f"🕐 Ishlash vaqti: {int(uptime.total_seconds()//3600)}s\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📋 *So'nggi foydalanuvchilar:*\n"
    )

    for uid, stats in list(user_stats.items())[-5:]:
        admin_text += f"• {stats['name']} — {stats['messages']} xabar\n"

    await update.message.reply_text(
        admin_text,
        parse_mode="Markdown"
    )


# =============================================
# CALLBACK HANDLER
# =============================================

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user

    mode_prompts = {
        "mode_general": ("general", "💬 Umumiy", "Har qanday mavzuda gaplasha olasan."),
        "mode_finance": ("finance", "📈 Moliya", "Moliya, XAU/USD, investitsiya eksperti sifatida javob ber."),
        "mode_coding": ("coding", "💻 Dasturlash", "Dasturlash eksperti sifatida kod yoz va tushuntir."),
        "mode_translate": ("translate", "🌐 Tarjimon", "Professional tarjimon sifatida xizmat ko'rsat."),
        "mode_writer": ("writer", "✍️ Yozuvchi", "Professional yozuvchi sifatida matnlar yoz."),
        "mode_teacher": ("teacher", "📚 O'qituvchi", "Sabr-toqatli o'qituvchi sifatida tushuntir."),
    }

    if query.data == "reset":
        conversation_history[user.id] = []
        await query.edit_message_text(
            "🔄 *Suhbat tozalandi!*\n\n✅ Yangi suhbat boshlashingiz mumkin.",
            parse_mode="Markdown",
            reply_markup=main_inline_keyboard()
        )

    elif query.data == "stats":
        stats = get_user_stats(user.id)
        history_count = len(conversation_history.get(user.id, []))
        await query.edit_message_text(
            f"📊 *Statistika:*\n\n"
            f"👤 {user.first_name}\n"
            f"💬 Xabarlar: *{stats['messages']}*\n"
            f"🧠 Xotirada: {history_count} xabar\n"
            f"📅 {stats['joined']}",
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

    elif query.data in mode_prompts:
        mode_key, mode_name, mode_desc = mode_prompts[query.data]
        user_modes[user.id] = mode_key
        conversation_history[user.id] = []

        global SYSTEM_PROMPT
        base_prompt = f"""Sen Nova AI — aqlli yordamchisan.
Joriy rejim: {mode_name}
{mode_desc}
Foydalanuvchi qaysi tilda yozsa, o'sha tilda javob ber.
Emoji ishlatib, xabarlarni chiroyli qil."""

        await query.edit_message_text(
            f"✅ *{mode_name} rejimi faollashtirildi!*\n\n"
            f"_{mode_desc}_\n\n"
            f"Suhbat tarixi tozalandi. Boshlang! 💪",
            parse_mode="Markdown",
            reply_markup=main_inline_keyboard()
        )

    elif query.data == "about":
        await query.edit_message_text(
            f"ℹ️ *Nova AI haqida:*\n\n"
            f"🤖 Model: `{MODEL}`\n"
            f"⚡ Groq AI\n"
            f"👥 Foydalanuvchilar: {len(user_stats)}\n"
            f"📌 Versiya: 3.0.0",
            parse_mode="Markdown",
            reply_markup=main_inline_keyboard()
        )

    elif query.data == "help":
        await query.edit_message_text(
            "📋 *Yordam:*\n\n"
            "/start — Boshlash\n"
            "/reset — Yangi suhbat\n"
            "/mode — Rejim tanlash\n"
            "/stats — Statistika\n"
            "/about — Haqida\n\n"
            "💡 Savolingizni yozing!",
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

    # Reply klaviatura tugmalari
    if user_message == "🔄 Yangi suhbat":
        conversation_history[user.id] = []
        await update.message.reply_text(
            "🔄 *Suhbat tozalandi!*",
            parse_mode="Markdown",
            reply_markup=main_inline_keyboard()
        )
        return
    elif user_message == "📊 Statistika":
        await stats_command(update, context)
        return
    elif user_message == "🧠 Rejimlar":
        await mode_command(update, context)
        return
    elif user_message == "ℹ️ Haqida":
        await about_command(update, context)
        return

    logger.info(f"{user.first_name} ({user.id}): {user_message[:50]}")
    update_stats(user.id, user)

    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action="typing"
    )

    try:
        response = get_groq_response(user.id, user_message)

        if len(response) > 4096:
            for i in range(0, len(response), 4096):
                await update.message.reply_text(response[i:i+4096])
        else:
            await update.message.reply_text(response)

    except Exception as e:
        logger.error(f"Xato ({user.id}): {e}")
        await update.message.reply_text(
            "❌ *Xato yuz berdi!*\n\n"
            "Iltimos qayta urining yoki /reset bosing.",
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

    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("reset", reset_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("about", about_command))
    app.add_handler(CommandHandler("mode", mode_command))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error_handler)

    logger.info("✅ Nova AI Bot ishga tushdi!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
