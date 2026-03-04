import os
import logging
import threading
import pandas as pd
import numpy as np
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from tvDatafeed import TvDatafeed, Interval
import nest_asyncio

# Apply nest_asyncio to allow nested event loops
nest_asyncio.apply()

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
# TradingView (PUBLIC MODE - FIXED FOR RENDER)
# -------------------------
# Use public mode with auto_login=False to prevent interactive prompts
try:
    # Initialize without any parameters - this uses no-login mode
    # The library version from baselsm might handle this differently
    tv = TvDatafeed()
    logging.info("TvDatafeed initialized successfully in no-login mode")
except Exception as e:
    logging.error(f"First init attempt failed: {e}")
    try:
        # Alternative initialization with explicit None values
        tv = TvDatafeed(username=None, password=None)
        logging.info("TvDatafeed initialized with None credentials")
    except Exception as e2:
        logging.error(f"Second init attempt failed: {e2}")
        # Last resort - try with auto_login=False if the fork supports it
        try:
            tv = TvDatafeed(auto_login=False)
            logging.info("TvDatafeed initialized with auto_login=False")
        except Exception as e3:
            logging.error(f"All initialization attempts failed: {e3}")
            raise

# -------------------------
# Indicator Functions
# -------------------------
def calculate_rsi(df, period=14):
    """Calculate RSI indicator"""
    delta = df['close'].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_macd(df):
    """Calculate MACD indicator"""
    ema12 = df['close'].ewm(span=12, adjust=False).mean()
    ema26 = df['close'].ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    return macd, signal

def calculate_stoch_rsi(df, period=14):
    """Calculate Stochastic RSI"""
    rsi = calculate_rsi(df, period)
    min_rsi = rsi.rolling(window=period, min_periods=period).min()
    max_rsi = rsi.rolling(window=period, min_periods=period).max()
    stoch_rsi = 100 * (rsi - min_rsi) / (max_rsi - min_rsi)
    return stoch_rsi

def calculate_atr(df, period=14):
    """Calculate Average True Range"""
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    atr = true_range.rolling(window=period, min_periods=period).mean()
    return atr

def calculate_obv(df):
    """Calculate On-Balance Volume"""
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
# Interval Map (TvDatafeed)
# -------------------------
interval_map = {
    "15m": Interval.in_15_minute,
    "30m": Interval.in_30_minute,
    "1h": Interval.in_1_hour,
    "2h": Interval.in_2_hour,
    "4h": Interval.in_4_hour,
    "12h": Interval.in_12_hour,
}

# List of PSX symbols
stocks = ["FFC", "OGDC", "HUBCO", "ENGRO"]

# -------------------------
# Telegram Command Generator
# -------------------------
def create_psx_command(symbol, interval_key):
    async def command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            # Send typing indicator
            await update.message.chat.send_action(action="typing")
            
            # Fetch data with error handling
            try:
                # Using the correct parameters for the forked tvdatafeed
                df = tv.get_hist(
                    symbol=symbol, 
                    exchange="PSX", 
                    interval=interval_map[interval_key], 
                    n_bars=150
                )
            except Exception as e:
                logging.error(f"Error fetching data from TvDatafeed: {e}")
                await update.message.reply_text(f"Failed to fetch data for {symbol}. Please try again later.")
                return
            
            if df is None or df.empty:
                await update.message.reply_text(f"No data found for {symbol} on PSX exchange.")
                return

            # Ensure we have enough data for calculations
            if len(df) < 30:
                await update.message.reply_text(f"Insufficient data for {symbol}. Need at least 30 bars.")
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
            
            # Check for NaN values
            if pd.isna(last['RSI']) or pd.isna(last['MACD']):
                await update.message.reply_text("Insufficient data for indicator calculations.")
                return

            # Format message with proper number formatting
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
            await update.message.reply_text(f"Error fetching data for {symbol}. Please try again.")

    return command

# -------------------------
# Telegram Bot App
# -------------------------
# Build application
telegram_app = ApplicationBuilder().token(BOT_TOKEN).build()

# Add stock commands
for stock in stocks:
    for interval_key in interval_map.keys():
        cmd_name = f"{stock.lower()}_{interval_key}"
        telegram_app.add_handler(CommandHandler(cmd_name, create_psx_command(stock, interval_key)))
        logging.info(f"Added command: /{cmd_name}")

# /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Create a list of example commands
    example_commands = [
        "/ffc_15m - FFC 15-minute",
        "/ogdc_1h - OGDC 1-hour", 
        "/hubco_4h - HUBCO 4-hour",
        "/engro_12h - ENGRO 12-hour"
    ]
    
    commands_text = "\n".join(example_commands)
    
    await update.message.reply_text(
        "🔥 *PSX Indicator Bot Active*\n\n"
        "*Available intervals:* 15m, 30m, 1h, 2h, 4h, 12h\n"
        "*Stocks:* FFC, OGDC, HUBCO, ENGRO\n\n"
        "*Example commands:*\n"
        f"{commands_text}\n\n"
        "Just type /stock_interval (e.g., /ffc_15m)",
        parse_mode='Markdown'
    )

telegram_app.add_handler(CommandHandler("start", start))

# Add error handler
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.error(f"Update {update} caused error {context.error}")

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
    """Run Flask app in a separate thread"""
    port = int(os.environ.get("PORT", 5000))
    flask_app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

# -------------------------
# Main
# -------------------------
if __name__ == "__main__":
    try:
        # Start Flask in a separate thread
        flask_thread = threading.Thread(target=run_flask, daemon=True)
        flask_thread.start()
        logging.info(f"Flask server started on port {os.environ.get('PORT', 5000)}")
        
        # Run Telegram bot in polling mode
        logging.info("Starting Telegram bot...")
        telegram_app.run_polling()
        
    except KeyboardInterrupt:
        logging.info("Bot stopped by user")
    except Exception as e:
        logging.error(f"Fatal error: {e}", exc_info=True)
        raise
