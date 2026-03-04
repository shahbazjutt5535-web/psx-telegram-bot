import pandas_ta as ta

def calculate_all(data):

    # Moving Averages
    data["SMA5"] = ta.sma(data["close"], 5)
    data["SMA13"] = ta.sma(data["close"], 13)
    data["SMA21"] = ta.sma(data["close"], 21)
    data["SMA50"] = ta.sma(data["close"], 50)
    data["SMA100"] = ta.sma(data["close"], 100)
    data["SMA200"] = ta.sma(data["close"], 200)

    data["EMA5"] = ta.ema(data["close"], 5)
    data["EMA13"] = ta.ema(data["close"], 13)
    data["EMA21"] = ta.ema(data["close"], 21)
    data["EMA50"] = ta.ema(data["close"], 50)
    data["EMA100"] = ta.ema(data["close"], 100)
    data["EMA200"] = ta.ema(data["close"], 200)

    # MACD
    macd = ta.macd(data["close"], fast=3, slow=10, signal=16)
    data = data.join(macd)

    # RSI
    data["RSI5"] = ta.rsi(data["close"], 5)
    data["RSI14"] = ta.rsi(data["close"], 14)

    # ATR
    data["ATR14"] = ta.atr(data["high"], data["low"], data["close"], 14)

    # ADX
    adx = ta.adx(data["high"], data["low"], data["close"], 14)
    data = data.join(adx)

    # Bollinger
    bb = ta.bbands(data["close"], 20)
    data = data.join(bb)

    # Supertrend
    st = ta.supertrend(data["high"], data["low"], data["close"], 10, 3)
    data = data.join(st)

    # Donchian
    dc = ta.donchian(data["high"], data["low"], 20)
    data = data.join(dc)

    return data
