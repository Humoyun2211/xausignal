
import logging
import os
import json
from datetime import datetime
from groq import Groq
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
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
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))  # Admin Telegram ID

MODEL = "llama-3.3-70b-versatile"
MAX_TOKENS = 2048
MAX_HISTORY = 20  # Xotira chegarasi

SYSTEM_PROMPT = """Sen aqlli va do'stona AI yordamchisan.
O'zbek, Rus va Ingliz tillarida muloqot qila olasan.
Foydalanuvchi qaysi tilda yozsa, shu tilda javob ber.
Aniq, foydali va qisqa javoblar ber.
Agar bilmasang, bilmasligingni ayt."""

# =============================================
# LOGGING
# =============================================
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(),
    ]
)
logger = logging.getLogger(__name__)

# =============================================
# MA'LUMOTLAR
# =============================================
client = Groq(api_key=GROQ_API_KEY)
conversation_history: dict[int, list] = {}
user_stats: dict[int, dict] = {}
bot_start_time = datetime.now()


# =============================================
# YORDAMCHI FUNKSIYALAR
# =============================================

def get_user_stats(user_id: int) -> dict:
    if user_id not in user_stats:
        user_stats[user_id] = {
            "messages": 0,
            "joined": datetime.now().strftime("%Y-%m-%d"),
            "name": ""
        }
    return user_stats[user_id]


def update_stats(user_id: int, name: str):
    stats = get_user_stats(user_id)
    stats["messages"] += 1
    stats["name"] = name


def get_groq_response(user_id: int, user_message: str) -> str:
    if user_id not in conversation_history:
        conversation_history[user_id] = []

    conversation_history[user_id].append({
        "role": "user",
        "content": user_message
    })

    # Tarixni cheklash
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


def main_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("🔄 Yangi suhbat", callback_data="reset"),
            InlineKeyboardButton("📊 Statistika", callback_data="stats"),
        ],
        [
            InlineKeyboardButton("ℹ️ Haqida", callback_data="about"),
            InlineKeyboardButton("🌐 Til", callback_data="language"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


# =============================================
# KOMANDALAR
# =============================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    conversation_history[user.id] = []
    get_user_stats(user.id)
    user_stats[user.id]["name"] = user.first_name

    logger.info(f"Yangi foydalanuvchi: {user.first_name} ({user.id})")

    await update.message.reply_text(
        f"👋 Salom, *{user.first_name}*!\n\n"
        f"🤖 Men sun'iy intellekt yordamchiman.\n"
        f"💬 Istalgan savolingizni bering!\n\n"
        f"📌 *Komandalar:*\n"
        f"/start — Boshlash\n"
        f"/reset — Suhbatni tozalash\n"
        f"/help — Yordam\n"
        f"/stats — Statistika\n"
        f"/about — Bot haqida",
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📋 *Yordam:*\n\n"
        "Men har qanday savolga javob bera olaman:\n\n"
        "✅ Tarjima\n"
        "✅ Kod yozish\n"
        "✅ Matematik masalalar\n"
        "✅ Matn yozish\n"
        "✅ Tahlil va maslahat\n\n"
        "💡 *Maslahat:* Savolingizni to'liq va aniq yozing!\n\n"
        "🔄 /reset — Yangi suhbat boshlash\n"
        "📊 /stats — Sizning statistikangiz",
        parse_mode="Markdown"
    )


async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    conversation_history[user.id] = []
    await update.message.reply_text(
        "🔄 *Suhbat tarixi tozalandi!*\n\n"
        "Yangi suhbat boshlashingiz mumkin.",
        parse_mode="Markdown"
    )


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    stats = get_user_stats(user.id)
    history_count = len(conversation_history.get(user.id, []))

    await update.message.reply_text(
        f"📊 *Sizning statistikangiz:*\n\n"
        f"👤 Ism: {user.first_name}\n"
        f"🆔 ID: `{user.id}`\n"
        f"📅 Qo'shilgan: {stats['joined']}\n"
        f"💬 Jami xabarlar: {stats['messages']}\n"
        f"🧠 Xotiradagi xabarlar: {history_count}\n",
        parse_mode="Markdown"
    )


async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uptime = datetime.now() - bot_start_time
    hours = int(uptime.total_seconds() // 3600)
    minutes = int((uptime.total_seconds() % 3600) // 60)

    await update.message.reply_text(
        f"ℹ️ *Bot haqida:*\n\n"
        f"🤖 Model: `{MODEL}`\n"
        f"⚡ Powered by: Groq AI\n"
        f"🕐 Ishlash vaqti: {hours}s {minutes}d\n"
        f"👥 Foydalanuvchilar: {len(user_stats)}\n\n"
        f"📌 Versiya: 2.0.0",
        parse_mode="Markdown"
    )


async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_ID:
        await update.message.reply_text("❌ Ruxsat yo'q!")
        return

    total_messages = sum(s.get("messages", 0) for s in user_stats.values())
    await update.message.reply_text(
        f"👑 *Admin panel:*\n\n"
        f"👥 Jami foydalanuvchilar: {len(user_stats)}\n"
        f"💬 Jami xabarlar: {total_messages}\n"
        f"🤖 Faol suhbatlar: {len(conversation_history)}\n",
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
            "🔄 *Suhbat tozalandi!*\n\nYangi savol bering.",
            parse_mode="Markdown",
            reply_markup=main_keyboard()
        )

    elif query.data == "stats":
        stats = get_user_stats(user.id)
        history_count = len(conversation_history.get(user.id, []))
        await query.edit_message_text(
            f"📊 *Statistika:*\n\n"
            f"💬 Xabarlar: {stats['messages']}\n"
            f"🧠 Xotirada: {history_count} xabar\n"
            f"📅 Qo'shilgan: {stats['joined']}",
            parse_mode="Markdown",
            reply_markup=main_keyboard()
        )

    elif query.data == "about":
        await query.edit_message_text(
            f"ℹ️ *Bot haqida:*\n\n"
            f"🤖 Model: `{MODEL}`\n"
            f"⚡ Groq AI\n"
            f"📌 Versiya: 2.0.0",
            parse_mode="Markdown",
            reply_markup=main_keyboard()
        )

    elif query.data == "language":
        await query.edit_message_text(
            "🌐 *Til:*\n\n"
            "Men quyidagi tillarda gaplasha olaman:\n\n"
            "🇺🇿 O'zbek\n"
            "🇷🇺 Русский\n"
            "🇬🇧 English\n\n"
            "Qaysi tilda yozsangiz, o'sha tilda javob beraman!",
            parse_mode="Markdown",
            reply_markup=main_keyboard()
        )


# =============================================
# XABAR HANDLERI
# =============================================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_message = update.message.text

    logger.info(f"{user.first_name} ({user.id}): {user_message[:50]}")
    update_stats(user.id, user.first_name)

    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action="typing"
    )

    try:
        response = get_groq_response(user.id, user_message)

        # Uzun xabarlarni bo'lib yuborish
        if len(response) > 4096:
            for i in range(0, len(response), 4096):
                await update.message.reply_text(response[i:i+4096])
        else:
            await update.message.reply_text(response)

    except Exception as e:
        logger.error(f"Xato ({user.id}): {e}")
        await update.message.reply_text(
            "❌ Xato yuz berdi. Iltimos qayta urining.\n\n"
            "Agar muammo davom etsa /reset bosing."
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

    # Komanda handlerlari
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("reset", reset_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("about", about_command))
    app.add_handler(CommandHandler("admin", admin_command))

    # Callback va xabar handlerlari
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.add_error_handler(error_handler)

    logger.info("✅ Bot ishga tushdi!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
