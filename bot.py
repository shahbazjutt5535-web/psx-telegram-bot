import os
import logging
import threading
import pandas as pd
import numpy as np
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import nest_asyncio
import asyncio
import time

# Apply nest_asyncio to allow nested event loops
nest_asyncio.apply()

# -------------------------
# MONKEY PATCH: Replace input() to bypass interactive prompt in tvDatafeed
# -------------------------
import builtins
original_input = builtins.input
builtins.input = lambda prompt='': 'y'

from tvDatafeed import TvDatafeed, Interval

builtins.input = original_input

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
    raise ValueError("BOT_TOKEN environment variable not set")

# -------------------------
# TradingView Initialization
# -------------------------
try:
    tv = TvDatafeed()
    logging.info("TvDatafeed initialized successfully in no-login mode")
except Exception as e:
    logging.error(f"TvDatafeed initialization failed: {e}")
    raise

# -------------------------
# Interval Map
# -------------------------
interval_map = {
    "15m": Interval.in_15_minute,
    "30m": Interval.in_30_minute,
    "1h": Interval.in_1_hour,
    "2h": Interval.in_2_hour,
    "4h": Interval.in_4_hour,
    "12h": Interval.in_12_hour,
}

stocks = ["FFC", "OGDC", "HUBCO", "ENGRO"]

# -------------------------
# Indicator Functions
# -------------------------
def calculate_rsi(df, period=14):
    delta = df['close'].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_macd(df):
    ema12 = df['close'].ewm(span=12, adjust=False).mean()
    ema26 = df['close'].ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    return macd, signal

def calculate_stoch_rsi(df, period=14):
    rsi = calculate_rsi(df, period)
    min_rsi = rsi.rolling(window=period, min_periods=period).min()
    max_rsi = rsi.rolling(window=period, min_periods=period).max()
    stoch_rsi = 100 * (rsi - min_rsi) / (max_rsi - min_rsi)
    return stoch_rsi

def calculate_atr(df, period=14):
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    atr = true_range.rolling(window=period, min_periods=period).mean()
    return atr

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
# Telegram Command Generator - FIXED VERSION
# -------------------------
def create_psx_command(symbol, interval_key):
    async def command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Send immediate acknowledgment
        await update.message.reply_text(f"⏳ Fetching data for {symbol} ({interval_key})...")
        
        try:
            # Run data fetching in a thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            
            # Fetch data with timeout
            try:
                df = await loop.run_in_executor(
                    None, 
                    lambda: tv.get_hist(
                        symbol=symbol, 
                        exchange="PSX", 
                        interval=interval_map[interval_key], 
                        n_bars=150
                    )
                )
            except Exception as e:
                logging.error(f"Error fetching data from TvDatafeed: {e}")
                await update.message.reply_text(f"❌ Failed to fetch data for {symbol}. TradingView may be limiting access.")
                return
            
            if df is None or df.empty:
                await update.message.reply_text(f"❌ No data found for {symbol} on PSX exchange. The symbol might be incorrect or delisted.")
                return

            if len(df) < 30:
                await update.message.reply_text(f"⚠️ Insufficient data for {symbol}. Need at least 30 bars.")
                return

            # Calculate indicators
            df['RSI'] = calculate_rsi(df)
            df['MACD'], df['MACD_SIGNAL'] = calculate_macd(df)
            df['STOCH_RSI'] = calculate_stoch_rsi(df)
            df['ATR'] = calculate_atr(df)
            df['OBV'] = calculate_obv(df)
            df['SMA20'] = df['close'].rolling(window=20, min_periods=20).mean()
            df['EMA20'] = df['close'].ewm(span=20, adjust=False).mean()

            last = df.iloc[-1]
            
            if pd.isna(last['RSI']) or pd.isna(last['MACD']):
                await update.message.reply_text("⚠️ Insufficient data for indicator calculations.")
                return

            # Format message
            message = (
                f"📊 *{symbol} ({interval_key})*\n\n"
                f"💰 *Price Data*\n"
                f"Close: `{last['close']:.2f}`\n"
                f"Volume: `{last['volume']:,.0f}`\n\n"
                f"📈 *Indicators*\n"
                f"RSI: `{last['RSI']:.2f}`\n"
                f"MACD: `{last['MACD']:.2f}`\n"
                f"MACD Signal: `{last['MACD_SIGNAL']:.2f}`\n"
                f"Stoch RSI: `{last['STOCH_RSI']:.2f}`\n"
                f"ATR: `{last['ATR']:.2f}`\n"
                f"SMA20: `{last['SMA20']:.2f}`\n"
                f"EMA20: `{last['EMA20']:.2f}`\n"
                f"OBV: `{last['OBV']:,.0f}`"
            )

            await update.message.reply_text(message, parse_mode='Markdown')

        except Exception as e:
            logging.error(f"Error processing {symbol} {interval_key}: {e}", exc_info=True)
            await update.message.reply_text(f"❌ Error fetching data for {symbol}. Please try again later.")

    return command

# -------------------------
# Telegram Bot App - FIXED INITIALIZATION
# -------------------------
# Build application with custom settings
telegram_app = ApplicationBuilder()\
    .token(BOT_TOKEN)\
    .concurrent_updates(True)\
    .pool_timeout(30)\
    .connect_timeout(30)\
    .read_timeout(30)\
    .write_timeout(30)\
    .build()

# Add stock commands
for stock in stocks:
    for interval_key in interval_map.keys():
        cmd_name = f"{stock.lower()}_{interval_key}"
        telegram_app.add_handler(CommandHandler(cmd_name, create_psx_command(stock, interval_key)))
        logging.info(f"Added command: /{cmd_name}")

# /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    commands_text = "\n".join([f"/{stock.lower()}_{interval}" for stock in stocks[:1] for interval in ["15m", "1h", "4h"]])
    
    await update.message.reply_text(
        "🔥 *PSX Indicator Bot Active*\n\n"
        "*Available intervals:* 15m, 30m, 1h, 2h, 4h, 12h\n"
        "*Stocks:* FFC, OGDC, HUBCO, ENGRO\n\n"
        "*Example commands:*\n"
        f"`/ffc_15m` - FFC 15-minute\n"
        f"`/ogdc_1h` - OGDC 1-hour\n"
        f"`/hubco_4h` - HUBCO 4-hour\n\n"
        "⏳ *Note:* First request may take 10-15 seconds",
        parse_mode='Markdown'
    )

telegram_app.add_handler(CommandHandler("start", start))

# Add error handler
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.error(f"Update {update} caused error {context.error}")
    if update and update.message:
        await update.message.reply_text("⚠️ An error occurred. Please try again.")

telegram_app.add_error_handler(error_handler)

# -------------------------
# Flask App for Render
# -------------------------
flask_app = Flask(__name__)

@flask_app.route("/")
def home():
    return "✅ PSX Indicator Bot is Running!"

@flask_app.route("/health")
def health():
    return {"status": "healthy", "bot": "running"}, 200

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    flask_app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

# -------------------------
# Main
# -------------------------
if __name__ == "__main__":
    try:
        # Start Flask
        flask_thread = threading.Thread(target=run_flask, daemon=True)
        flask_thread.start()
        logging.info(f"Flask server started on port {os.environ.get('PORT', 5000)}")
        
        # Small delay to ensure Flask starts
        time.sleep(2)
        
        # Run Telegram bot
        logging.info("Starting Telegram bot...")
        telegram_app.run_polling(drop_pending_updates=True)
        
    except KeyboardInterrupt:
        logging.info("Bot stopped by user")
    except Exception as e:
        logging.error(f"Fatal error: {e}", exc_info=True)
        raise
