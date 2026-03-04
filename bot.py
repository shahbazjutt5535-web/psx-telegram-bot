import os
from flask import Flask
from telegram.ext import ApplicationBuilder, CommandHandler
from tvDatafeed import TvDatafeed, Interval
import pandas as pd
import logging

# ------------------------------
# Logging
# ------------------------------
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# ------------------------------
# Flask Web Service (Render Port)
# ------------------------------
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

# ------------------------------
# Telegram Bot Setup (v20+)
# ------------------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN")

if not BOT_TOKEN:
    logging.error("BOT_TOKEN env variable not set")
    exit(1)

async def start(update, context):
    await update.message.reply_text("Bot is running!")

telegram_app = ApplicationBuilder().token(BOT_TOKEN).build()
telegram_app.add_handler(CommandHandler("start", start))

# ------------------------------
# TradingView Datafeed Setup
# ------------------------------
TV_USERNAME = os.environ.get("TV_USERNAME")
TV_PASSWORD = os.environ.get("TV_PASSWORD")

if TV_USERNAME and TV_PASSWORD:
    try:
        tv = TvDatafeed(TV_USERNAME, TV_PASSWORD)
        # Example: Get last 5 daily bars for AAPL
        data: pd.DataFrame = tv.get_hist("AAPL", "NASDAQ", interval=Interval.in_daily, n_bars=5)
        logging.info(f"TradingView data:\n{data}")
    except Exception as e:
        logging.error(f"TradingView login/data fetch failed: {e}")
else:
    logging.warning("TV_USERNAME or TV_PASSWORD not set. Skipping TradingView login.")

# ------------------------------
# Run Both Flask and Telegram
# ------------------------------
def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    import threading

    # Run Flask in a thread
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()

    # Run Telegram bot (polling)
    telegram_app.run_polling()
