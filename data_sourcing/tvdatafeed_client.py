try:
    from tvDatafeed import TvDatafeed, Interval
    from python_engine.utils.symbol_converter import upstox_to_tv_option
except ImportError:
    TvDatafeed = None
    Interval = None

class TVDatafeedClient:
    def __init__(self, username=None, password=None):
        try:
            self.tv = TvDatafeed(username, password, auto_login=False)
        except Exception as e:
            print(f"[TVDatafeed] Failed to initialize: {e}")
            self.tv = None

    def get_historical_data(self, symbol, exchange, interval, n_bars):
        if not self.tv:
            return None

        tv_symbol = symbol
        # If it looks like an Upstox option symbol, convert it
        if any(x in symbol.upper() for x in [" CE ", " PE "]):
            tv_symbol = upstox_to_tv_option(symbol)
            print(f"[TVDatafeed] Converted {symbol} -> {tv_symbol}")

        try:
            return self.tv.get_hist(
                symbol=tv_symbol,
                exchange=exchange,
                interval=interval,
                n_bars=n_bars
            )
        except Exception as e:
            print(f"[TVDatafeed] Error fetching historical data for {symbol}: {e}")
            return None
