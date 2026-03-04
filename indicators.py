import pandas as pd
import numpy as np
from tvDatafeed import TvDatafeed, Interval

# ---------------------------
# Helper indicator functions
# ---------------------------
def EMA(data, period=14):
    return data['close'].ewm(span=period, adjust=False).mean()

def SMA(data, period=14):
    return data['close'].rolling(window=period).mean()

def RSI(data, period=14):
    delta = data['close'].diff()
    gain = delta.clip(lower=0)
    loss = -1 * delta.clip(upper=0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def MACD(data, fast=12, slow=26, signal=9):
    exp1 = data['close'].ewm(span=fast, adjust=False).mean()
    exp2 = data['close'].ewm(span=slow, adjust=False).mean()
    macd = exp1 - exp2
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    return macd, signal_line

def Bollinger_Bands(data, period=20):
    sma = SMA(data, period)
    std = data['close'].rolling(period).std()
    upper = sma + (2 * std)
    lower = sma - (2 * std)
    return upper, lower

def ATR(data, period=14):
    high_low = data['high'] - data['low']
    high_close = np.abs(data['high'] - data['close'].shift())
    low_close = np.abs(data['low'] - data['close'].shift())
    tr = high_low.combine(high_close, max).combine(low_close, max)
    atr = tr.rolling(period).mean()
    return atr

def Stochastic(data, k_period=14, d_period=3):
    low_min = data['low'].rolling(k_period).min()
    high_max = data['high'].rolling(k_period).max()
    k = 100 * ((data['close'] - low_min) / (high_max - low_min))
    d = k.rolling(d_period).mean()
    return k, d

# ---------------------------
# Calculate all indicators for a given symbol
# ---------------------------
def calculate_all(tv: TvDatafeed, symbol="PSX:KSE100", interval=Interval.in_daily, n=100):
    """
    Fetch latest n candles from TradingView and calculate signals
    """
    try:
        df = tv.get_hist(symbol=symbol, interval=interval, n=n)
        if df.empty:
            return "No data available for symbol."

        signals = []

        # EMA & SMA signals
        ema20 = EMA(df, 20).iloc[-1]
        ema50 = EMA(df, 50).iloc[-1]
        sma20 = SMA(df, 20).iloc[-1]

        if ema20 > ema50:
            signals.append("EMA20 > EMA50 ✅ Bullish")
        else:
            signals.append("EMA20 < EMA50 ❌ Bearish")

        if df['close'].iloc[-1] > sma20:
            signals.append("Price above SMA20 ✅")
        else:
            signals.append("Price below SMA20 ❌")

        # MACD
        macd, signal_line = MACD(df)
        if macd.iloc[-1] > signal_line.iloc[-1]:
            signals.append("MACD bullish crossover ✅")
        else:
            signals.append("MACD bearish crossover ❌")

        # RSI
        rsi_val = RSI(df).iloc[-1]
        if rsi_val > 70:
            signals.append(f"RSI: {rsi_val:.2f} ❌ Overbought")
        elif rsi_val < 30:
            signals.append(f"RSI: {rsi_val:.2f} ✅ Oversold")
        else:
            signals.append(f"RSI: {rsi_val:.2f} Neutral")

        # Bollinger Bands
        upper, lower = Bollinger_Bands(df)
        close_price = df['close'].iloc[-1]
        if close_price > upper.iloc[-1]:
            signals.append(f"Price above upper BB ❌ Overbought")
        elif close_price < lower.iloc[-1]:
            signals.append(f"Price below lower BB ✅ Oversold")
        else:
            signals.append("Price within Bollinger Bands")

        # ATR
        atr_val = ATR(df).iloc[-1]
        signals.append(f"ATR(14): {atr_val:.2f}")

        # Stochastic
        k, d = Stochastic(df)
        if k.iloc[-1] > d.iloc[-1]:
            signals.append("Stochastic bullish ✅")
        else:
            signals.append("Stochastic bearish ❌")

        return "\n".join(signals)

    except Exception as e:
        return f"Error calculating indicators: {e}"
