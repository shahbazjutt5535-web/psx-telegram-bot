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

def WMA(data, period=14):
    """Weighted Moving Average"""
    weights = np.arange(1, period + 1)
    def wma(window):
        return np.dot(window, weights) / weights.sum()
    return data['close'].rolling(window=period).apply(wma, raw=True)

def HMA(data, period=14):
    """Hull Moving Average"""
    half_length = int(period / 2)
    sqrt_length = int(np.sqrt(period))
    
    wma_half = WMA(data, half_length)
    wma_full = WMA(data, period)
    raw_hma = 2 * wma_half - wma_full
    hma = WMA(pd.DataFrame({'close': raw_hma}), sqrt_length)
    return hma

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
    histogram = macd - signal_line
    return macd, signal_line, histogram

def Bollinger_Bands(data, period=20, std_dev=2):
    sma = SMA(data, period)
    std = data['close'].rolling(period).std()
    upper = sma + (std_dev * std)
    lower = sma - (std_dev * std)
    return upper, sma, lower

def ATR(data, period=14):
    high_low = data['high'] - data['low']
    high_close = np.abs(data['high'] - data['close'].shift())
    low_close = np.abs(data['low'] - data['close'].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    atr = tr.rolling(period).mean()
    return atr

def Stochastic(data, k_period=14, d_period=3):
    low_min = data['low'].rolling(k_period).min()
    high_max = data['high'].rolling(k_period).max()
    k = 100 * ((data['close'] - low_min) / (high_max - low_min))
    d = k.rolling(d_period).mean()
    return k, d

def Ichimoku(data, conversion=9, base=26, span=52):
    """Ichimoku Cloud"""
    high = data['high']
    low = data['low']
    
    # Conversion Line (Tenkan-sen)
    conversion_high = high.rolling(conversion).max()
    conversion_low = low.rolling(conversion).min()
    conversion_line = (conversion_high + conversion_low) / 2
    
    # Base Line (Kijun-sen)
    base_high = high.rolling(base).max()
    base_low = low.rolling(base).min()
    base_line = (base_high + base_low) / 2
    
    # Leading Span A (Senkou Span A)
    leading_span_a = ((conversion_line + base_line) / 2).shift(base)
    
    # Leading Span B (Senkou Span B)
    span_high = high.rolling(span).max()
    span_low = low.rolling(span).min()
    leading_span_b = ((span_high + span_low) / 2).shift(base)
    
    return conversion_line, base_line, leading_span_a, leading_span_b

def SuperTrend(data, period=10, multiplier=3):
    """SuperTrend Indicator"""
    hl2 = (data['high'] + data['low']) / 2
    atr = ATR(data, period)
    
    upper_band = hl2 + (multiplier * atr)
    lower_band = hl2 - (multiplier * atr)
    
    supertrend = [0] * len(data)
    trend = [1] * len(data)  # 1 for uptrend, -1 for downtrend
    
    for i in range(1, len(data)):
        if data['close'].iloc[i] > upper_band.iloc[i-1]:
            trend[i] = 1
        elif data['close'].iloc[i] < lower_band.iloc[i-1]:
            trend[i] = -1
        else:
            trend[i] = trend[i-1]
            if trend[i] == 1 and lower_band.iloc[i] < lower_band.iloc[i-1]:
                lower_band.iloc[i] = lower_band.iloc[i-1]
            if trend[i] == -1 and upper_band.iloc[i] > upper_band.iloc[i-1]:
                upper_band.iloc[i] = upper_band.iloc[i-1]
        
        if trend[i] == 1:
            supertrend[i] = lower_band.iloc[i]
        else:
            supertrend[i] = upper_band.iloc[i]
    
    return pd.Series(supertrend, index=data.index)

def ParabolicSAR(data, step=0.02, max_step=0.20):
    """Parabolic SAR"""
    high = data['high']
    low = data['low']
    
    psar = [0] * len(data)
    bull = [True] * len(data)
    af = [step] * len(data)
    ep = [0] * len(data)
    
    if len(data) > 1:
        if high.iloc[0] - low.iloc[0] < high.iloc[1] - low.iloc[1]:
            bull[0] = True
            psar[0] = low.iloc[0]
            ep[0] = high.iloc[0]
        else:
            bull[0] = False
            psar[0] = high.iloc[0]
            ep[0] = low.iloc[0]
    
    for i in range(1, len(data)):
        if bull[i-1]:
            psar[i] = psar[i-1] + af[i-1] * (ep[i-1] - psar[i-1])
            if low.iloc[i] < psar[i]:
                bull[i] = False
                psar[i] = ep[i-1]
                ep[i] = low.iloc[i]
                af[i] = step
            else:
                bull[i] = True
                if high.iloc[i] > ep[i-1]:
                    ep[i] = high.iloc[i]
                    af[i] = min(af[i-1] + step, max_step)
                else:
                    ep[i] = ep[i-1]
                    af[i] = af[i-1]
        else:
            psar[i] = psar[i-1] - af[i-1] * (psar[i-1] - ep[i-1])
            if high.iloc[i] > psar[i]:
                bull[i] = True
                psar[i] = ep[i-1]
                ep[i] = high.iloc[i]
                af[i] = step
            else:
                bull[i] = False
                if low.iloc[i] < ep[i-1]:
                    ep[i] = low.iloc[i]
                    af[i] = min(af[i-1] + step, max_step)
                else:
                    ep[i] = ep[i-1]
                    af[i] = af[i-1]
    
    return pd.Series(psar, index=data.index)

def OBV(data):
    """On-Balance Volume"""
    obv = [0]
    for i in range(1, len(data)):
        if data['close'].iloc[i] > data['close'].iloc[i-1]:
            obv.append(obv[-1] + data['volume'].iloc[i])
        elif data['close'].iloc[i] < data['close'].iloc[i-1]:
            obv.append(obv[-1] - data['volume'].iloc[i])
        else:
            obv.append(obv[-1])
    return pd.Series(obv, index=data.index)

def MFI(data, period=14):
    """Money Flow Index"""
    typical_price = (data['high'] + data['low'] + data['close']) / 3
    money_flow = typical_price * data['volume']
    
    positive_flow = []
    negative_flow = []
    
    for i in range(1, len(typical_price)):
        if typical_price.iloc[i] > typical_price.iloc[i-1]:
            positive_flow.append(money_flow.iloc[i])
            negative_flow.append(0)
        else:
            positive_flow.append(0)
            negative_flow.append(money_flow.iloc[i])
    
    positive_flow = pd.Series(positive_flow, index=typical_price.index[1:])
    negative_flow = pd.Series(negative_flow, index=typical_price.index[1:])
    
    pos_mf = positive_flow.rolling(period).sum()
    neg_mf = negative_flow.rolling(period).sum()
    
    mfi = 100 - (100 / (1 + (pos_mf / neg_mf)))
    return mfi

def VWAP(data):
    """Volume Weighted Average Price"""
    vwap = (data['close'] * data['volume']).cumsum() / data['volume'].cumsum()
    return vwap

def KeltnerChannel(data, period=20, atr_period=10, multiplier=2):
    """Keltner Channel"""
    ema = EMA(data, period)
    atr = ATR(data, atr_period)
    
    upper = ema + (multiplier * atr)
    lower = ema - (multiplier * atr)
    
    return upper, ema, lower

def HeikinAshi(data):
    """Heikin Ashi candles"""
    ha_data = pd.DataFrame(index=data.index)
    
    ha_data['ha_close'] = (data['open'] + data['high'] + data['low'] + data['close']) / 4
    
    ha_open = [data['open'].iloc[0]]
    for i in range(1, len(data)):
        ha_open.append((ha_open[i-1] + ha_data['ha_close'].iloc[i-1]) / 2)
    ha_data['ha_open'] = ha_open
    
    ha_data['ha_high'] = data[['high', 'low', 'close']].max(axis=1)
    ha_data['ha_low'] = data[['high', 'low', 'close']].min(axis=1)
    
    return ha_data['ha_close']

def ChoppinessIndex(data, period=14):
    """Choppiness Index"""
    tr = ATR(data, 1)  # True Range
    high_period = data['high'].rolling(period).max()
    low_period = data['low'].rolling(period).min()
    
    ci = 100 * np.log10(tr.rolling(period).sum() / (high_period - low_period)) / np.log10(period)
    return ci

def TRIX(data, period=14):
    """TRIX Indicator"""
    ema1 = EMA(data, period)
    ema2 = EMA(pd.DataFrame({'close': ema1}), period)
    ema3 = EMA(pd.DataFrame({'close': ema2}), period)
    
    trix = 100 * (ema3.diff() / ema3.shift(1))
    return trix

def DonchianChannel(data, period=20):
    """Donchian Channel"""
    upper = data['high'].rolling(period).max()
    lower = data['low'].rolling(period).min()
    middle = (upper + lower) / 2
    
    return upper, middle, lower

def ADX(data, period=14):
    """Average Directional Index"""
    high = data['high']
    low = data['low']
    close = data['close']
    
    plus_dm = high.diff()
    minus_dm = low.diff()
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm > 0] = 0
    
    tr = ATR(data, 1)  # True Range
    
    plus_di = 100 * (plus_dm.ewm(alpha=1/period).mean() / tr.ewm(alpha=1/period).mean())
    minus_di = abs(100 * (minus_dm.ewm(alpha=1/period).mean() / tr.ewm(alpha=1/period).mean()))
    
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
    adx = dx.ewm(alpha=1/period).mean()
    
    return adx, plus_di, minus_di

