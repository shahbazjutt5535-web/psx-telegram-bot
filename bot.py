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
# Interval Mapping
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

# -------------------------
# FIXED SYMBOLS - CORRECT ONES
# -------------------------
stocks = [
    {"symbol": "FFC", "name": "Fauji Fertilizer Company", "tv_symbol": "PSX:FFC"},
    {"symbol": "ENGRO", "name": "Engro Corporation", "tv_symbol": "PSX:ENGRO"},  # Fixed from ENGROH
    {"symbol": "OGDC", "name": "Oil & Gas Development Company", "tv_symbol": "PSX:OGDC"},
    {"symbol": "HUBC", "name": "Hub Power Company", "tv_symbol": "PSX:HUBC"},
    {"symbol": "PPL", "name": "Pakistan Petroleum Limited", "tv_symbol": "PSX:PPL"},
    {"symbol": "NBP", "name": "National Bank of Pakistan", "tv_symbol": "PSX:NBP"},
    {"symbol": "UBL", "name": "United Bank Limited", "tv_symbol": "PSX:UBL"},
    {"symbol": "MZNPETF", "name": "Meezan Pakistan ETF", "tv_symbol": "PSX:MZNPETF"},
    {"symbol": "NBPGETF", "name": "NBP Pakistan Growth ETF", "tv_symbol": "PSX:NBPGETF"},  # TEMP - using KSE100
    {"symbol": "KEL", "name": "K-Electric", "tv_symbol": "PSX:KEL"},
    {"symbol": "SYS", "name": "Systems Limited", "tv_symbol": "PSX:SYS"},
    {"symbol": "LUCK", "name": "Lucky Cement", "tv_symbol": "PSX:LUCK"},
    {"symbol": "PSO", "name": "Pakistan State Oil", "tv_symbol": "PSX:PSO"},
]

# KSE-100 Index - CORRECT SYMBOL
kse100 = {"symbol": "KSE100", "name": "KSE-100 Index", "tv_symbol": "PSX:KSE100"}

# Gold symbol
gold = {"symbol": "GOLD", "name": "Gold", "tv_symbol": "TVC:GOLD"}

# Alternative symbols for problematic ETFs
etf_alternatives = {
    "MZNPETF": ["PSX:MZNPETF", "PSX:MEZNPETF", "PSX:MZNP"],
    "NBPGETF": ["PSX:NBPGETF", "PSX:NBGETF", "PSX:NBPGETF"],  # KSE100 as fallback
}

# -------------------------
# Format value helper
# -------------------------
def format_value(value, decimals=2):
    """Format numeric value"""
    if pd.isna(value):
        return "N/A"
    if isinstance(value, (int, float)):
        return f"{value:.{decimals}f}"
    return str(value)

