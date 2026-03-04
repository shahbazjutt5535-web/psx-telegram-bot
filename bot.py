import os
import logging
from tvDatafeed import TvDatafeed, Interval
from indicators import calculate_all  # your indicators module
from telegram import Bot, Update
from telegram.ext import Updater, CommandHandler, CallbackContext
from flask import Flask

# ----------------------------
# Logging
# ----------------------------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ----------------------------
# Environment variables
# ----------------------------
TV_USERNAME = os.environ.get("TV_USERNAME")
TV_PASSWORD = os.environ.get("TV_PASSWORD")
BOT_TOKEN   = os.environ.get("BOT_TOKEN")
PORT        = int(os.environ.get("PORT", 5000))

if not TV_USERNAME or not TV_PASSWORD or not BOT_TOKEN:
    logger.error("TV_USERNAME, TV_PASSWORD, or BOT_TOKEN not set in env variables.")
    raise SystemExit("Missing credentials")

# ----------------------------
# TradingView login (non-interactive)
# ----------------------------
try:
    tv = TvDatafeed(username=TV_USERNAME, password=TV_PASSWORD, chromedriver_path=None)
except Exception as e:
    logger.error(f"TradingView login failed: {e}")
    raise SystemExit("Cannot login to TradingView non-interactively.")

# ----------------------------
# Telegram Bot setup
# ----------------------------
bot = Bot(token=BOT_TOKEN)
updater = Updater(token=BOT_TOKEN, use_context=True)
dispatcher = updater.dispatcher

def start(update: Update, context: CallbackContext):
    update.message.reply_text("Bot is running ✅")

def indicators_command(update: Update, context: CallbackContext):
    try:
        results = calculate_all(tv)  # your indicator calculations
        update.message.reply_text(str(results))
    except Exception as e:
        logger.error(f"Error in indicator calculation: {e}")
        update.message.reply_text("Error calculating indicators")

dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CommandHandler("indicators", indicators_command))

# Start polling in background
updater.start_polling()

# ----------------------------
# Flask server for Render
# ----------------------------
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running ✅"

if __name__ == "__main__":
    # Keep Flask running so Render doesn't kill the service
    app.run(host="0.0.0.0", port=PORT)