def Aroon(data, period=14):
    """Aroon Indicator"""
    aroon_up = 100 * (data['high'].rolling(period).apply(lambda x: period - x.argmax()) / period)
    aroon_down = 100 * (data['low'].rolling(period).apply(lambda x: period - x.argmin()) / period)
    
    return aroon_up, aroon_down

def WilliamsR(data, period=14):
    """Williams %R"""
    high_period = data['high'].rolling(period).max()
    low_period = data['low'].rolling(period).min()
    
    williams_r = -100 * ((high_period - data['close']) / (high_period - low_period))
    return williams_r

def CCI(data, period=14):
    """Commodity Channel Index"""
    tp = (data['high'] + data['low'] + data['close']) / 3
    sma_tp = tp.rolling(period).mean()
    mad = tp.rolling(period).apply(lambda x: np.abs(x - x.mean()).mean())
    
    cci = (tp - sma_tp) / (0.015 * mad)
    return cci

def ROC(data, period=14):
    """Rate of Change"""
    roc = ((data['close'] - data['close'].shift(period)) / data['close'].shift(period)) * 100
    return roc

def Momentum(data, period=14):
    """Momentum"""
    momentum = data['close'] - data['close'].shift(period)
    return momentum

def UltimateOscillator(data, period1=7, period2=14, period3=28):
    """Ultimate Oscillator"""
    high = data['high']
    low = data['low']
    close = data['close']
    
    bp = close - np.minimum(low, close.shift(1))
    tr = np.maximum(high, close.shift(1)) - np.minimum(low, close.shift(1))
    
    avg1 = bp.rolling(period1).sum() / tr.rolling(period1).sum()
    avg2 = bp.rolling(period2).sum() / tr.rolling(period2).sum()
    avg3 = bp.rolling(period3).sum() / tr.rolling(period3).sum()
    
    uo = 100 * (4 * avg1 + 2 * avg2 + avg3) / 7
    return uo

