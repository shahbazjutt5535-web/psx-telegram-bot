"""
PSX Stock Indicator Telegram Bot
FINAL VERSION - With correct Meezan ETF symbol
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

# Import indicators
from indicators import *

# Import analysis template
from analysis_template import get_analysis_template

# Apply nest_asyncio for Render deployment
nest_asyncio.apply()

# -------------------------
# FIX: Patch input() before importing tvDatafeed
# -------------------------
import builtins
original_input = builtins.input
builtins.input = lambda prompt='': 'y\n'  # Auto-answer with 'y' and newline

# Import tvDatafeed
try:
    from tvDatafeed import TvDatafeed, Interval
    print("tvDatafeed imported successfully")
except Exception as e:
    print(f"Failed to import tvDatafeed: {e}")
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
    raise ValueError("BOT_TOKEN environment variable not set")

# -------------------------
# TradingView Initialization
# -------------------------
def init_tvdatafeed():
    """Initialize TvDatafeed with proper handling for headless environment"""
    
    # Method 1: Try with auto_login=False first (best for headless)
    try:
        tv = TvDatafeed(auto_login=False)
        logger.info("TvDatafeed initialized with auto_login=False")
        return tv
    except Exception as e:
        logger.warning(f"Method 1 failed: {e}")
    
    # Method 2: Simple initialization (might prompt for input)
    try:
        tv = TvDatafeed()
        logger.info("TvDatafeed initialized successfully")
        return tv
    except Exception as e:
        logger.warning(f"Method 2 failed: {e}")
    
    # Method 3: Explicit None credentials (fallback)
    try:
        tv = TvDatafeed(username=None, password=None)
        logger.info("TvDatafeed initialized with None credentials")
        return tv
    except Exception as e:
        logger.warning(f"Method 3 failed: {e}")
    
    # If all methods fail
    raise Exception("All TvDatafeed initialization methods failed")

# Initialize TvDatafeed
try:
    tv = init_tvdatafeed()
    # Test the connection with a simple request
    test_data = tv.get_hist(symbol="FFC", exchange="PSX", interval=Interval.in_daily, n_bars=1)
    if test_data is not None and not test_data.empty:
        logger.info("TvDatafeed connection test successful")
    else:
        logger.warning("TvDatafeed connection test returned no data")
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

# PSX Stocks - Updated with correct TradingView symbols
stocks = [
    {"symbol": "FFC", "name": "Fauji Fertilizer Company", "tv_symbol": "PSX:FFC"},
    {"symbol": "ENGROH", "name": "Engro Holdings", "tv_symbol": "PSX:ENGROH"},
    {"symbol": "OGDC", "name": "Oil & Gas Development Company", "tv_symbol": "PSX:OGDC"},
    {"symbol": "HUBC", "name": "Hub Power Company", "tv_symbol": "PSX:HUBC"},
    {"symbol": "PPL", "name": "Pakistan Petroleum Limited", "tv_symbol": "PSX:PPL"},
    {"symbol": "NBP", "name": "National Bank of Pakistan", "tv_symbol": "PSX:NBP"},
    {"symbol": "UBL", "name": "United Bank Limited", "tv_symbol": "PSX:UBL"},
    {"symbol": "MZNPETF", "name": "Meezan Pakistan ETF", "tv_symbol": "PSX:MZNPETF"},  # Corrected symbol
    {"symbol": "NBPGETF", "name": "NBP Pakistan Growth ETF", "tv_symbol": "PSX:NBPGETF"},
    {"symbol": "KEL", "name": "K-Electric", "tv_symbol": "PSX:KEL"},
    {"symbol": "SYS", "name": "Systems Limited", "tv_symbol": "PSX:SYS"},
    {"symbol": "LUCK", "name": "Lucky Cement", "tv_symbol": "PSX:LUCK"},
    {"symbol": "PSO", "name": "Pakistan State Oil", "tv_symbol": "PSX:PSO"},
]

# Alternative Meezan ETF symbols if the above doesn't work
meezan_alternatives = [
    "PSX:MZNPETF",
    "PSX:MEZNPETF", 
    "PSX:MEEZAN",
    "PSX:MZNP",
]

# Gold symbol
gold = {"symbol": "GOLD", "name": "Gold", "tv_symbol": "TVC:GOLD"}

# Combine all symbols
all_symbols = stocks + [gold]

# -------------------------
# Main indicator calculation function
# -------------------------
def calculate_all_indicators(df):
    """Calculate all technical indicators"""
    
    # Market Overview - already in df
    
    # 1️⃣ Trend Direction Indicators
    # SMAs
    df['SMA_10'] = SMA(df, 10)
    df['SMA_20'] = SMA(df, 20)
    df['SMA_50'] = SMA(df, 50)
    df['SMA_200'] = SMA(df, 200)
    
    # EMAs
    df['EMA_9'] = EMA(df, 9)
    df['EMA_21'] = EMA(df, 21)
    df['EMA_50'] = EMA(df, 50)
    df['EMA_200'] = EMA(df, 200)
    
    # WMAs
    df['WMA_8'] = WMA(df, 8)
    df['WMA_20'] = WMA(df, 20)
    df['WMA_50'] = WMA(df, 50)
    df['WMA_100'] = WMA(df, 100)
    
    # Hull MA
    df['HMA_9'] = HMA(df, 9)
    df['HMA_14'] = HMA(df, 14)
    df['HMA_21'] = HMA(df, 21)
    
    # Ichimoku
    df['ICHIMOKU_CONVERSION'], df['ICHIMOKU_BASE'], df['ICHIMOKU_SPAN_A'], df['ICHIMOKU_SPAN_B'] = Ichimoku(df)
    
    # SuperTrend
    df['SUPERTREND_7'] = SuperTrend(df, period=7, multiplier=3)
    df['SUPERTREND_10'] = SuperTrend(df, period=10, multiplier=3)
    df['SUPERTREND_14'] = SuperTrend(df, period=14, multiplier=3)
    
    # Parabolic SAR
    df['PSAR'] = ParabolicSAR(df)
    
    # 2️⃣ Momentum Strength
    # MACD (6,13,5)
    df['MACD_6_13_5'], df['MACD_SIGNAL_6_13_5'], df['MACD_HIST_6_13_5'] = MACD(df, fast=6, slow=13, signal=5)
    
    # MACD (12,26,9)
    df['MACD_12_26_9'], df['MACD_SIGNAL_12_26_9'], df['MACD_HIST_12_26_9'] = MACD(df)
    
    # VW-MACD
    df['VW_MACD'], df['VW_MACD_SIGNAL'], df['VW_MACD_HIST'] = VW_MACD(df)
    
    # RSI
    df['RSI_3'] = RSI(df, 3)
    df['RSI_10'] = RSI(df, 10)
    df['RSI_14'] = RSI(df, 14)
    
    # RVI
    df['RVI_14'], df['RVI_SIGNAL'] = RVI(df, 14)
    df['RVI_10'], _ = RVI(df, 10)
    
    # Stochastic RSI
    df['STOCH_RSI_K'], df['STOCH_RSI_D'] = Stochastic(df, 14, 3)
    
    # KDJ
    df['KDJ_K'], df['KDJ_D'], df['KDJ_J'] = KDJ(df)
    
    # Williams %R
    df['WILLIAMS_R_12'] = WilliamsR(df, 12)
    df['WILLIAMS_R_25'] = WilliamsR(df, 25)
    
    # CCI
    df['CCI_14'] = CCI(df, 14)
    df['CCI_20'] = CCI(df, 20)
    
    # ROC
    df['ROC_14'] = ROC(df, 14)
    df['ROC_25'] = ROC(df, 25)
    
    # Momentum
    df['MTM_10'] = Momentum(df, 10)
    df['MTM_20'] = Momentum(df, 20)
    
    # Ultimate Oscillator
    df['UO'] = UltimateOscillator(df)
    
    # ADX
    df['ADX_14'], df['PLUS_DI_14'], df['MINUS_DI_14'] = ADX(df)
    
    # TDI
    df['TDI_RSI'], df['TDI_UPPER'], df['TDI_LOWER'], df['TDI_SIGNAL'] = TDI(df)
    
    # 3️⃣ Volume & Money Flow
    # OBV
    df['OBV'] = OBV(df)
    
    # ADOSC
    df['ADOSC'] = ADOSC(df)
    
    # MFI
    df['MFI_14'] = MFI(df)
    
    # Aroon
    df['AROON_UP'], df['AROON_DOWN'] = Aroon(df)
    
    # VWAP
    df['VWAP_1'] = VWAP(df)
    df['VWAP_3'] = VWAP(df)  # Using same VWAP as requested
    df['VWAP_4'] = VWAP(df)
    
    # 4️⃣ Volatility & Range
    # Bollinger Bands
    df['BB_UPPER'], df['BB_MIDDLE'], df['BB_LOWER'] = Bollinger_Bands(df)
    
    # Fibonacci Bollinger Bands
    fib_bands = FibBollingerBands(df)
    df['FIB_BB_UPPER_1'] = fib_bands[0]
    df['FIB_BB_UPPER_0618'] = fib_bands[1]
    df['FIB_BB_UPPER_0382'] = fib_bands[2]
    df['FIB_BB_MIDDLE'] = fib_bands[3]
    df['FIB_BB_LOWER_0382'] = fib_bands[4]
    df['FIB_BB_LOWER_0618'] = fib_bands[5]
    df['FIB_BB_LOWER_1'] = fib_bands[6]
    
    # Keltner Channel
    df['KC_UPPER'], df['KC_MIDDLE'], df['KC_LOWER'] = KeltnerChannel(df)
    
    # ATR
    df['ATR_14'] = ATR(df)
    
    # Heikin Ashi
    df['HA_CLOSE'] = HeikinAshi(df)
    
    # Choppiness Index
    df['CHOP_14'] = ChoppinessIndex(df, 14)
    df['CHOP_21'] = ChoppinessIndex(df, 21)
    df['CHOP_UPPER'] = 61.8  # Upper band
    df['CHOP_LOWER'] = 38.2  # Lower band
    
    # TRIX
    df['TRIX_10'] = TRIX(df, 10)
    df['TRIX_14'] = TRIX(df, 14)
    df['TRIX_SIGNAL_7'] = df['TRIX_14'].ewm(span=7).mean()
    df['TRIX_SIGNAL_9'] = df['TRIX_14'].ewm(span=9).mean()
    
    # Donchian Channel
    df['DC_UPPER'], df['DC_MIDDLE'], df['DC_LOWER'] = DonchianChannel(df)
    
    return df

# -------------------------
# Format indicator values
# -------------------------
def format_value(value, decimals=2):
    """Format numeric value, handling NaN"""
    if pd.isna(value):
        return "N/A"
    if isinstance(value, (int, float)):
        return f"{value:.{decimals}f}"
    return str(value)

# -------------------------
# Create stock command with comprehensive output
# -------------------------
def create_stock_command(symbol, name, tv_symbol, interval_key):
    """Create a command handler with comprehensive indicator output"""
    
    async def command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Send immediate acknowledgment
        await update.message.reply_text(f"Fetching {name} ({interval_key}) data... This may take 10-15 seconds.")
        
        try:
            # Run in thread pool with timeout
            loop = asyncio.get_event_loop()
            
            # Parse exchange and symbol
            if ':' in tv_symbol:
                exchange, sym = tv_symbol.split(':')
            else:
                exchange = "PSX"
                sym = tv_symbol
            
            # Use asyncio.wait_for to set a timeout
            try:
                df = await asyncio.wait_for(
                    loop.run_in_executor(
                        None,
                        lambda: tv.get_hist(
                            symbol=sym,
                            exchange=exchange,
                            interval=interval_map[interval_key],
                            n_bars=300  # Get enough bars for all indicators
                        )
                    ),
                    timeout=25.0  # 25 seconds timeout
                )
            except asyncio.TimeoutError:
                logger.error(f"Timeout fetching {symbol} {interval_key}")
                await update.message.reply_text(f"Request timed out. TradingView is taking too long to respond. Please try again.")
                return
            
            # Validate data
            if df is None or df.empty:
                # If Meezan ETF fails, try alternative symbols
                if symbol == "MZNPETF":
                    await update.message.reply_text(f"Trying alternative symbol for {name}...")
                    for alt_sym in meezan_alternatives:
                        try:
                            if ':' in alt_sym:
                                alt_exchange, alt_symbol = alt_sym.split(':')
                            else:
                                alt_exchange = "PSX"
                                alt_symbol = alt_sym
                            
                            df = tv.get_hist(
                                symbol=alt_symbol,
                                exchange=alt_exchange,
                                interval=interval_map[interval_key],
                                n_bars=300
                            )
                            if df is not None and not df.empty:
                                await update.message.reply_text(f"Found data using symbol: {alt_sym}")
                                break
                        except:
                            continue
                
                if df is None or df.empty:
                    await update.message.reply_text(f"No data found for {name}. The symbol might not be available on TradingView.")
                    return
            
            if len(df) < 200:
                await update.message.reply_text(f"Insufficient data for {name}. Only {len(df)} bars available. Some indicators may not calculate.")
            
            # Calculate all indicators
            df = calculate_all_indicators(df)
            
            # Get latest values
            last = df.iloc[-1]
            prev = df.iloc[-2] if len(df) > 1 else last
            
            # Format close time
            close_time = df.index[-1].strftime('%Y-%m-%d %H:%M:%S')
            
            # Calculate change
            change_points = last['close'] - prev['close']
            change_percent = (change_points / prev['close']) * 100 if prev['close'] != 0 else 0
            
            # Determine change sign
            if change_points > 0:
                change_sign = "+"
            elif change_points < 0:
                change_sign = "-"
            else:
                change_sign = "="
            
            # Format message with all indicators
            message = (
                f"📊 {name} - {tv_symbol} ({interval_key})\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n\n"
                
                f"1️⃣ Market Overview\n"
                f"💰 Price: {format_value(last['close'])}\n"
                f"🔓 Open Price: {format_value(last['open'])}\n"
                f"📈 24h High: {format_value(last['high'])}\n"
                f"📉 24h Low: {format_value(last['low'])}\n"
                f"🔁 Change: {change_sign} {format_value(change_points)} ({format_value(change_percent)}%)\n"
                f"🧮 Volume: {format_value(last['volume'], 0)}\n"
                f"⏰ Close Time: {close_time}\n\n"
                
                f"2️⃣ Trend Direction\n\n"
                f"📊 Simple Moving Averages (SMA):\n"
                f" - SMA 10: {format_value(last['SMA_10'])}\n"
                f" - SMA 20: {format_value(last['SMA_20'])}\n"
                f" - SMA 50: {format_value(last['SMA_50'])}\n"
                f" - SMA 200: {format_value(last['SMA_200'])}\n\n"
                
                f"📈 Exponential Moving Averages (EMA):\n"
                f" - EMA 9: {format_value(last['EMA_9'])}\n"
                f" - EMA 21: {format_value(last['EMA_21'])}\n"
                f" - EMA 50: {format_value(last['EMA_50'])}\n"
                f" - EMA 200: {format_value(last['EMA_200'])}\n\n"
                
                f"⚖️ Weighted Moving Averages (WMA):\n"
                f" - WMA 8: {format_value(last['WMA_8'])}\n"
                f" - WMA 20: {format_value(last['WMA_20'])}\n"
                f" - WMA 50: {format_value(last['WMA_50'])}\n"
                f" - WMA 100: {format_value(last['WMA_100'])}\n\n"
                
                f"📈 Hull Moving Average:\n"
                f"  (HMA 9): {format_value(last['HMA_9'])}\n"
                f"  (HMA 14): {format_value(last['HMA_14'])}\n"
                f"  (HMA 21): {format_value(last['HMA_21'])}\n\n"
                
                f"📊 Ichimoku Cloud:\n"
                f" - Conversion Line (9): {format_value(last['ICHIMOKU_CONVERSION'])}\n"
                f" - Base Line (26): {format_value(last['ICHIMOKU_BASE'])}\n"
                f" - Leading Span A: {format_value(last['ICHIMOKU_SPAN_A'])}\n"
                f" - Leading Span B: {format_value(last['ICHIMOKU_SPAN_B'])}\n\n"
                
                f"📈 SuperTrend:\n"
                f" - Value(7): {format_value(last['SUPERTREND_7'])}\n"
                f" - Value(10): {format_value(last['SUPERTREND_10'])}\n"
                f" - Value(14): {format_value(last['SUPERTREND_14'])}\n\n"
                
                f"📈 Parabolic SAR:\n"
                f" - Step AF Value(0.02): {format_value(last['PSAR'])}\n\n"
                
                f"3️⃣ Momentum Strength\n\n"
                f"📉 MACD: 6,13,5\n"
                f" - MACD: {format_value(last['MACD_6_13_5'])}\n"
                f" - Signal: {format_value(last['MACD_SIGNAL_6_13_5'])}\n"
                f" - Histogram: {format_value(last['MACD_HIST_6_13_5'])}\n\n"
                
                f"📉 MACD: 12,26,9\n"
                f" - MACD: {format_value(last['MACD_12_26_9'])}\n"
                f" - Signal: {format_value(last['MACD_SIGNAL_12_26_9'])}\n"
                f" - Histogram: {format_value(last['MACD_HIST_12_26_9'])}\n\n"
                
                f"📊 Volume-Weighted MACD (VW-MACD):\n"
                f" - VW-MACD: {format_value(last['VW_MACD'])}\n"
                f" - VW-Signal: {format_value(last['VW_MACD_SIGNAL'])}\n"
                f" - VW-Histogram: {format_value(last['VW_MACD_HIST'])}\n\n"
                
                f"⚡ Relative Strength Index (RSI):\n"
                f" - RSI (3): {format_value(last['RSI_3'])}\n"
                f" - RSI (10): {format_value(last['RSI_10'])}\n"
                f" - RSI (14): {format_value(last['RSI_14'])}\n\n"
                
                f"📊 Relative Volatility Index (RVI):\n"
                f" - RVI (14): {format_value(last['RVI_14'])}\n"
                f" - RVI (10): {format_value(last['RVI_10'])}\n"
                f" - Signal Line(4): {format_value(last['RVI_SIGNAL'])}\n\n"
                
                f"📉 Stochastic RSI (14,3,3):\n"
                f" - %K: {format_value(last['STOCH_RSI_K'])}\n"
                f" - %D: {format_value(last['STOCH_RSI_D'])}\n\n"
                
                f"📊 KDJ (9,3,3):\n"
                f" - K: {format_value(last['KDJ_K'])}\n"
                f" - D: {format_value(last['KDJ_D'])}\n"
                f" - J: {format_value(last['KDJ_J'])}\n\n"
                
                f"📉 Williams %R Indicator:\n"
                f" - Williams %R (12): {format_value(last['WILLIAMS_R_12'])}\n"
                f" - Williams %R (25): {format_value(last['WILLIAMS_R_25'])}\n\n"
                
                f"📘 Commodity Channel Index (CCI):\n"
                f" - CCI (14): {format_value(last['CCI_14'])}\n"
                f" - CCI (20): {format_value(last['CCI_20'])}\n\n"
                
                f"📊 Rate of Change (ROC):\n"
                f" - ROC (14): {format_value(last['ROC_14'])}\n"
                f" - ROC (25): {format_value(last['ROC_25'])}\n\n"
                
                f"📈 Momentum (MTM):\n"
                f" - MTM (10): {format_value(last['MTM_10'])}\n"
                f" - MTM (20): {format_value(last['MTM_20'])}\n\n"
                
                f"🧭 Ultimate Oscillator:\n"
                f" - UO (7,14,28): {format_value(last['UO'])}\n\n"
                
                f"📊 ADX (Trend Strength):\n"
                f" - ADX (14): {format_value(last['ADX_14'])}\n"
                f" - +DI (14): {format_value(last['PLUS_DI_14'])}\n"
                f" - -DI (14): {format_value(last['MINUS_DI_14'])}\n\n"
                
                f"📊 Traders Dynamic Index (TDI):\n"
                f" - RSI (13): {format_value(last['TDI_RSI'])}\n"
                f" - Volatility Bands(34): {format_value(last['TDI_UPPER'])}\n"
                f" - Trade Signal Line (34): {format_value(last['TDI_SIGNAL'])}\n\n"
                
                f"4️⃣ Volume & Money Flow\n\n"
                f"📊 On-Balance Volume (OBV):\n"
                f" - OBV: {format_value(last['OBV'], 0)}\n\n"
                
                f"📊 ADOSC: {format_value(last['ADOSC'])}\n\n"
                
                f"💧 Money Flow Index (MFI):\n"
                f" - MFI (14): {format_value(last['MFI_14'])}\n\n"
                
                f"📊 Aroon Indicator (14):\n"
                f" - Aroon Up: {format_value(last['AROON_UP'])}\n"
                f" - Aroon Down: {format_value(last['AROON_DOWN'])}\n\n"
                
                f"🔹 VWAP:\n"
                f" - VWAP(1): {format_value(last['VWAP_1'])}\n"
                f" - VWAP(3): {format_value(last['VWAP_3'])}\n"
                f" - VWAP(4): {format_value(last['VWAP_4'])}\n\n"
                
                f"5️⃣ Volatility & Range\n\n"
                f"🎯 Bollinger Bands (20, 2 StdDev):\n"
                f" - Upper Band: {format_value(last['BB_UPPER'])}\n"
                f" - Middle Band: {format_value(last['BB_MIDDLE'])}\n"
                f" - Lower Band: {format_value(last['BB_LOWER'])}\n\n"
                
                f"📊 Fibonacci Bollinger Bands:\n"
                f" - Upper (1.0): {format_value(last['FIB_BB_UPPER_1'])}\n"
                f" - Fib 0.618: {format_value(last['FIB_BB_UPPER_0618'])}\n"
                f" - Fib 0.382: {format_value(last['FIB_BB_UPPER_0382'])}\n"
                f" - Middle: {format_value(last['FIB_BB_MIDDLE'])}\n"
                f" - Fib -0.382: {format_value(last['FIB_BB_LOWER_0382'])}\n"
                f" - Fib -0.618: {format_value(last['FIB_BB_LOWER_0618'])}\n"
                f" - Lower (-1.0): {format_value(last['FIB_BB_LOWER_1'])}\n\n"
                
                f"📐 Keltner Channel (20 EMA, 2 ATR):\n"
                f" - Upper Band: {format_value(last['KC_UPPER'])}\n"
                f" - Middle EMA: {format_value(last['KC_MIDDLE'])}\n"
                f" - Lower Band: {format_value(last['KC_LOWER'])}\n\n"
                
                f"📏 Average True Range (ATR):\n"
                f" - ATR (14): {format_value(last['ATR_14'])}\n\n"
                
                f"🕯 Heikin Ashi:\n"
                f" - Close: {format_value(last['HA_CLOSE'])}\n\n"
                
                f"🌀 Choppiness Index:\n"
                f" - Value (14): {format_value(last['CHOP_14'])}\n"
                f" - Value (21): {format_value(last['CHOP_21'])}\n"
                f" - Upper Band(61.8): 61.8\n"
                f" - Lower Band(38.2): 38.2\n\n"
                
                f"📊 TRIX:\n"
                f" - TRIX(10): {format_value(last['TRIX_10'])}\n"
                f" - TRIX(14): {format_value(last['TRIX_14'])}\n"
                f" - Signal EMA(7): {format_value(last['TRIX_SIGNAL_7'])}\n"
                f" - Signal EMA(9): {format_value(last['TRIX_SIGNAL_9'])}\n\n"
                
                f"📊 Donchian Channel (20):\n"
                f" - Upper: {format_value(last['DC_UPPER'])}\n"
                f" - Middle: {format_value(last['DC_MIDDLE'])}\n"
                f" - Lower: {format_value(last['DC_LOWER'])}\n\n"
                f"📍 Final Signal Summary"
            )
            
            # Split message if too long
            if len(message) > 4096:
                # Send first part
                await update.message.reply_text(message[:4096])
                # Send second part
                await update.message.reply_text(message[4096:])
            else:
                await update.message.reply_text(message)
            
        except Exception as e:
            logger.error(f"Error: {e}", exc_info=True)
            await update.message.reply_text(f"Error fetching {name}. Please try again later.")
    
    return command

# -------------------------
# Text Command - Returns the analysis template
# -------------------------
async def text_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /text command - returns the analysis template for copying"""
    try:
        template = get_analysis_template()
        await update.message.reply_text(template)
        logger.info(f"Text command used by user {update.effective_user.id}")
    except Exception as e:
        logger.error(f"Error in text command: {e}")
        await update.message.reply_text("Error retrieving analysis template. Please try again.")

