import os
import pandas as pd
from tvDatafeed import TvDatafeed, Interval
from telegram import Bot, Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from indicators import calculate_indicators

# ==================== CONFIG ====================
TV_USERNAME = os.getenv("shahbazjutt553")  # TradingView login
TV_PASSWORD = os.getenv("shahbazjutt535@")  # TradingView password
TELEGRAM_TOKEN = os.getenv("8493857966:AAFEnjd_wWh7xi7VdCYdPvDAM5I-8Zr-l-M")  # Bot token
STOCKS = ["FFC", "OGDC", "ENGRO", "PPL", "HUBC"]
TIMEFRAMES = {
    "15m": Interval.in_15_minute,
    "30m": Interval.in_30_minute,
    "1h": Interval.in_1_hour,
    "2h": Interval.in_2_hour,
    "4h": Interval.in_4_hour,
    "12h": Interval.in_12_hour,
    "1d": Interval.in_daily
}
# =================================================

tv = TvDatafeed(TV_USERNAME, TV_PASSWORD)
bot = Bot(token=TELEGRAM_TOKEN)

async def stock_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = ""
    for symbol in STOCKS:
        for tf_label, tf in TIMEFRAMES.items():
            df = tv.get_hist(symbol=symbol, exchange="PSX", interval=tf, n_bars=200)
            if df.empty:
                continue
            df = calculate_indicators(df)
            latest = df.iloc[-1]
            msg += f"📊 {symbol} {tf_label} Analysis\n"
            msg += f"💰 Price: {latest['close']:.2f}\n"
            msg += f"📈 SMA50: {latest['SMA50']:.2f}\n"
            msg += f"📈 EMA50: {latest['EMA50']:.2f}\n"
            msg += f"⚡ RSI14: {latest['RSI14']:.2f}\n"
            msg += f"📉 MACD: {latest['MACD']:.2f}, Signal: {latest['MACD_SIGNAL']:.2f}, Hist: {latest['MACD_HIST']:.2f}\n"
            msg += f"🎯 BB Upper: {latest['BB_UPPER']:.2f}, Middle: {latest['BB_MIDDLE']:.2f}, Lower: {latest['BB_LOWER']:.2f}\n\n"

    await update.message.reply_text(msg[:4000])  # Telegram limit

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📊 PSX Stock Bot is ready! Use /stocks to get analysis.")

app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("stocks", stock_handler))

app.run_polling()
