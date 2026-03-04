"""
PSX Stock Indicator Telegram Bot
FIXED VERSION - Responds to all commands
"""

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
from datetime import datetime
import functools

# Apply nest_asyncio for Render deployment
nest_asyncio.apply()

# -------------------------
# FIX: Patch input() before importing tvDatafeed
# -------------------------
import builtins
original_input = builtins.input
builtins.input = lambda prompt='': 'y'

# Import tvDatafeed
try:
    from tvDatafeed import TvDatafeed, Interval
    print("✅ tvDatafeed imported successfully")
except Exception as e:
    print(f"❌ Failed to import tvDatafeed: {e}")
    raise

# Restore input
builtins.input = original_input

# -------------------------
# Logging Setup
# -------------------------
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# -------------------------
# Environment Variables
# -------------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN environment variable not set")

# -------------------------
# TradingView Initialization
# -------------------------
def init_tvdatafeed():
    """Initialize TvDatafeed with multiple fallback methods"""
    
    # Method 1: Simple initialization
    try:
        tv = TvDatafeed()
        logger.info("✅ TvDatafeed initialized successfully")
        return tv
    except Exception as e:
        logger.warning(f"Method 1 failed: {e}")
    
    # Method 2: With auto_login=False
    try:
        tv = TvDatafeed(auto_login=False)
        logger.info("✅ TvDatafeed initialized with auto_login=False")
        return tv
    except Exception as e:
        logger.warning(f"Method 2 failed: {e}")
    
    # Method 3: Explicit None credentials
    try:
        tv = TvDatafeed(username=None, password=None)
        logger.info("✅ TvDatafeed initialized with None credentials")
        return tv
    except Exception as e:
        logger.warning(f"Method 3 failed: {e}")
    
    # If all methods fail
    raise Exception("❌ All TvDatafeed initialization methods failed")

# Initialize TvDatafeed
try:
    tv = init_tvdatafeed()
except Exception as e:
    logger.error(f"Fatal: Could not initialize TvDatafeed: {e}")
    raise

# -------------------------
# Interval Mapping
# -------------------------
interval_map = {
    "15m": Interval.in_15_minute,
    "30m": Interval.in_30_minute,
    "1h": Interval.in_1_hour,
    "2h": Interval.in_2_hour,
    "4h": Interval.in_4_hour,
    "1d": Interval.in_daily,
    "1w": Interval.in_weekly,
}

# PSX Stocks
stocks = ["FFC", "OGDC", "HUBCO", "ENGRO", "POL", "LUCK", "SEARL"]

# -------------------------
# Technical Indicators
# -------------------------
def calculate_rsi(df, period=14):
    """Relative Strength Index"""
    delta = df['close'].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_macd(df):
    """MACD"""
    ema12 = df['close'].ewm(span=12, adjust=False).mean()
    ema26 = df['close'].ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    histogram = macd - signal
    return macd, signal, histogram

def calculate_stoch_rsi(df, period=14):
    """Stochastic RSI"""
    rsi = calculate_rsi(df, period)
    min_rsi = rsi.rolling(window=period, min_periods=period).min()
    max_rsi = rsi.rolling(window=period, min_periods=period).max()
    stoch_rsi = 100 * (rsi - min_rsi) / (max_rsi - min_rsi)
    return stoch_rsi

def calculate_atr(df, period=14):
    """Average True Range"""
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    atr = true_range.rolling(window=period, min_periods=period).mean()
    return atr

def calculate_obv(df):
    """On-Balance Volume"""
    obv = [0]
    for i in range(1, len(df)):
        if df['close'].iloc[i] > df['close'].iloc[i-1]:
            obv.append(obv[-1] + df['volume'].iloc[i])
        elif df['close'].iloc[i] < df['close'].iloc[i-1]:
            obv.append(obv[-1] - df['volume'].iloc[i])
        else:
            obv.append(obv[-1])
    return pd.Series(obv, index=df.index)

