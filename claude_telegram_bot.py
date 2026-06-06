import logging
import os
import anthropic
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
SYSTEM_PROMPT = """Sen yordamchi sun'iy intellektsan. O'zbek tilida javob ber."""

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
conversation_history = {}

def get_claude_response(user_id, user_message):
    if user_id not in conversation_history:
        conversation_history[user_id] = []
    conversation_history[user_id].append({"role": "user", "content": user_message})
    history = conversation_history[user_id][-20:]
    response = client.messages.create(model="claude-sonnet-4-20250514", max_tokens=1024, system=SYSTEM_PROMPT, messages=history)
    msg = response.content[0].text
    conversation_history[user_id].append({"role": "assistant", "content": msg})
    return msg

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conversation_history[update.effective_user.id] = []
    await update.message.reply_text(f"Salom, {update.effective_user.first_name}! Men Claude AI! Savol bering! /reset - yangilash")

async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conversation_history[update.effective_user.id] = []
    await update.message.reply_text("Tozalandi!")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    try:
        response = get_claude_response(update.effective_user.id, update.message.text)
        await update.message.reply_text(response)
    except Exception as e:
        logger.error(f"Xato: {e}")
        await update.message.reply_text("Xato. Qayta urining.")

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reset", reset_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Bot ishga tushdi!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
