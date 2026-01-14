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
}
