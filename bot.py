import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from tvDatafeed import TvDatafeed, Interval
from indicators import calculate_all

TOKEN = os.getenv("8493857966:AAFEnjd_wWh7xi7VdCYdPvDAM5I-8Zr-l-M")
TV_USER = os.getenv("shahbazjutt553")
TV_PASS = os.getenv("shahbazjutt535@")

tv = TvDatafeed(username=TV_USER, password=TV_PASS)

timeframes = {
    "15m": Interval.in_15_minute,
    "30m": Interval.in_30_minute,
    "1h": Interval.in_1_hour,
    "2h": Interval.in_2_hour,
    "4h": Interval.in_4_hour,
    "1d": Interval.in_daily
}

allowed_stocks = ["FFC", "OGDC", "ENGRO", "PPL", "HUBC"]

async def analyze(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if len(context.args) < 2:
        await update.message.reply_text("Usage: /analyze OGDC 15m")
        return

    symbol = context.args[0].upper()
    tf = context.args[1]

    if symbol not in allowed_stocks:
        await update.message.reply_text("Stock not allowed.")
        return

    data = tv.get_hist(
        symbol=symbol,
        exchange="PSX",
        interval=timeframes[tf],
        n_bars=500
    )

    data = calculate_all(data)
    latest = data.iloc[-1]

    message = f"""
📊 {symbol} {tf} Analysis

💰 Price: {latest['close']}
📈 SMA 50: {latest['SMA50']}
📈 EMA 50: {latest['EMA50']}
⚡ RSI 14: {latest['RSI14']}
📉 MACD: {latest['MACD_3_10_16']}
🎯 BB Upper: {latest['BBU_20_2.0']}
📏 ATR: {latest['ATR14']}
"""

    await update.message.reply_text(message)

app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("analyze", analyze))

app.run_polling()
