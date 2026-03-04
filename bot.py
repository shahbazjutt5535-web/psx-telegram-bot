import os
from flask import Flask
from tvDatafeed import TvDatafeed, Interval
from indicators import *  # your indicators.py file
from telegram import Bot
from telegram.ext import Updater, CommandHandler
import logging

# ------------------- SETTINGS -------------------

# TradingView credentials from environment variables
TV_USERNAME = os.environ.get("TV_USERNAME", "shahbazjutt553")
TV_PASSWORD = os.environ.get("TV_PASSWORD", "shahbazjutt535@")

# Telegram Bot API
BOT_TOKEN = os.environ.get("BOT_API", "8493857966:AAFEnjd_wWh7xi7VdCYdPvDAM5I-8Zr-l-M")

# Port detection for Render
PORT = int(os.environ.get("PORT", 5000))

# ------------------- LOGGING -------------------
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ------------------- TRADINGVIEW SETUP -------------------
# Use non-interactive login
try:
    tv = TvDatafeed(username=TV_USERNAME, password=TV_PASSWORD)
except Exception as e:
    logger.error("TradingView login failed: %s", e)
    tv = None

# ------------------- TELEGRAM BOT SETUP -------------------
bot = Bot(token=BOT_TOKEN)
updater = Updater(token=BOT_TOKEN, use_context=True)
dispatcher = updater.dispatcher

def start(update, context):
    update.message.reply_text("Hello! Bot is running on Render 🚀")

start_handler = CommandHandler('start', start)
dispatcher.add_handler(start_handler)

# ------------------- FLASK APP (for open port) -------------------
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running on Render ✅"

# ------------------- BACKGROUND JOBS / SIGNALS -------------------
# Example function using indicators
def check_signals():
    if tv:
        # Replace with your logic
        data = tv.get_hist(symbol='AAPL', exchange='NASDAQ', interval=Interval.in_daily, n_bars=10)
        logger.info("Fetched AAPL data: %s", data.head())

# ------------------- RUN BOT -------------------
if __name__ == "__main__":
    import threading

    # Start Telegram bot in a thread
    bot_thread = threading.Thread(target=updater.start_polling, daemon=True)
    bot_thread.start()
    logger.info("Telegram bot started")

    # Optional: background indicator check thread
    bg_thread = threading.Thread(target=check_signals, daemon=True)
    bg_thread.start()

    # Start Flask web server (so Render detects the open port)
    logger.info("Starting Flask server on port %d", PORT)
    app.run(host="0.0.0.0", port=PORT)
