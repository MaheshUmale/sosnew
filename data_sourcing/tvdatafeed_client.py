from data_sourcing.tvdatafeed.main import TvDatafeed, Interval

class TVDatafeedClient:
    def __init__(self, username=None, password=None):
        try:
            self.tv = TvDatafeed(username, password)
        except Exception as e:
            print(f"[TVDatafeed] Failed to initialize: {e}")
            self.tv = None

    def get_historical_data(self, symbol, exchange, interval, n_bars):
        if not self.tv:
            return None
        try:
            return self.tv.get_hist(
                symbol=symbol,
                exchange=exchange,
                interval=interval,
                n_bars=n_bars
            )
        except Exception as e:
            print(f"[TVDatafeed] Error fetching historical data for {symbol}: {e}")
            return None
