import pandas as pd
import numpy as np

def calculate_all(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculates major technical indicators:
    SMA, EMA, RSI, MACD, Bollinger Bands, Stochastic, ATR, OBV, ADX, CCI, Momentum
    """

    # --- SMA ---
    df['SMA_10'] = df['close'].rolling(10).mean()
    df['SMA_20'] = df['close'].rolling(20).mean()
    df['SMA_50'] = df['close'].rolling(50).mean()

    # --- EMA ---
    df['EMA_10'] = df['close'].ewm(span=10, adjust=False).mean()
    df['EMA_20'] = df['close'].ewm(span=20, adjust=False).mean()
    df['EMA_50'] = df['close'].ewm(span=50, adjust=False).mean()

    # --- RSI ---
    delta = df['close'].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()
    rs = avg_gain / avg_loss
    df['RSI_14'] = 100 - (100 / (1 + rs))

    # --- MACD ---
    df['EMA_12'] = df['close'].ewm(span=12, adjust=False).mean()
    df['EMA_26'] = df['close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = df['EMA_12'] - df['EMA_26']
    df['MACD_SIGNAL'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_HIST'] = df['MACD'] - df['MACD_SIGNAL']

    # --- Bollinger Bands ---
    df['BBM'] = df['close'].rolling(20).mean()
    df['BB_STD'] = df['close'].rolling(20).std()
    df['BBU'] = df['BBM'] + 2 * df['BB_STD']
    df['BBL'] = df['BBM'] - 2 * df['BB_STD']
    df['BBP'] = (df['close'] - df['BBL']) / (df['BBU'] - df['BBL'])

    # --- Stochastic Oscillator ---
    low_min = df['low'].rolling(14).min()
    high_max = df['high'].rolling(14).max()
    df['STOCH_K'] = 100 * (df['close'] - low_min) / (high_max - low_min)
    df['STOCH_D'] = df['STOCH_K'].rolling(3).mean()

    # --- ATR (Average True Range) ---
    df['H-L'] = df['high'] - df['low']
    df['H-PC'] = abs(df['high'] - df['close'].shift(1))
    df['L-PC'] = abs(df['low'] - df['close'].shift(1))
    df['TR'] = df[['H-L', 'H-PC', 'L-PC']].max(axis=1)
    df['ATR_14'] = df['TR'].rolling(14).mean()
    df.drop(['H-L','H-PC','L-PC','TR','BB_STD','EMA_12','EMA_26'], axis=1, inplace=True)

    # --- OBV (On-Balance Volume) ---
    df['OBV'] = (np.sign(df['close'].diff()) * df['volume']).fillna(0).cumsum()

    # --- ADX ---
    df['plus_dm'] = df['high'].diff()
    df['minus_dm'] = df['low'].diff() * -1
    df['plus_dm'] = np.where((df['plus_dm'] > df['minus_dm']) & (df['plus_dm'] > 0), df['plus_dm'], 0)
    df['minus_dm'] = np.where((df['minus_dm'] > df['plus_dm']) & (df['minus_dm'] > 0), df['minus_dm'], 0)
    df['TR'] = df[['high','low','close']].apply(lambda x: max(x['high']-x['low'], abs(x['high']-x['close']), abs(x['low']-x['close'])), axis=1)
    df['plus_di'] = 100 * (df['plus_dm'].rolling(14).sum() / df['TR'].rolling(14).sum())
    df['minus_di'] = 100 * (df['minus_dm'].rolling(14).sum() / df['TR'].rolling(14).sum())
    df['DX'] = (abs(df['plus_di'] - df['minus_di']) / (df['plus_di'] + df['minus_di'])) * 100
    df['ADX_14'] = df['DX'].rolling(14).mean()
    df.drop(['plus_dm','minus_dm','TR','plus_di','minus_di','DX'], axis=1, inplace=True)

    # --- CCI ---
    tp = (df['high'] + df['low'] + df['close']) / 3
    cci = (tp - tp.rolling(20).mean()) / (0.015 * tp.rolling(20).std())
    df['CCI_20'] = cci

    # --- Momentum ---
    df['MOM_10'] = df['close'] - df['close'].shift(10)

    return df
