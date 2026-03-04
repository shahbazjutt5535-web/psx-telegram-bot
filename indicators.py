import pandas as pd
import numpy as np

def calculate_indicators(df):
    """
    Input: df with 'close' column
    Output: df with SMA, EMA, RSI, MACD, Bollinger Bands
    """
    # Simple Moving Averages
    for period in [5, 13, 21, 50, 100, 200]:
        df[f"SMA{period}"] = df["close"].rolling(window=period).mean()

    # Exponential Moving Averages
    for period in [5, 13, 21, 50, 100, 200]:
        df[f"EMA{period}"] = df["close"].ewm(span=period, adjust=False).mean()

    # Weighted Moving Averages
    for period in [5, 13, 21, 50, 100]:
        weights = np.arange(1, period + 1)
        df[f"WMA{period}"] = df["close"].rolling(period).apply(lambda prices: np.dot(prices, weights)/weights.sum(), raw=True)

    # RSI
    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()
    rs = avg_gain / avg_loss
    df["RSI14"] = 100 - (100 / (1 + rs))

    # MACD
    ema12 = df["close"].ewm(span=12, adjust=False).mean()
    ema26 = df["close"].ewm(span=26, adjust=False).mean()
    df["MACD"] = ema12 - ema26
    df["MACD_SIGNAL"] = df["MACD"].ewm(span=9, adjust=False).mean()
    df["MACD_HIST"] = df["MACD"] - df["MACD_SIGNAL"]

    # Bollinger Bands
    df["BB_MIDDLE"] = df["close"].rolling(20).mean()
    df["BB_STD"] = df["close"].rolling(20).std()
    df["BB_UPPER"] = df["BB_MIDDLE"] + 2 * df["BB_STD"]
    df["BB_LOWER"] = df["BB_MIDDLE"] - 2 * df["BB_STD"]

    return df
