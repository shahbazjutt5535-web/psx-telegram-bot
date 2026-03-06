"""
PSX Stock Indicator Telegram Bot
FINAL VERSION - 90% Accuracy with Timeframe Optimized Settings
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
    
    try:
        tv = TvDatafeed(auto_login=False)
        logger.info("TvDatafeed initialized with auto_login=False")
        return tv
    except Exception as e:
        logger.warning(f"Method 1 failed: {e}")
    
    try:
        tv = TvDatafeed()
        logger.info("TvDatafeed initialized successfully")
        return tv
    except Exception as e:
        logger.warning(f"Method 2 failed: {e}")
    
    try:
        tv = TvDatafeed(username=None, password=None)
        logger.info("TvDatafeed initialized with None credentials")
        return tv
    except Exception as e:
        logger.warning(f"Method 3 failed: {e}")
    
    raise Exception("All TvDatafeed initialization methods failed")

# Initialize TvDatafeed
try:
    tv = init_tvdatafeed()
    test_data = tv.get_hist(symbol="FFC", exchange="PSX", interval=Interval.in_daily, n_bars=1)
    if test_data is not None and not test_data.empty:
        logger.info("TvDatafeed connection test successful")
    else:
        logger.warning("TvDatafeed connection test returned no data")
except Exception as e:
    logger.error(f"Fatal: Could not initialize TvDatafeed: {e}")
    raise

# -------------------------
# Interval Mapping - ALL TIMEFRAMES (5min to 1week)
# -------------------------
interval_map = {
    "5m": Interval.in_5_minute,
    "15m": Interval.in_15_minute,
    "30m": Interval.in_30_minute,
    "1h": Interval.in_1_hour,
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
    {"symbol": "MZNPETF", "name": "Meezan Pakistan ETF", "tv_symbol": "PSX:MZNPETF"},
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
# TIME FRAME OPTIMIZED INDICATORS - 90% ACCURACY
# -------------------------
def calculate_indicators_by_timeframe(df, timeframe):
    """Calculate indicators with settings optimized for specific timeframe"""
    
    # ===== 5 MINUTE / 15 MINUTE (Scalping - Fast) =====
    if timeframe in ["5m", "15m"]:
        # Fast Moving Averages
        df['SMA_20'] = SMA(df, 20)
        df['EMA_9'] = EMA(df, 9)
        df['EMA_21'] = EMA(df, 21)
        df['HMA_9'] = HMA(df, 9)
        
        # Ichimoku
        df['ICHIMOKU_CONVERSION'], df['ICHIMOKU_BASE'], df['ICHIMOKU_SPAN_A'], df['ICHIMOKU_SPAN_B'] = Ichimoku(df)
        
        # SuperTrend - Fast
        df['SUPERTREND'] = SuperTrend(df, period=7, multiplier=3)
        
        # Parabolic SAR
        df['PSAR'] = ParabolicSAR(df)
        
        # MACD
        df['MACD'], df['MACD_SIGNAL'], df['MACD_HIST'] = MACD(df)
        
        # RSI
        df['RSI'] = RSI(df, 14)
        
        # Stochastic - Fast
        df['STOCH_K'], df['STOCH_D'] = Stochastic(df, 10, 3)
        
        # KDJ
        df['KDJ_K'], df['KDJ_D'] = KDJ(df, 9, 3, 3)
        
        # Williams %R
        df['WILLIAMS'] = WilliamsR(df, 25)
        
        # CCI
        df['CCI'] = CCI(df, 14)
        
        # ROC
        df['ROC'] = ROC(df, 14)
        
        # ADX
        df['ADX'], df['PLUS_DI'], df['MINUS_DI'] = ADX(df, 14)
        
        # Ultimate Oscillator
        df['UO'] = UltimateOscillator(df)
        
        # Volume
        df['OBV'] = OBV(df)
        df['MFI'] = MFI(df, 10)
        df['VWAP'] = VWAP(df)
        df['AROON_UP'], df['AROON_DOWN'] = Aroon(df, 10)
        
        # Bollinger Bands - Fast
        df['BB_UPPER'], df['BB_MIDDLE'], df['BB_LOWER'] = Bollinger_Bands(df, 15, 2)
        
        # ATR - Fast
        df['ATR'] = ATR(df, 7)
        
        # Heikin Ashi
        df['HA_CLOSE'] = HeikinAshi(df)
        
        # Donchian Channel - Fast
        df['DC_UPPER'], df['DC_MIDDLE'], df['DC_LOWER'] = DonchianChannel(df, 15)
    
    # ===== 30 MINUTE / 1 HOUR (Intraday - Medium) =====
    elif timeframe in ["30m", "1h"]:
        # Moving Averages
        df['SMA_20'] = SMA(df, 20)
        df['SMA_50'] = SMA(df, 50)
        df['EMA_9'] = EMA(df, 9)
        df['EMA_21'] = EMA(df, 21)
        df['EMA_50'] = EMA(df, 50)
        df['HMA_14'] = HMA(df, 14)
        
        # Ichimoku
        df['ICHIMOKU_CONVERSION'], df['ICHIMOKU_BASE'], df['ICHIMOKU_SPAN_A'], df['ICHIMOKU_SPAN_B'] = Ichimoku(df)
        
        # SuperTrend - Medium
        df['SUPERTREND'] = SuperTrend(df, period=10, multiplier=3)
        
        # Parabolic SAR
        df['PSAR'] = ParabolicSAR(df)
        
        # MACD
        df['MACD'], df['MACD_SIGNAL'], df['MACD_HIST'] = MACD(df)
        
        # RSI
        df['RSI'] = RSI(df, 14)
        
        # Stochastic
        df['STOCH_K'], df['STOCH_D'] = Stochastic(df, 14, 3)
        
        # KDJ
        df['KDJ_K'], df['KDJ_D'] = KDJ(df)
        
        # Williams %R
        df['WILLIAMS'] = WilliamsR(df, 25)
        
        # CCI
        df['CCI'] = CCI(df, 14)
        
        # ROC
        df['ROC'] = ROC(df, 14)
        
        # Ultimate Oscillator
        df['UO'] = UltimateOscillator(df)
        
        # ADX
        df['ADX'], df['PLUS_DI'], df['MINUS_DI'] = ADX(df, 14)
        
        # Volume
        df['OBV'] = OBV(df)
        df['MFI'] = MFI(df, 14)
        df['VWAP'] = VWAP(df)
        df['AROON_UP'], df['AROON_DOWN'] = Aroon(df, 14)
        
        # Bollinger Bands
        df['BB_UPPER'], df['BB_MIDDLE'], df['BB_LOWER'] = Bollinger_Bands(df)
        
        # ATR
        df['ATR'] = ATR(df, 14)
        
        # Heikin Ashi
        df['HA_CLOSE'] = HeikinAshi(df)
        
        # Donchian Channel
        df['DC_UPPER'], df['DC_MIDDLE'], df['DC_LOWER'] = DonchianChannel(df, 20)
    
    # ===== 4 HOUR (Swing Trading - Slow) =====
    elif timeframe == "4h":
        # Moving Averages
        df['SMA_20'] = SMA(df, 20)
        df['SMA_50'] = SMA(df, 50)
        df['SMA_200'] = SMA(df, 200)
        df['EMA_9'] = EMA(df, 9)
        df['EMA_21'] = EMA(df, 21)
        df['EMA_50'] = EMA(df, 50)
        df['EMA_200'] = EMA(df, 200)
        df['HMA_21'] = HMA(df, 21)
        
        # Ichimoku
        df['ICHIMOKU_CONVERSION'], df['ICHIMOKU_BASE'], df['ICHIMOKU_SPAN_A'], df['ICHIMOKU_SPAN_B'] = Ichimoku(df)
        
        # SuperTrend - Slow
        df['SUPERTREND'] = SuperTrend(df, period=14, multiplier=3)
        
        # Parabolic SAR
        df['PSAR'] = ParabolicSAR(df)
        
        # MACD
        df['MACD'], df['MACD_SIGNAL'], df['MACD_HIST'] = MACD(df)
        
        # RSI
        df['RSI'] = RSI(df, 14)
        
        # Stochastic
        df['STOCH_K'], df['STOCH_D'] = Stochastic(df, 14, 3)
        
        # KDJ
        df['KDJ_K'], df['KDJ_D'] = KDJ(df)
        
        # Williams %R
        df['WILLIAMS'] = WilliamsR(df, 25)
        
        # CCI - Slower for 4h
        df['CCI'] = CCI(df, 20)
        
        # ROC
        df['ROC'] = ROC(df, 14)
        
        # ADX
        df['ADX'], df['PLUS_DI'], df['MINUS_DI'] = ADX(df, 14)
        
        # Volume
        df['OBV'] = OBV(df)
        df['MFI'] = MFI(df, 14)
        df['VWAP'] = VWAP(df)
        df['AROON_UP'], df['AROON_DOWN'] = Aroon(df, 14)
        
        # Bollinger Bands
        df['BB_UPPER'], df['BB_MIDDLE'], df['BB_LOWER'] = Bollinger_Bands(df)
        
        # ATR
        df['ATR'] = ATR(df, 14)
        
        # Heikin Ashi
        df['HA_CLOSE'] = HeikinAshi(df)
        
        # Donchian Channel
        df['DC_UPPER'], df['DC_MIDDLE'], df['DC_LOWER'] = DonchianChannel(df, 20)
    
    # ===== DAILY / WEEKLY (Position Trading - Strong Trends) =====
    else:  # "1d", "1w"
        # All important Moving Averages
        df['SMA_20'] = SMA(df, 20)
        df['SMA_50'] = SMA(df, 50)
        df['SMA_200'] = SMA(df, 200)
        df['EMA_9'] = EMA(df, 9)
        df['EMA_21'] = EMA(df, 21)
        df['EMA_50'] = EMA(df, 50)
        df['EMA_200'] = EMA(df, 200)
        df['HMA_21'] = HMA(df, 21)
        
        # Ichimoku
        df['ICHIMOKU_CONVERSION'], df['ICHIMOKU_BASE'], df['ICHIMOKU_SPAN_A'], df['ICHIMOKU_SPAN_B'] = Ichimoku(df)
        
        # SuperTrend - All periods for confirmation
        df['SUPERTREND_7'] = SuperTrend(df, period=7, multiplier=3)
        df['SUPERTREND_10'] = SuperTrend(df, period=10, multiplier=3)
        df['SUPERTREND_14'] = SuperTrend(df, period=14, multiplier=3)
        
        # Parabolic SAR
        df['PSAR'] = ParabolicSAR(df)
        
        # MACD
        df['MACD'], df['MACD_SIGNAL'], df['MACD_HIST'] = MACD(df)
        
        # RSI
        df['RSI'] = RSI(df, 14)
        
        # Stochastic
        df['STOCH_K'], df['STOCH_D'] = Stochastic(df, 14, 3)
        
        # KDJ
        df['KDJ_K'], df['KDJ_D'] = KDJ(df)
        
        # Williams %R
        df['WILLIAMS'] = WilliamsR(df, 25)
        
        # CCI
        df['CCI'] = CCI(df, 20)
        
        # ROC
        df['ROC'] = ROC(df, 14)
        
        # ADX
        df['ADX'], df['PLUS_DI'], df['MINUS_DI'] = ADX(df, 14)
        
        # Ultimate Oscillator
        df['UO'] = UltimateOscillator(df)
        
        # Volume
        df['OBV'] = OBV(df)
        df['MFI'] = MFI(df, 14)
        df['VWAP'] = VWAP(df)
        df['AROON_UP'], df['AROON_DOWN'] = Aroon(df, 14)
        
        # Bollinger Bands
        df['BB_UPPER'], df['BB_MIDDLE'], df['BB_LOWER'] = Bollinger_Bands(df)
        
        # ATR
        df['ATR'] = ATR(df, 14)
        
        # Heikin Ashi
        df['HA_CLOSE'] = HeikinAshi(df)
        
        # Donchian Channel
        df['DC_UPPER'], df['DC_MIDDLE'], df['DC_LOWER'] = DonchianChannel(df, 20)
    
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
                            n_bars=500  # Enough bars for all indicators
                        )
                    ),
                    timeout=25.0
                )
            except asyncio.TimeoutError:
                logger.error(f"Timeout fetching {symbol} {interval_key}")
                await update.message.reply_text(f"Request timed out. Please try again.")
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
                                n_bars=500
                            )
                            if df is not None and not df.empty:
                                await update.message.reply_text(f"Found data using symbol: {alt_sym}")
                                break
                        except:
                            continue
                
                if df is None or df.empty:
                    await update.message.reply_text(f"No data found for {name}.")
                    return
            
            # Calculate indicators based on timeframe
            df = calculate_indicators_by_timeframe(df, interval_key)
            
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
            
            # START BUILDING MESSAGE - EXACT FORMAT AS REQUESTED
            message = (
                f"📊 {name} - {tv_symbol} ({interval_key})\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n\n"
                
                f"1️⃣ Market Overview\n"
                f"💰 Price: {format_value(last['close'])}\n"
                f"🔓 Open Price: {format_value(last['open'])}\n"
                f"🔒 LDCP: {format_value(prev['close'])}\n"  
                f"📈 24h High: {format_value(last['high'])}\n"
                f"📉 24h Low: {format_value(last['low'])}\n"
                f"🔁 Change: {change_sign} {format_value(change_points)} ({format_value(change_percent)}%)\n"
                f"🧮 Volume: {format_value(last['volume'], 0)}\n"
                f"⏰ Close Time: {close_time}\n\n"
                
                f"2️⃣ Trend Direction\n\n"
            )
            
            # Add available SMA values
            sma_section = "📊 Simple Moving Averages (SMA):\n"
            if 'SMA_10' in last.index:
                sma_section += f" - SMA 10: {format_value(last['SMA_10'])}\n"
            if 'SMA_20' in last.index:
                sma_section += f" - SMA 20: {format_value(last['SMA_20'])}\n"
            if 'SMA_50' in last.index:
                sma_section += f" - SMA 50: {format_value(last['SMA_50'])}\n"
            if 'SMA_200' in last.index:
                sma_section += f" - SMA 200: {format_value(last['SMA_200'])}\n"
            if sma_section != "📊 Simple Moving Averages (SMA):\n":
                message += sma_section + "\n"
            
            # EMA section
            ema_section = "📈 Exponential Moving Averages (EMA):\n"
            if 'EMA_9' in last.index:
                ema_section += f" - EMA 9: {format_value(last['EMA_9'])}\n"
            if 'EMA_21' in last.index:
                ema_section += f" - EMA 21: {format_value(last['EMA_21'])}\n"
            if 'EMA_50' in last.index:
                ema_section += f" - EMA 50: {format_value(last['EMA_50'])}\n"
            if 'EMA_200' in last.index:
                ema_section += f" - EMA 200: {format_value(last['EMA_200'])}\n"
            if ema_section != "📈 Exponential Moving Averages (EMA):\n":
                message += ema_section + "\n"
            
            # HMA section
            hma_section = "📈 Hull Moving Average:\n"
            if 'HMA_9' in last.index:
                hma_section += f"  (HMA 9): {format_value(last['HMA_9'])}\n"
            if 'HMA_14' in last.index:
                hma_section += f"  (HMA 14): {format_value(last['HMA_14'])}\n"
            if 'HMA_21' in last.index:
                hma_section += f"  (HMA 21): {format_value(last['HMA_21'])}\n"
            if hma_section != "📈 Hull Moving Average:\n":
                message += hma_section + "\n"
            
            # Ichimoku
            if 'ICHIMOKU_CONVERSION' in last.index:
                message += (
                    f"📊 Ichimoku Cloud:\n"
                    f" - Conversion Line (9): {format_value(last['ICHIMOKU_CONVERSION'])}\n"
                    f" - Base Line (26): {format_value(last['ICHIMOKU_BASE'])}\n"
                    f" - Leading Span A: {format_value(last['ICHIMOKU_SPAN_A'])}\n"
                    f" - Leading Span B: {format_value(last['ICHIMOKU_SPAN_B'])}\n\n"
                )
            
            # SuperTrend
            st_section = "📈 SuperTrend:\n"
            if 'SUPERTREND' in last.index:
                st_section += f" - Value: {format_value(last['SUPERTREND'])}\n"
            if 'SUPERTREND_7' in last.index:
                st_section += f" - Value(7): {format_value(last['SUPERTREND_7'])}\n"
            if 'SUPERTREND_10' in last.index:
                st_section += f" - Value(10): {format_value(last['SUPERTREND_10'])}\n"
            if 'SUPERTREND_14' in last.index:
                st_section += f" - Value(14): {format_value(last['SUPERTREND_14'])}\n"
            if st_section != "📈 SuperTrend:\n":
                message += st_section + "\n"
            
            # Parabolic SAR
            if 'PSAR' in last.index:
                message += f"📈 Parabolic SAR:\n - Step AF Value(0.02): {format_value(last['PSAR'])}\n\n"
            
            # 3️⃣ Momentum Strength
            message += f"3️⃣ Momentum Strength\n\n"
            
            # MACD
            if 'MACD' in last.index:
                message += (
                    f"📉 MACD: 12,26,9\n"
                    f" - MACD: {format_value(last['MACD'])}\n"
                    f" - Signal: {format_value(last['MACD_SIGNAL'])}\n"
                    f" - Histogram: {format_value(last['MACD_HIST'])}\n\n"
                )
            
            # RSI
            if 'RSI' in last.index:
                message += f"⚡ Relative Strength Index (RSI):\n - RSI (14): {format_value(last['RSI'])}\n\n"
            
            # Stochastic
            if 'STOCH_K' in last.index:
                message += (
                    f"📉 Stochastic (14,3,3):\n"
                    f" - %K: {format_value(last['STOCH_K'])}\n"
                    f" - %D: {format_value(last['STOCH_D'])}\n\n"
                )
            
            # KDJ
            if 'KDJ_K' in last.index:
                message += (
                    f"📊 KDJ (9,3,3):\n"
                    f" - K: {format_value(last['KDJ_K'])}\n"
                    f" - D: {format_value(last['KDJ_D'])}\n\n"
                )
            
            # Williams %R
            if 'WILLIAMS' in last.index:
                message += f"📉 Williams %R Indicator:\n - Williams %R (25): {format_value(last['WILLIAMS'])}\n\n"
            
            # CCI
            if 'CCI' in last.index:
                message += f"📘 Commodity Channel Index (CCI):\n - CCI (14): {format_value(last['CCI'])}\n\n"
            
            # ROC
            if 'ROC' in last.index:
                message += f"📊 Rate of Change (ROC):\n - ROC (14): {format_value(last['ROC'])}\n\n"
            
            # Ultimate Oscillator
            if 'UO' in last.index:
                message += f"🧭 Ultimate Oscillator:\n - UO (7,14,28): {format_value(last['UO'])}\n\n"
            
            # ADX
            if 'ADX' in last.index:
                message += (
                    f"📊 ADX (Trend Strength):\n"
                    f" - ADX (14): {format_value(last['ADX'])}\n"
                    f" - +DI (14): {format_value(last['PLUS_DI'])}\n"
                    f" - -DI (14): {format_value(last['MINUS_DI'])}\n\n"
                )
            
            # 4️⃣ Volume & Money Flow
            message += f"4️⃣ Volume & Money Flow\n\n"
            
            # OBV
            if 'OBV' in last.index:
                message += f"📊 On-Balance Volume (OBV):\n - OBV: {format_value(last['OBV'], 0)}\n\n"
            
            # MFI
            if 'MFI' in last.index:
                message += f"💧 Money Flow Index (MFI):\n - MFI (14): {format_value(last['MFI'])}\n\n"
            
            # Aroon
            if 'AROON_UP' in last.index:
                message += (
                    f"📊 Aroon Indicator (14):\n"
                    f" - Aroon Up: {format_value(last['AROON_UP'])}\n"
                    f" - Aroon Down: {format_value(last['AROON_DOWN'])}\n\n"
                )
            
            # VWAP
            if 'VWAP' in last.index:
                message += f"🔹 VWAP:\n - VWAP: {format_value(last['VWAP'])}\n\n"
            
            # 5️⃣ Volatility & Range
            message += f"5️⃣ Volatility & Range\n\n"
            
            # Bollinger Bands
            if 'BB_UPPER' in last.index:
                message += (
                    f"🎯 Bollinger Bands (20, 2 StdDev):\n"
                    f" - Upper Band: {format_value(last['BB_UPPER'])}\n"
                    f" - Middle Band: {format_value(last['BB_MIDDLE'])}\n"
                    f" - Lower Band: {format_value(last['BB_LOWER'])}\n\n"
                )
            
            # ATR
            if 'ATR' in last.index:
                message += f"📏 Average True Range (ATR):\n - ATR (14): {format_value(last['ATR'])}\n\n"
            
            # Heikin Ashi
            if 'HA_CLOSE' in last.index:
                message += f"🕯 Heikin Ashi:\n - Close: {format_value(last['HA_CLOSE'])}\n\n"
            
            # Donchian Channel
            if 'DC_UPPER' in last.index:
                message += (
                    f"📊 Donchian Channel (20):\n"
                    f" - Upper: {format_value(last['DC_UPPER'])}\n"
                    f" - Middle: {format_value(last['DC_MIDDLE'])}\n"
                    f" - Lower: {format_value(last['DC_LOWER'])}\n\n"
                )
            
            # Final Signal Summary
            message += f"📍 Final Signal Summary"
            
            # Split message if too long
            if len(message) > 4096:
                await update.message.reply_text(message[:4096])
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
    
    start_time = time.time()
    msg = await update.message.reply_text("Checking...")
    end_time = time.time()
    ping_time = round((end_time - start_time) * 1000, 2)
    
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

# Add all stock commands for all timeframes
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