def calculate_bollinger_bands(df, period=20):
    """Bollinger Bands"""
    sma = df['close'].rolling(window=period, min_periods=period).mean()
    std = df['close'].rolling(window=period, min_periods=period).std()
    upper = sma + (std * 2)
    lower = sma - (std * 2)
    return upper, sma, lower

def calculate_moving_averages(df):
    """Moving Averages"""
    sma20 = df['close'].rolling(window=20, min_periods=20).mean()
    sma50 = df['close'].rolling(window=50, min_periods=50).mean()
    ema20 = df['close'].ewm(span=20, adjust=False).mean()
    return sma20, sma50, ema20

# -------------------------
# FIXED: Command Generator with Timeout
# -------------------------
def create_stock_command(symbol, interval_key):
    """Create a command handler with timeout protection"""
    
    async def command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Send immediate acknowledgment
        await update.message.reply_text(f"⏳ Fetching {symbol} ({interval_key}) data... This may take 10-15 seconds.")
        
        try:
            # Run in thread pool with timeout
            loop = asyncio.get_event_loop()
            
            # Create a timeout task
            try:
                # Use asyncio.wait_for to set a timeout
                df = await asyncio.wait_for(
                    loop.run_in_executor(
                        None,
                        lambda: tv.get_hist(
                            symbol=symbol,
                            exchange="PSX",
                            interval=interval_map[interval_key],
                            n_bars=200
                        )
                    ),
                    timeout=25.0  # 25 seconds timeout
                )
            except asyncio.TimeoutError:
                logger.error(f"Timeout fetching {symbol} {interval_key}")
                await update.message.reply_text(f"❌ Request timed out. TradingView is taking too long to respond. Please try again.")
                return
            
            # Validate data
            if df is None or df.empty:
                await update.message.reply_text(f"❌ No data found for {symbol} on PSX exchange.")
                return
            
            if len(df) < 50:
                await update.message.reply_text(f"⚠️ Insufficient data for {symbol}. Only {len(df)} bars available.")
                return
            
            # Calculate indicators
            df['RSI'] = calculate_rsi(df)
            df['MACD'], df['MACD_SIGNAL'], df['MACD_HIST'] = calculate_macd(df)
            df['STOCH_RSI'] = calculate_stoch_rsi(df)
            df['ATR'] = calculate_atr(df)
            df['OBV'] = calculate_obv(df)
            df['BB_UPPER'], df['BB_MIDDLE'], df['BB_LOWER'] = calculate_bollinger_bands(df)
            df['SMA20'], df['SMA50'], df['EMA20'] = calculate_moving_averages(df)
            
            # Get latest values
            last = df.iloc[-1]
            
            # Determine signals
            rsi_val = last['RSI']
            if pd.isna(rsi_val):
                rsi_signal = "N/A"
            elif rsi_val > 70:
                rsi_signal = "🟢 Overbought"
            elif rsi_val < 30:
                rsi_signal = "🔴 Oversold"
            else:
                rsi_signal = "⚪ Neutral"
            
            macd_signal = "🟢 Bullish" if last['MACD'] > last['MACD_SIGNAL'] else "🔴 Bearish"
            
            # Format message
            message = (
                f"📊 *{symbol} - PSX ({interval_key})*\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n\n"
                
                f"💰 *PRICE*\n"
                f"Close: `{last['close']:.2f}`\n"
                f"High: `{last['high']:.2f}`\n"
                f"Low: `{last['low']:.2f}`\n"
                f"Volume: `{last['volume']:,.0f}`\n\n"
                
                f"📈 *MOMENTUM*\n"
                f"RSI: `{last['RSI']:.1f}` {rsi_signal}\n"
                f"Stoch RSI: `{last['STOCH_RSI']:.1f}`\n"
                f"MACD: `{last['MACD']:.2f}`\n"
                f"Signal: `{last['MACD_SIGNAL']:.2f}`\n"
                f"MACD Trend: {macd_signal}\n\n"
                
                f"📊 *TREND*\n"
                f"SMA20: `{last['SMA20']:.2f}`\n"
                f"SMA50: `{last['SMA50']:.2f}`\n"
                f"EMA20: `{last['EMA20']:.2f}`\n\n"
                
                f"📉 *VOLATILITY*\n"
                f"ATR: `{last['ATR']:.2f}`\n"
                f"BB Upper: `{last['BB_UPPER']:.2f}`\n"
                f"BB Lower: `{last['BB_LOWER']:.2f}`\n\n"
                
                f"📦 *VOLUME*\n"
                f"OBV: `{last['OBV']:,.0f}`\n\n"
                
                f"⏱️ {df.index[-1].strftime('%Y-%m-%d %H:%M')}"
            )
            
            await update.message.reply_text(message, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error: {e}", exc_info=True)
            await update.message.reply_text(f"❌ Error fetching {symbol}. Please try again later.")
    
    return command

# -------------------------
# FIXED: Add Test Command to Verify Bot Works
# -------------------------
async def test_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Simple test command to verify bot is responding"""
    await update.message.reply_text("✅ Bot is working! If you see this, the bot is responding properly.")

async def ping_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ping command to check latency"""
    start_time = time.time()
    msg = await update.message.reply_text("🏓 Pong!")
    end_time = time.time()
    latency = round((end_time - start_time) * 1000, 2)
    await msg.edit_text(f"🏓 Pong! Response time: {latency}ms")

# -------------------------
# Build Telegram Application
# -------------------------
telegram_app = ApplicationBuilder()\
    .token(BOT_TOKEN)\
    .concurrent_updates(True)\
    .build()

# Add test commands FIRST (so they're easy to test)
telegram_app.add_handler(CommandHandler("test", test_command))
telegram_app.add_handler(CommandHandler("ping", ping_command))
logger.info(f"✅ Added test commands: /test, /ping")

# Add all stock commands
for stock in stocks:
    for interval_key in interval_map.keys():
        cmd_name = f"{stock.lower()}_{interval_key}"
        telegram_app.add_handler(CommandHandler(cmd_name, create_stock_command(stock, interval_key)))
        logger.info(f"✅ Added command: /{cmd_name}")

# -------------------------
# Start Command
# -------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    help_text = (
        "🔥 *PSX Stock Indicator Bot*\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        "*TEST COMMANDS (Verify bot works):*\n"
        "`/test` - Check if bot is responding\n"
        "`/ping` - Check response time\n\n"
        
        "*Available Stocks:*\n"
        "FFC, OGDC, HUBCO, ENGRO, POL, LUCK, SEARL\n\n"
        
        "*Timeframes:* 15m, 30m, 1h, 2h, 4h, 1d, 1w\n\n"
        
        "*Example Commands:*\n"
        "`/ffc_15m` - FFC 15min\n"
        "`/ogdc_1h` - OGDC 1hour\n"
        "`/hubco_4h` - HUBCO 4hour\n"
        "`/engro_1d` - ENGRO Daily\n\n"
        
        "*Indicators:*\n"
        "RSI • MACD • Stoch RSI • ATR • OBV • BB • SMA • EMA\n\n"
        
        "⏳ *Note:* First request may take 10-15 seconds"
    )
    
    await update.message.reply_text(help_text, parse_mode='Markdown')

telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(CommandHandler("help", start))

# -------------------------
# Error Handler
# -------------------------
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Error: {context.error}")
    if update and update.effective_message:
        await update.effective_message.reply_text("⚠️ An error occurred. Please try again.")

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
# Main Execution
# -------------------------
if __name__ == "__main__":
    try:
        # Start Flask
        flask_thread = threading.Thread(target=run_flask, daemon=True)
        flask_thread.start()
        logger.info(f"✅ Flask server started on port {os.environ.get('PORT', 5000)}")
        
        # Small delay
        time.sleep(2)
        
        # Start Telegram bot
        logger.info("🚀 Starting Telegram bot...")
        telegram_app.run_polling(drop_pending_updates=True)
        
    except KeyboardInterrupt:
        logger.info("👋 Bot stopped")
    except Exception as e:
        logger.error(f"💥 Fatal error: {e}", exc_info=True)
        raise