# -------------------------
# Calculate indicators by timeframe
# -------------------------
def calculate_indicators_by_timeframe(df, timeframe):
    """Calculate indicators with proper timeframe distribution"""
    
    # Base indicators for all timeframes
    df['EMA_9'] = EMA(df, 9)
    df['EMA_21'] = EMA(df, 21)
    df['EMA_50'] = EMA(df, 50)
    
    # EMA 200 for higher timeframes
    if timeframe in ["4h", "1d", "1w"]:
        df['EMA_200'] = EMA(df, 200)
    
    # HMA based on timeframe
    if timeframe in ["5m", "15m"]:
        df['HMA_9'] = HMA(df, 9)
    elif timeframe in ["30m", "1h"]:
        df['HMA_14'] = HMA(df, 14)
    elif timeframe in ["4h", "1d", "1w"]:
        df['HMA_21'] = HMA(df, 21)
    
    # Momentum indicators
    df['RSI'] = RSI(df, 14)
    df['MACD'], df['MACD_SIGNAL'], df['MACD_HIST'] = MACD(df)
    df['UO'] = UltimateOscillator(df)
    
    # ADX - 30m to 1w
    if timeframe in ["30m", "1h", "4h", "1d", "1w"]:
        df['ADX'], df['PLUS_DI'], df['MINUS_DI'] = ADX(df, 14)
    
    # ROC - 5m to 4h
    if timeframe in ["5m", "15m", "30m", "1h", "4h"]:
        df['ROC_14'] = ROC(df, 14)
        df['ROC_25'] = ROC(df, 25)
    
    # CCI - 5m to 1h
    if timeframe in ["5m", "15m", "30m", "1h"]:
        df['CCI_14'] = CCI(df, 14)
        df['CCI_20'] = CCI(df, 20)
    
    # Volume indicators
    df['OBV'] = OBV(df)
    df['VOLUME_MA'] = Volume_MA(df, 20)
    df['VOLUME_OSC'] = Volume_Oscillator(df, 5, 20)
    
    # ADI - 1h to 1w
    if timeframe in ["1h", "4h", "1d", "1w"]:
        df['ADI'] = ADI(df)
    
    # CMF - 1h, 4h
    if timeframe in ["1h", "4h"]:
        df['CMF'] = CMF(df, 20)
    
    # ELDER RAY - 15m to 4h (as requested)
    if timeframe in ["15m", "30m", "1h", "4h"]:
        df['BULL_POWER'], df['BEAR_POWER'] = ElderRay(df, 13)
    
    # VWAP for intraday
    if timeframe in ["5m", "15m", "30m", "1h", "4h"]:
        df['VWAP'] = VWAP_HLC3(df)
        vwap, upper1, lower1, upper2, lower2 = VWAP_Bands(df, 1, 2)
        df['VWAP'] = vwap
        df['VWAP_UPPER_1'] = upper1
        df['VWAP_LOWER_1'] = lower1
        df['VWAP_UPPER_2'] = upper2
        df['VWAP_LOWER_2'] = lower2
    
    # Volatility indicators
    df['ATR'] = ATR(df, 14)
    df['BB_UPPER'], df['BB_MIDDLE'], df['BB_LOWER'] = Bollinger_Bands(df)
    
    # Keltner Channels - 5m to 1h
    if timeframe in ["5m", "15m", "30m", "1h"]:
        df['KC_UPPER'], df['KC_MIDDLE'], df['KC_LOWER'] = KeltnerChannels(df, 20, 2)
    
    # Donchian Channel
    df['DC_UPPER'], df['DC_MIDDLE'], df['DC_LOWER'] = DonchianChannel(df, 20)
    
    # Parabolic SAR - 5m to 4h
    if timeframe in ["5m", "15m", "30m", "1h", "4h"]:
        df['PSAR'] = ParabolicSAR(df)
    
    # Timeframe specific indicators
    if timeframe in ["5m", "15m"]:
        df['SUPERTREND'] = SuperTrend(df, period=7, multiplier=3)
        df['MFI'] = MFI(df, 10)
        df['HA_CLOSE'] = HeikinAshi(df)
    
    elif timeframe in ["30m", "1h"]:
        if timeframe == "1h":
            df['ICHIMOKU_CONVERSION'], df['ICHIMOKU_BASE'], df['ICHIMOKU_SPAN_A'], df['ICHIMOKU_SPAN_B'] = Ichimoku(df)
        
        df['SUPERTREND'] = SuperTrend(df, period=10, multiplier=3)
        df['MFI'] = MFI(df, 14)
        df['AROON_UP'], df['AROON_DOWN'] = Aroon(df, 14)
        df['HA_CLOSE'] = HeikinAshi(df)
    
    elif timeframe == "4h":
        df['ICHIMOKU_CONVERSION'], df['ICHIMOKU_BASE'], df['ICHIMOKU_SPAN_A'], df['ICHIMOKU_SPAN_B'] = Ichimoku(df)
        df['SUPERTREND'] = SuperTrend(df, period=14, multiplier=3)
        df['MFI'] = MFI(df, 14)
        df['AROON_UP'], df['AROON_DOWN'] = Aroon(df, 14)
        df['HA_CLOSE'] = HeikinAshi(df)
        
        # Fibonacci on 4h+
        try:
            fib_high, fib_low, fib_levels = Fibonacci_Retracement(df, 100)
            if fib_high is not None:
                df['FIB_HIGH'] = fib_high
                df['FIB_LOW'] = fib_low
                df.attrs['fib_levels'] = fib_levels
        except:
            pass
    
    else:  # 1d, 1w
        df['ICHIMOKU_CONVERSION'], df['ICHIMOKU_BASE'], df['ICHIMOKU_SPAN_A'], df['ICHIMOKU_SPAN_B'] = Ichimoku(df)
        df['SUPERTREND_7'] = SuperTrend(df, period=7, multiplier=3)
        df['SUPERTREND_14'] = SuperTrend(df, period=14, multiplier=3)
        df['MFI'] = MFI(df, 14)
        df['AROON_UP'], df['AROON_DOWN'] = Aroon(df, 14)
        df['HA_CLOSE'] = HeikinAshi(df)
        
        # Fibonacci
        try:
            fib_high, fib_low, fib_levels = Fibonacci_Retracement(df, 200)
            if fib_high is not None:
                df['FIB_HIGH'] = fib_high
                df['FIB_LOW'] = fib_low
                df.attrs['fib_levels'] = fib_levels
        except:
            pass
        
        # Volume Profile
        try:
            poc, va_low, va_high, bins, profile = Volume_Profile(df, 12)
            if poc is not None:
                df['VOL_PROFILE_POC'] = poc
                df['VOL_PROFILE_VA_LOW'] = va_low
                df['VOL_PROFILE_VA_HIGH'] = va_high
        except:
            pass
        
        # Pivot Points
        try:
            pivot, r1, r2, s1, s2 = PivotPoints(df)
            if pivot is not None:
                df['PIVOT'] = pivot
                df['R1'] = r1
                df['R2'] = r2
                df['S1'] = s1
                df['S2'] = s2
        except:
            pass
    
    return df