def KDJ(data, period=9, k_slow=3, d_slow=3):
    """KDJ Indicator"""
    low_min = data['low'].rolling(period).min()
    high_max = data['high'].rolling(period).max()
    
    rsv = (data['close'] - low_min) / (high_max - low_min) * 100
    
    k = rsv.ewm(span=k_slow, adjust=False).mean()
    d = k.ewm(span=d_slow, adjust=False).mean()
    j = 3 * k - 2 * d
    
    return k, d, j

def RVI(data, period=14):
    """Relative Volatility Index"""
    std = data['close'].rolling(period).std()
    
    up_std = std.where(data['close'] > data['close'].shift(1), 0)
    down_std = std.where(data['close'] < data['close'].shift(1), 0)
    
    up_avg = up_std.rolling(period).mean()
    down_avg = down_std.rolling(period).mean()
    
    rvi = 100 * up_avg / (up_avg + down_avg)
    signal = rvi.rolling(4).mean()
    
    return rvi, signal

def ADOSC(data, fast_period=3, slow_period=10):
    """Accumulation/Distribution Oscillator"""
    clv = ((data['close'] - data['low']) - (data['high'] - data['close'])) / (data['high'] - data['low'])
    ad = clv * data['volume']
    ad = ad.cumsum()
    
    adosc = ad.ewm(span=fast_period).mean() - ad.ewm(span=slow_period).mean()
    return adosc

def FibBollingerBands(data, period=20, std_dev=2):
    """Fibonacci Bollinger Bands"""
    sma = SMA(data, period)
    std = data['close'].rolling(period).std()
    
    upper_std = sma + (std_dev * std)
    lower_std = sma - (std_dev * std)
    
    # Fibonacci levels
    fib_levels = [1.0, 0.618, 0.382, 0, -0.382, -0.618, -1.0]
    bands = []
    
    for level in fib_levels:
        if level >= 0:
            band = sma + (level * (upper_std - sma))
        else:
            band = sma + (level * (sma - lower_std))
        bands.append(band)
    
    return bands

def TDI(data, rsi_period=13, bb_period=34, signal_period=34):
    """Traders Dynamic Index"""
    rsi = RSI(data, rsi_period)
    
    # Volatility Bands (similar to Bollinger Bands on RSI)
    rsi_sma = SMA(pd.DataFrame({'close': rsi}), bb_period)
    rsi_std = rsi.rolling(bb_period).std()
    
    rsi_upper = rsi_sma + (2 * rsi_std)
    rsi_lower = rsi_sma - (2 * rsi_std)
    
    # Trade Signal Line
    trade_signal = rsi.ewm(span=signal_period).mean()
    
    return rsi, rsi_upper, rsi_lower, trade_signal

def VW_MACD(data, fast=12, slow=26, signal=9):
    """Volume-Weighted MACD"""
    volume_ema12 = data['close'].ewm(span=fast, adjust=False).mean()
    volume_ema26 = data['close'].ewm(span=slow, adjust=False).mean()
    
    vw_macd = (volume_ema12 - volume_ema26) * (data['volume'] / data['volume'].rolling(50).mean())
    vw_signal = vw_macd.ewm(span=signal, adjust=False).mean()
    vw_histogram = vw_macd - vw_signal
    
    return vw_macd, vw_signal, vw_histogram
