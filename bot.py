import os
from flask import Flask
from tvDatafeed import TvDatafeed
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import logging

# ----------------------------
# Logging
# ----------------------------
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# ----------------------------
# Environment Variables
# ----------------------------
TV_USERNAME = os.getenv("TV_USERNAME")
TV_PASSWORD = os.getenv("TV_PASSWORD")
BOT_TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", 5000))  # default 5000 if not set

if not TV_USERNAME or not TV_PASSWORD or not BOT_TOKEN:
    logging.error("Environment variables TV_USERNAME, TV_PASSWORD, BOT_TOKEN must be set")
    exit(1)

# ----------------------------
# TradingView login (non-interactive)
# ----------------------------
try:
    tv = TvDatafeed(username=TV_USERNAME, password=TV_PASSWORD, chromedriver_path=None)
    logging.info("TradingView login successful")
except Exception as e:
    logging.error(f"TradingView login failed: {e}")
    exit(1)

# ----------------------------
# Flask app for Render
# ----------------------------
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running!"

# ----------------------------
# Telegram Bot
# ----------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot is running!")

# Initialize bot
application = ApplicationBuilder().token(BOT_TOKEN).build()
application.add_handler(CommandHandler("start", start))

# ----------------------------
# Run both Flask and Telegram
# ----------------------------
if __name__ == "__main__":
    import threading

    # Run Flask in a separate thread
    def run_flask():
        app.run(host="0.0.0.0", port=PORT)

    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()

    # Run Telegram bot
    logging.info("Starting Telegram bot...")
    application.run_polling()
