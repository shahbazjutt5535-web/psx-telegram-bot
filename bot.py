import os
import logging
from tvDatafeed import TvDatafeed
import chromedriver_autoinstaller
from flask import Flask
from telegram import Update, Bot
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ------------------------
# Environment variables
# ------------------------
TV_USERNAME = os.getenv("TV_USERNAME")
TV_PASSWORD = os.getenv("TV_PASSWORD")
BOT_TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", 5000))

# ------------------------
# Logging
# ------------------------
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)

# ------------------------
# Chromedriver auto install
# ------------------------
chromedriver_autoinstaller.install()

# ------------------------
# Initialize TVDatafeed
# ------------------------
try:
    tv = TvDatafeed(username=TV_USERNAME, password=TV_PASSWORD)
    logger.info("TradingView login successful")
except Exception as e:
    logger.error(f"TradingView login failed: {e}")

# ------------------------
# Import indicators
# ------------------------
from indicators import calculate_all

# ------------------------
# Telegram Bot Handlers
# ------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot is running! Use /signal to get latest indicators.")

async def signal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        # Example: fetch calculated indicators
        result = calculate_all(tv)
        await update.message.reply_text(f"Latest indicators:\n{result}")
    except Exception as e:
        await update.message.reply_text(f"Error fetching indicators: {e}")

# ------------------------
# Start Telegram Bot
# ------------------------
application = ApplicationBuilder().token(BOT_TOKEN).build()
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("signal", signal))

# ------------------------
# Flask Web Server for Render
# ------------------------
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running"

# ------------------------
# Run both Flask and Telegram bot
# ------------------------
if __name__ == "__main__":
    import threading

    # Run Telegram bot in a thread
    def run_bot():
        application.run_polling()

    bot_thread = threading.Thread(target=run_bot)
    bot_thread.start()

    # Run Flask server for Render port detection
    app.run(host="0.0.0.0", port=PORT)
