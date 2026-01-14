import pandas as pd

def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Calculates the Average True Range (ATR) for a given DataFrame.
    """
    df_copy = df.copy()
    df_copy['high_low'] = df_copy['high'] - df_copy['low']
    df_copy['high_close'] = (df_copy['high'] - df_copy['close'].shift()).abs()
    df_copy['low_close'] = (df_copy['low'] - df_copy['close'].shift()).abs()

    df_copy['true_range'] = df_copy[['high_low', 'high_close', 'low_close']].max(axis=1)

    atr = df_copy['true_range'].rolling(window=period, min_periods=1).mean()

    return atr