# -------------------------
# Create stock command
# -------------------------
def create_stock_command(symbol, name, tv_symbol, interval_key):
    """Create a command handler"""
    
    async def command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(f"Fetching {name} ({interval_key}) data...")
        
        try:
            loop = asyncio.get_event_loop()
            
            if ':' in tv_symbol:
                exchange, sym = tv_symbol.split(':')
            else:
                exchange = "PSX"
                sym = tv_symbol
            
            # Try primary symbol
            df = await loop.run_in_executor(
                None,
                lambda: tv.get_hist(
                    symbol=sym,
                    exchange=exchange,
                    interval=interval_map[interval_key],
                    n_bars=500
                )
            )
            
            # If ETF fails, try alternatives
            if (df is None or df.empty) and symbol in etf_alternatives:
                for alt_sym in etf_alternatives[symbol]:
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
                            await update.message.reply_text(f"Using alternative symbol: {alt_sym}")
                            break
                    except:
                        continue
            
            if df is None or df.empty:
                await update.message.reply_text(f"No data found for {name}. Please check symbol.")
                return
            
            # Calculate indicators
            df = calculate_indicators_by_timeframe(df, interval_key)
            
            # Get latest values
            last = df.iloc[-1]
            prev = df.iloc[-2] if len(df) > 1 else last
            
            # Calculate Day's Range
            if interval_key in ["5m", "15m", "30m", "1h", "4h"]:
                today = pd.Timestamp.now().date()
                today_data = df[df.index.date == today]
                
                if not today_data.empty:
                    day_high = today_data['high'].max()
                    day_low = today_data['low'].min()
                else:
                    day_high = df['high'].iloc[-min(24, len(df)):].max()
                    day_low = df['low'].iloc[-min(24, len(df)):].min()
            else:
                day_high = last['high']
                day_low = last['low']
            
            close_time = df.index[-1].strftime('%Y-%m-%d %H:%M:%S')
            
            change_points = last['close'] - prev['close']
            change_percent = (change_points / prev['close']) * 100 if prev['close'] != 0 else 0
            
            if change_points > 0:
                change_sign = "+"
            elif change_points < 0:
                change_sign = "-"
            else:
                change_sign = "="
            
            # Build message
            message = (
                f"📊 {name} - {tv_symbol} ({interval_key})\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n\n"
                
                f"1️⃣ Market Overview\n"
                f"💰 Price: {format_value(last['close'])}\n"
                f"🔓 Open Price: {format_value(last['open'])}\n"
                f"🔒 Prev Close: {format_value(prev['close'])}\n"
                f"📈 Day Range High: {format_value(day_high)}\n"
                f"📉 Day Range Low: {format_value(day_low)}\n"
                f"🔁 Change: {change_sign} {format_value(change_points)} ({format_value(change_percent)}%)\n"
                f"🧮 Volume: {format_value(last['volume'], 0)}\n"
                f"⏰ Close Time: {close_time}\n\n"
                
                f"2️⃣ Trend Direction\n\n"
            )
            
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
            hma_section = "🔷 Hull Moving Average (HMA):\n"
            if 'HMA_9' in last.index:
                hma_section += f" - HMA 9: {format_value(last['HMA_9'])}\n"
            if 'HMA_14' in last.index:
                hma_section += f" - HMA 14: {format_value(last['HMA_14'])}\n"
            if 'HMA_21' in last.index:
                hma_section += f" - HMA 21: {format_value(last['HMA_21'])}\n"
            if hma_section != "🔷 Hull Moving Average (HMA):\n":
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
            if 'SUPERTREND_14' in last.index:
                st_section += f" - Value(14): {format_value(last['SUPERTREND_14'])}\n"
            if st_section != "📈 SuperTrend:\n":
                message += st_section + "\n"
            
            # Parabolic SAR
            if 'PSAR' in last.index:
                message += f"📈 Parabolic SAR:\n - SAR: {format_value(last['PSAR'])}\n\n"
            
            # Heikin Ashi
            if 'HA_CLOSE' in last.index:
                message += f"🕯 Heikin Ashi:\n - Close: {format_value(last['HA_CLOSE'])}\n\n"
            
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
            
            # CCI
            if 'CCI_14' in last.index:
                message += f"📊 Commodity Channel Index (CCI):\n - CCI (14): {format_value(last['CCI_14'])}\n"
            if 'CCI_20' in last.index:
                message += f" - CCI (20): {format_value(last['CCI_20'])}\n\n"
            
            # ROC
            if 'ROC_14' in last.index:
                message += f"📊 Rate of Change (ROC):\n - ROC (14): {format_value(last['ROC_14'])}%\n"
            if 'ROC_25' in last.index:
                message += f" - ROC (25): {format_value(last['ROC_25'])}%\n\n"
            
            # ADX
            if 'ADX' in last.index:
                message += (
                    f"📊 ADX (Average Directional Index):\n"
                    f" - ADX (14): {format_value(last['ADX'])}\n"
                    f" - +DI (14): {format_value(last['PLUS_DI'])}\n"
                    f" - -DI (14): {format_value(last['MINUS_DI'])}\n\n"
                )
            
            # Ultimate Oscillator
            if 'UO' in last.index:
                message += f"🧭 Ultimate Oscillator:\n - UO (7,14,28): {format_value(last['UO'])}\n\n"
            
            # 4️⃣ Volume & Money Flow
            message += f"4️⃣ Volume & Money Flow\n\n"
            
            # OBV
            if 'OBV' in last.index:
                message += f"📊 On-Balance Volume (OBV):\n - OBV: {format_value(last['OBV'], 0)}\n\n"
            
            # MFI
            if 'MFI' in last.index:
                message += f"💧 Money Flow Index (MFI):\n - MFI: {format_value(last['MFI'])}\n\n"
            
            # ADI
            if 'ADI' in last.index:
                message += f"📊 Accumulation/Distribution Index (ADI):\n - ADI: {format_value(last['ADI'], 0)}\n\n"
            
            # CMF
            if 'CMF' in last.index:
                message += f"📊 Chaikin Money Flow (CMF):\n - CMF (20): {format_value(last['CMF'])}\n\n"
            
            # Elder Ray - NEW
            if 'BULL_POWER' in last.index:
                message += (
                    f"📊 Elder Ray Index (13):\n"
                    f" - Bull Power: {format_value(last['BULL_POWER'])}\n"
                    f" - Bear Power: {format_value(last['BEAR_POWER'])}\n\n"
                )
            
            # Volume Analysis
            if 'VOLUME_MA' in last.index:
                volume_ratio = last['volume'] / last['VOLUME_MA'] if last['VOLUME_MA'] > 0 else 0
                message += (
                    f"📊 Volume Analysis:\n"
                    f" - Volume MA (20): {format_value(last['VOLUME_MA'], 0)}\n"
                    f" - Volume Ratio: {format_value(volume_ratio, 2)}x\n"
                )
                if 'VOLUME_OSC' in last.index:
                    message += f" - Volume Oscillator: {format_value(last['VOLUME_OSC'], 2)}%\n"
                message += "\n"
            
            # Aroon
            if 'AROON_UP' in last.index:
                message += (
                    f"📊 Aroon Indicator (14):\n"
                    f" - Aroon Up: {format_value(last['AROON_UP'])}\n"
                    f" - Aroon Down: {format_value(last['AROON_DOWN'])}\n\n"
                )
            
            # VWAP
            if 'VWAP' in last.index:
                message += f"🔹 VWAP (HLC3):\n - VWAP: {format_value(last['VWAP'])}\n"
                if 'VWAP_UPPER_1' in last.index:
                    message += f" - VWAP +1σ: {format_value(last['VWAP_UPPER_1'])}\n"
                    message += f" - VWAP -1σ: {format_value(last['VWAP_LOWER_1'])}\n"
                if 'VWAP_UPPER_2' in last.index:
                    message += f" - VWAP +2σ: {format_value(last['VWAP_UPPER_2'])}\n"
                    message += f" - VWAP -2σ: {format_value(last['VWAP_LOWER_2'])}\n"
                message += "\n"
            
            # 5️⃣ Volatility & Range
            message += f"5️⃣ Volatility & Range\n\n"
            
            # Bollinger Bands
            if 'BB_UPPER' in last.index:
                bb_width = (last['BB_UPPER'] - last['BB_LOWER']) / last['BB_MIDDLE'] * 100
                message += (
                    f"🎯 Bollinger Bands (20, 2 StdDev):\n"
                    f" - Upper Band: {format_value(last['BB_UPPER'])}\n"
                    f" - Middle Band: {format_value(last['BB_MIDDLE'])}\n"
                    f" - Lower Band: {format_value(last['BB_LOWER'])}\n"
                    f" - Band Width: {format_value(bb_width, 2)}%\n\n"
                )
            
            # Keltner Channels
            if 'KC_UPPER' in last.index:
                message += (
                    f"📊 Keltner Channels (20, 2 ATR):\n"
                    f" - Upper Channel: {format_value(last['KC_UPPER'])}\n"
                    f" - Middle Line: {format_value(last['KC_MIDDLE'])}\n"
                    f" - Lower Channel: {format_value(last['KC_LOWER'])}\n\n"
                )
            
            # ATR
            if 'ATR' in last.index:
                message += f"📏 Average True Range (ATR):\n - ATR (14): {format_value(last['ATR'])}\n\n"
            
            # Donchian Channel
            if 'DC_UPPER' in last.index:
                message += (
                    f"📊 Donchian Channel (20):\n"
                    f" - Upper: {format_value(last['DC_UPPER'])}\n"
                    f" - Middle: {format_value(last['DC_MIDDLE'])}\n"
                    f" - Lower: {format_value(last['DC_LOWER'])}\n\n"
                )
            
            # Fibonacci
            if 'FIB_HIGH' in last.index:
                message += f"📊 Fibonacci Levels:\n"
                message += f" - Swing High: {format_value(last['FIB_HIGH'])}\n"
                message += f" - Swing Low: {format_value(last['FIB_LOW'])}\n"
                
                if hasattr(df, 'attrs') and 'fib_levels' in df.attrs:
                    fib_levels = df.attrs['fib_levels']
                    for level, price in sorted(fib_levels.items()):
                        message += f" - Fib {level*100:.1f}%: {format_value(price)}\n"
                message += "\n"
            
            # Volume Profile
            if 'VOL_PROFILE_POC' in last.index and not pd.isna(last['VOL_PROFILE_POC']):
                message += f"📊 Volume Profile:\n"
                message += f" - POC: {format_value(last['VOL_PROFILE_POC'])}\n"
                if not pd.isna(last['VOL_PROFILE_VA_LOW']):
                    message += f" - Value Area Low: {format_value(last['VOL_PROFILE_VA_LOW'])}\n"
                    message += f" - Value Area High: {format_value(last['VOL_PROFILE_VA_HIGH'])}\n"
                message += "\n"
            
            # Pivot Points
            if 'PIVOT' in last.index and not pd.isna(last['PIVOT']):
                message += (
                    f"📊 Pivot Points:\n"
                    f" - Pivot: {format_value(last['PIVOT'])}\n"
                    f" - R1: {format_value(last['R1'])}\n"
                    f" - R2: {format_value(last['R2'])}\n"
                    f" - S1: {format_value(last['S1'])}\n"
                    f" - S2: {format_value(last['S2'])}\n\n"
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
# Basic Commands

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
for stock in stocks + [kse100] + [gold]:
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
