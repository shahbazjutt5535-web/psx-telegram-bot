import os
import logging
from telegram import Update, Bot
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
from tvDatafeed import TvDatafeed, Interval
from indicators import calculate_all  # make sure indicators.py has this function

# ---------------------------
# Logging setup
# ---------------------------
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ---------------------------
# Environment variables
# ---------------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
TV_USERNAME = os.environ.get("TV_USERNAME")
TV_PASSWORD = os.environ.get("TV_PASSWORD")
PORT = int(os.environ.get("PORT", 5000))  # Default to 5000 if not set

if not BOT_TOKEN:
    logger.error("BOT_TOKEN is not set. Exiting.")
    exit(1)

# ---------------------------
# Initialize TradingView connection
# ---------------------------
try:
    tv = TvDatafeed(username=TV_USERNAME, password=TV_PASSWORD)
    logger.info("Connected to TradingView successfully.")
except EOFError:
    logger.error("Cannot do interactive login. Make sure TV_USERNAME and TV_PASSWORD are set as env variables.")
    exit(1)
except Exception as e:
    logger.error(f"TradingView connection failed: {e}")
    exit(1)

# ---------------------------
# Telegram bot command handlers
# ---------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Welcome to PSX Trading Bot! Send /signal to get latest signals.")

async def signal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        # Calculate all indicators from indicators.py
        signals = calculate_all(tv)
        await update.message.reply_text(signals)
    except Exception as e:
        logger.error(f"Error generating signals: {e}")
        await update.message.reply_text("Failed to fetch signals. Try again later.")

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"You said: {update.message.text}")

# ---------------------------
# Run bot
# ---------------------------
async def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("signal", signal))

    # Echo handler for testing
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), echo))

    # Start bot with webhook for Render
    webhook_url = f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME')}/"  # optional
    logger.info(f"Starting bot on port {PORT}...")
    await app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        webhook_url=webhook_url if webhook_url else None
    )

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
