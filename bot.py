import os
import logging
import threading
import pandas as pd
import numpy as np
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from tvDatafeed import TvDatafeed, Interval

# -------------------------
# Logging
# -------------------------
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# -------------------------
# Environment
# -------------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not set")

# -------------------------
# TradingView (PUBLIC MODE)
# -------------------------
tv = TvDatafeed()   # ← No username/password (Render safe)

# -------------------------
# Indicator Functions
# -------------------------

def calculate_rsi(df, period=14):
    delta = df['close'].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def calculate_macd(df):
    ema12 = df['close'].ewm(span=12, adjust=False).mean()
    ema26 = df['close'].ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    return macd, signal

def calculate_stoch_rsi(df, period=14):
    rsi = calculate_rsi(df, period)
    min_rsi = rsi.rolling(period).min()
    max_rsi = rsi.rolling(period).max()
    return 100 * (rsi - min_rsi) / (max_rsi - min_rsi)

def calculate_atr(df, period=14):
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    return true_range.rolling(period).mean()

def calculate_obv(df):
    obv = [0]
    for i in range(1, len(df)):
        if df['close'].iloc[i] > df['close'].iloc[i-1]:
            obv.append(obv[-1] + df['volume'].iloc[i])
        elif df['close'].iloc[i] < df['close'].iloc[i-1]:
            obv.append(obv[-1] - df['volume'].iloc[i])
        else:
            obv.append(obv[-1])
    return pd.Series(obv, index=df.index)

# -------------------------
# Interval Map
# -------------------------
interval_map = {
    "15m": Interval.in_15_minute,
    "30m": Interval.in_30_minute,
    "1h": Interval.in_hour,
    "2h": Interval.in_2_hour,
    "4h": Interval.in_4_hour,
    "12h": Interval.in_12_hour,
}

stocks = ["FFC", "OGDC", "HUBCO", "ENGRO"]

# -------------------------
# Command Generator
# -------------------------
def create_psx_command(symbol, interval_key):

    async def command(update: Update, context: ContextTypes.DEFAULT_TYPE):

        try:
            df = tv.get_hist(symbol, "PSX", interval=interval_map[interval_key], n_bars=150)

            if df is None or df.empty:
                await update.message.reply_text("No data found.")
                return

            df['RSI'] = calculate_rsi(df)
            df['MACD'], df['MACD_SIGNAL'] = calculate_macd(df)
            df['STOCH_RSI'] = calculate_stoch_rsi(df)
            df['ATR'] = calculate_atr(df)
            df['OBV'] = calculate_obv(df)
            df['SMA20'] = df['close'].rolling(20).mean()
            df['EMA20'] = df['close'].ewm(span=20, adjust=False).mean()

            last = df.iloc[-1]

            message = (
                f"📊 {symbol} ({interval_key})\n\n"
                f"Close: {round(last['close'],2)}\n"
                f"Volume: {round(last['volume'],2)}\n\n"
                f"RSI: {round(last['RSI'],2)}\n"
                f"MACD: {round(last['MACD'],2)}\n"
                f"MACD Signal: {round(last['MACD_SIGNAL'],2)}\n"
                f"Stoch RSI: {round(last['STOCH_RSI'],2)}\n"
                f"ATR: {round(last['ATR'],2)}\n"
                f"SMA20: {round(last['SMA20'],2)}\n"
                f"EMA20: {round(last['EMA20'],2)}\n"
                f"OBV: {round(last['OBV'],2)}"
            )

            await update.message.reply_text(message)

        except Exception as e:
            logging.error(e)
            await update.message.reply_text("Error fetching data.")

    return command

# -------------------------
# Telegram App
# -------------------------
telegram_app = ApplicationBuilder().token(BOT_TOKEN).build()

for stock in stocks:
    for interval_key in interval_map.keys():
        cmd = f"{stock.lower()}_{interval_key}"
        telegram_app.add_handler(
            CommandHandler(cmd, create_psx_command(stock, interval_key))
        )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔥 PSX Indicator Bot Active\n\n"
        "Example:\n"
        "/ffc_15m\n"
        "/ogdc_1h\n"
        "/hubco_4h\n"
        "/engro_12h"
    )

telegram_app.add_handler(CommandHandler("start", start))

# -------------------------
# Flask (Render Required)
# -------------------------
flask_app = Flask(__name__)

@flask_app.route("/")
def home():
    return "PSX Indicator Bot Running"

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    flask_app.run(host="0.0.0.0", port=port)

# -------------------------
# Main
# -------------------------
if __name__ == "__main__":
    threading.Thread(target=run_flask).start()
    telegram_app.run_polling()
