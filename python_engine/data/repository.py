import pandas as pd
import logging
from datetime import datetime
from data_sourcing.database_manager import DatabaseManager
from python_engine.utils.symbol_master import MASTER as SymbolMaster

logger = logging.getLogger(__name__)

class DataRepository:
    """
    Focused interface for all database retrieval operations.
    No remote fetching logic here.
    """
    def __init__(self):
        self.db = DatabaseManager()
        self.db.initialize_database()

    def get_historical_candles(self, symbol, exchange='NSE', interval='1m', from_date=None, to_date=None):
        try:
            canonical_symbol = SymbolMaster.get_canonical_ticker(symbol)
            df = self.db.get_historical_candles(canonical_symbol, exchange, interval, from_date, to_date)
            if df is not None and not df.empty:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                return df.sort_values('timestamp')
        except Exception as e:
            logger.error(f"Error fetching historical candles for {symbol}: {e}")
        return None

    def get_market_stats(self, symbol, from_ts, to_ts):
        try:
            return self.db.get_market_stats(symbol, from_ts, to_ts)
        except Exception as e:
            logger.error(f"Error fetching market stats for {symbol}: {e}")
            return pd.DataFrame()

    def get_option_chain(self, symbol, date_str):
        try:
            df = self.db.get_option_chain(symbol, date_str)
            if df is not None and not df.empty:
                return df.to_dict('records')
        except Exception as e:
            logger.error(f"Error fetching option chain for {symbol} on {date_str}: {e}")
        return None

    def get_closest_stats(self, symbol, timestamp):
        """Fetches the market stats snapshot closest to the given timestamp."""
        try:
            ts_str = timestamp.strftime('%Y-%m-%d %H:%M:%S')
            date_str = timestamp.strftime('%Y-%m-%d')
            stats = self.db.get_market_stats(symbol, date_str, ts_str)
            if not stats.empty:
                stats['timestamp_dt'] = pd.to_datetime(stats['timestamp'])
                stats['diff'] = (stats['timestamp_dt'] - timestamp).abs()
                return stats.sort_values('diff').iloc[0].to_dict()
        except Exception as e:
            logger.error(f"Error fetching closest stats for {symbol} at {timestamp}: {e}")
        return None
