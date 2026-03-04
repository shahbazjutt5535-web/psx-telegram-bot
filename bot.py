import os
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from indicators import calculate_all
from tvDatafeed import TvDatafeed, Interval
import pandas as pd

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# Telegram Bot Token
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8493857966:AAFEnjd_wWh7xi7VdCYdPvDAM5I-8Zr-l-M")

# TradingView login
TV_USERNAME = os.environ.get("TV_USERNAME", "shahbazjutt553")
TV_PASSWORD = os.environ.get("TV_PASSWORD", "shahbazjutt535@")
tv = TvDatafeed(username=TV_USERNAME, password=TV_PASSWORD)

# Stocks list
STOCKS = ["FFC", "OGDC", "ENGRO", "PPL", "HUBC"]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Welcome to PSX Bot! Use /getdata to fetch all indicators for your stocks."
    )

async def getdata(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = ""
    for stock in STOCKS:
        try:
            df = tv.get_hist(symbol=stock, exchange='PSX', interval=Interval.in_1_day, n_bars=60)
            if df.empty:
                message += f"{stock}: No data\n\n"
                continue

            df = calculate_all(df)
            latest = df.iloc[-1]

            message += f"📊 {stock} Indicators:\n"
            message += f"Close: {latest['close']}\n"
            message += f"SMA10: {latest['SMA_10']}, SMA20: {latest['SMA_20']}, SMA50: {latest['SMA_50']}\n"
            message += f"EMA10: {latest['EMA_10']}, EMA20: {latest['EMA_20']}, EMA50: {latest['EMA_50']}\n"
            message += f"RSI14: {latest['RSI_14']:.2f}\n"
            message += f"MACD: {latest['MACD']:.2f}, Signal: {latest['MACD_SIGNAL']:.2f}, Hist: {latest['MACD_HIST']:.2f}\n"
            message += f"Bollinger Bands: L={latest['BBL']:.2f}, M={latest['BBM']:.2f}, U={latest['BBU']:.2f}, %B={latest['BBP']:.2f}\n"
            message += f"Stochastic: K={latest['STOCH_K']:.2f}, D={latest['STOCH_D']:.2f}\n"
            message += f"ATR14: {latest['ATR_14']:.2f}, OBV: {latest['OBV']:.0f}, ADX14: {latest['ADX_14']:.2f}, CCI20: {latest['CCI_20']:.2f}, MOM10: {latest['MOM_10']:.2f}\n\n"

        except Exception as e:
            logger.error(f"Error fetching data for {stock}: {e}")
            message += f"{stock}: Error fetching data\n\n"

    await update.message.reply_text(message)

def main():
    port = int(os.environ.get("PORT", 5000))
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("getdata", getdata))

    logger.info(f"Bot running on port {port}")
    app.run_polling()

if __name__ == "__main__":
    main()