# -------------------------
# Start/Ping Commands
# -------------------------
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command with simple response"""
    
    # Calculate ping response time
    start_time = time.time()
    msg = await update.message.reply_text("Checking...")
    end_time = time.time()
    ping_time = round((end_time - start_time) * 1000, 2)
    
    # Simple response with just the required text
    await msg.edit_text(
        f"Your PSX Bot is working! ✅\n"
        f"Ping response time: {ping_time}ms"
    )

async def ping_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Simple ping command"""
    start_time = time.time()
    msg = await update.message.reply_text("Pong!")
    end_time = time.time()
    latency = round((end_time - start_time) * 1000, 2)
    await msg.edit_text(f"Pong! Response time: {latency}ms")

# -------------------------
# Build Telegram Application
# -------------------------
telegram_app = ApplicationBuilder()\
    .token(BOT_TOKEN)\
    .concurrent_updates(True)\
    .build()

# Add commands
telegram_app.add_handler(CommandHandler("start", start_command))
telegram_app.add_handler(CommandHandler("ping", ping_command))
telegram_app.add_handler(CommandHandler("text", text_command))
logger.info("Added commands: /start, /ping, /text")

# Add all stock commands
for stock in stocks + [gold]:
    for interval_key in interval_map.keys():
        cmd_name = f"{stock['symbol'].lower()}_{interval_key}"
        telegram_app.add_handler(
            CommandHandler(
                cmd_name, 
                create_stock_command(
                    stock['symbol'], 
                    stock['name'], 
                    stock['tv_symbol'], 
                    interval_key
                )
            )
        )
        logger.info(f"Added command: /{cmd_name}")

# -------------------------
# Error Handler
# -------------------------
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors gracefully"""
    logger.error(f"Error: {context.error}", exc_info=True)
    try:
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "An error occurred. Please try again.\n"
                "If the problem persists, try a different timeframe or contact support."
            )
    except Exception as e:
        logger.error(f"Error in error handler: {e}")

telegram_app.add_error_handler(error_handler)

# -------------------------
# Flask App for Render
# -------------------------
flask_app = Flask(__name__)

@flask_app.route("/")
def home():
    return "PSX Indicator Bot is Running!"

@flask_app.route("/health")
def health():
    return {"status": "healthy", "bot": "running"}, 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

# -------------------------
# Main Execution
# -------------------------
if __name__ == "__main__":
    try:
        # Start Flask
        flask_thread = threading.Thread(target=run_flask, daemon=True)
        flask_thread.start()
        logger.info(f"Flask server started on port {os.environ.get('PORT', 10000)}")
        
        # Small delay
        time.sleep(2)
        
        # Start Telegram bot
        logger.info("Starting Telegram bot...")
        telegram_app.run_polling(drop_pending_updates=True)
        
    except KeyboardInterrupt:
        logger.info("Bot stopped")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        raise
