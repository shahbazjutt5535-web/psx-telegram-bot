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
import sys
import builtins

# Apply nest_asyncio
nest_asyncio.apply()

# -------------------------
# RADICAL FIX: Directly patch the tvDatafeed module before import
# -------------------------
import importlib.util
import sys

# First, let's completely disable input() globally
original_input = builtins.input
builtins.input = lambda prompt='': 'y'

# Now, let's forcefully patch the specific method in the library
try:
    # Import the module
    from tvDatafeed import main as tvdatafeed_main
    
    # Directly replace the __assert_dir method that contains the input() call
    def patched_assert_dir(self):
        """Patched version that doesn't ask for input"""
        import os
        import stat
        from pathlib import Path
        
        # Skip the input prompt entirely
        print("Auto-installing chromedriver...")
        
        home = str(Path.home())
        driver_dir = os.path.join(home, '.wdm', 'drivers', 'chromedriver')
        if not os.path.exists(driver_dir):
            os.makedirs(driver_dir, exist_ok=True)
        
        self.driver_dir = driver_dir
        
    # Apply the patch
    tvdatafeed_main.TvDatafeed._TvDatafeed__assert_dir = patched_assert_dir
    
    # Also patch the __init__ to avoid any other prompts
    original_init = tvdatafeed_main.TvDatafeed.__init__
    
    def patched_init(self, username=None, password=None, auto_login=None):
        """Patched init that skips prompts"""
        self.username = username
        self.password = password
        self.auto_login = auto_login if auto_login is not None else (username is not None)
        
        # Skip the assert_dir call that causes problems
        import os
        import stat
        from pathlib import Path
        
        home = str(Path.home())
        driver_dir = os.path.join(home, '.wdm', 'drivers', 'chromedriver')
        os.makedirs(driver_dir, exist_ok=True)
        self.driver_dir = driver_dir
        
        self.ws = None
        self.session = None
        self.token = None
        self.user_profile = None
        
    tvdatafeed_main.TvDatafeed.__init__ = patched_init
    
    # Now import the class
    from tvDatafeed import TvDatafeed, Interval
    print("Successfully patched tvDatafeed!")
    
except Exception as e:
    print(f"Patching failed: {e}")
    # Fallback to normal import
    from tvDatafeed import TvDatafeed, Interval

# Restore original input
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
    # Try different initialization methods
    tv = None
    
    methods = [
        lambda: TvDatafeed(),
        lambda: TvDatafeed(username=None, password=None),
        lambda: TvDatafeed(auto_login=False),
    ]
    
    for i, method in enumerate(methods):
        try:
            print(f"Trying method {i+1}...")
            tv = method()
            print(f"Method {i+1} succeeded!")
            break
        except Exception as e:
            print(f"Method {i+1} failed: {e}")
            continue
    
    if tv is None:
        raise Exception("All initialization methods failed")
        
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
# Telegram Command Generator
# -------------------------
def create_psx_command(symbol, interval_key):
    async def command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Send immediate acknowledgment
        await update.message.reply_text(f"⏳ Fetching {symbol} ({interval_key}) data...")
        
        try:
            # Run data fetching in thread pool
            loop = asyncio.get_event_loop()
            
            df = await loop.run_in_executor(
                None, 
                lambda: tv.get_hist(
                    symbol=symbol, 
                    exchange="PSX", 
                    interval=interval_map[interval_key], 
                    n_bars=150
                )
            )
            
            if df is None or df.empty:
                await update.message.reply_text(f"❌ No data for {symbol}")
                return

            if len(df) < 30:
                await update.message.reply_text(f"⚠️ Insufficient data for {symbol}")
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
            
            message = (
                f"📊 *{symbol} ({interval_key})*\n\n"
                f"💰 Close: `{last['close']:.2f}`\n"
                f"📊 Volume: `{last['volume']:,.0f}`\n\n"
                f"📈 RSI: `{last['RSI']:.2f}`\n"
                f"📈 MACD: `{last['MACD']:.2f}`\n"
                f"📈 Signal: `{last['MACD_SIGNAL']:.2f}`\n"
                f"📈 Stoch RSI: `{last['STOCH_RSI']:.2f}`\n"
                f"📈 ATR: `{last['ATR']:.2f}`\n"
                f"📈 SMA20: `{last['SMA20']:.2f}`\n"
                f"📈 EMA20: `{last['EMA20']:.2f}`\n"
                f"📈 OBV: `{last['OBV']:,.0f}`"
            )

            await update.message.reply_text(message, parse_mode='Markdown')

        except Exception as e:
            logging.error(f"Error: {e}", exc_info=True)
            await update.message.reply_text(f"❌ Error fetching {symbol}")

    return command

# -------------------------
# Telegram Bot App
# -------------------------
telegram_app = ApplicationBuilder()\
    .token(BOT_TOKEN)\
    .concurrent_updates(True)\
    .pool_timeout(30)\
    .connect_timeout(30)\
    .read_timeout(30)\
    .write_timeout(30)\
    .build()

# Add commands
for stock in stocks:
    for interval_key in interval_map.keys():
        cmd_name = f"{stock.lower()}_{interval_key}"
        telegram_app.add_handler(CommandHandler(cmd_name, create_psx_command(stock, interval_key)))
        logging.info(f"Added command: /{cmd_name}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔥 *PSX Bot Active*\n\n"
        "Commands:\n"
        "`/ffc_15m` - FFC 15m\n"
        "`/ogdc_1h` - OGDC 1h\n"
        "`/hubco_4h` - HUBCO 4h\n"
        "`/engro_12h` - ENGRO 12h",
        parse_mode='Markdown'
    )

telegram_app.add_handler(CommandHandler("start", start))

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.error(f"Error: {context.error}")

telegram_app.add_error_handler(error_handler)

# -------------------------
# Flask App
# -------------------------
flask_app = Flask(__name__)

@flask_app.route("/")
def home():
    return "✅ PSX Bot Running!"

@flask_app.route("/health")
def health():
    return {"status": "healthy"}, 200

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
        time.sleep(2)
        
        # Start bot
        logging.info("Starting bot...")
        telegram_app.run_polling(drop_pending_updates=True)
        
    except Exception as e:
        logging.error(f"Fatal: {e}", exc_info=True)
        raise
