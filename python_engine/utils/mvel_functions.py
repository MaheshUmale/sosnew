import math
import statistics

def _extract_last_n(history, n, field):
    sub_list = history[-n:]
    return [getattr(bar, field.lower(), 0.0) for bar in sub_list]

def stdev(history, period, field):
    if len(history) < 2:
        return 0.0
    values = _extract_last_n(history, period, field)
    return statistics.stdev(values) if len(values) > 1 else 0.0

def highest(history, period, field):
    if not history:
        return 0.0
    values = _extract_last_n(history, period, field)
    return max(values) if values else 0.0

def lowest(history, period, field):
    if not history:
        return 0.0
    values = _extract_last_n(history, period, field)
    return min(values) if values else 0.0

def moving_avg(history, period, field):
    if not history:
        return 0.0
    values = _extract_last_n(history, period, field)
    return statistics.mean(values) if values else 0.0

def ema(history, period, field):
    if not history:
        return 0.0
    values = _extract_last_n(history, min(len(history), period * 2), field)
    if not values:
        return 0.0
    alpha = 2 / (period + 1)
    ema_val = values[0]
    for val in values[1:]:
        ema_val = val * alpha + ema_val * (1 - alpha)
    return ema_val

def vwap(history):
    if not history:
        return 0.0
    total_pv = 0.0
    total_v = 0.0
    # VWAP is usually reset daily, but for historical context we can calculate over window
    # Assuming history passed is for the current day
    for bar in history:
        tp = (bar.high + bar.low + bar.close) / 3.0
        total_pv += tp * bar.volume
        total_v += bar.volume
    return total_pv / total_v if total_v > 0 else history[-1].close

def rsi(history, period=14):
    if len(history) < period:
        return 50.0
    closes = _extract_last_n(history, period + 1, 'close')
    gains = []
    losses = []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i-1]
        if diff > 0:
            gains.append(diff)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(diff))
    
    avg_gain = statistics.mean(gains)
    avg_loss = statistics.mean(losses)
    
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))

def bb_upper(history, period=20, mult=2.0):
    if len(history) < period:
        return 0.0
    ma = moving_avg(history, period, 'close')
    sd = stdev(history, period, 'close')
    return ma + (mult * sd)

def bb_lower(history, period=20, mult=2.0):
    if len(history) < period:
        return 0.0
    ma = moving_avg(history, period, 'close')
    sd = stdev(history, period, 'close')
    return ma - (mult * sd)

MVEL_FUNCTIONS = {
    "abs": abs,
    "round": round,
    "stdev": stdev,
    "highest": highest,
    "max": highest,
    "lowest": lowest,
    "min": lowest,
    "moving_avg": moving_avg,
    "sma": moving_avg,
    "ema": ema,
    "vwap": vwap,
    "rsi": rsi,
    "bb_upper": bb_upper,
    "bb_lower": bb_lower,
    "high_wick": lambda candle: (candle.high - max(candle.open, candle.close)),
    "low_wick": lambda candle: (min(candle.open, candle.close) - candle.low),
    "body_size": lambda candle: abs(candle.open - candle.close),
    "candle_size": lambda candle: (candle.high - candle.low),
}
