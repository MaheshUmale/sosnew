import pandas as pd
import logging
from typing import Optional, Dict, Any, List
from functools import lru_cache
from datetime import datetime
from data_sourcing.database_manager import DatabaseManager
from python_engine.utils.symbol_master import MASTER as SymbolMaster

# Standardized Logging
logger = logging.getLogger(__name__)

class DataRepository:
    """
    Unified Data Access Layer for high-performance retrieval and caching.

    This repository abstracts all SQLite I/O and implements metadata caching
    to reduce database overhead during low-latency trading loops.
    """

    _instance = None
    _meta_cache: Dict[str, Any] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DataRepository, cls).__new__(cls)
            cls._instance.db = DatabaseManager()
            cls._instance.db.initialize_database()
        return cls._instance

    def get_historical_candles(self, symbol: str, exchange: str = 'NSE',
                               interval: str = '1m', from_date: Optional[str] = None,
                               to_date: Optional[str] = None) -> Optional[pd.DataFrame]:
        """
        Retrieves historical candles from the database.

        Args:
            symbol (str): Ticker symbol.
            exchange (str): Exchange code.
            interval (str): Candle interval (e.g., '1m').
            from_date (Optional[str]): Start date.
            to_date (Optional[str]): End date.

        Returns:
            Optional[pd.DataFrame]: Candle data or None if not found.
        """
        try:
            canonical_symbol = SymbolMaster.get_canonical_ticker(symbol)
            df = self.db.get_historical_candles(canonical_symbol, exchange, interval, from_date, to_date)
            if df is not None and not df.empty:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                return df.sort_values('timestamp')
        except Exception as e:
            logger.error(f"Error fetching historical candles for {symbol}: {e}")
        return None

    def get_market_stats(self, symbol: str, from_ts: str, to_ts: str) -> pd.DataFrame:
        """
        Retrieves market stats (PCR, Trend) for a given range.

        Args:
            symbol (str): Canonical symbol.
            from_ts (str): Start timestamp.
            to_ts (str): End timestamp.

        Returns:
            pd.DataFrame: Market stats data.
        """
        try:
            return self.db.get_market_stats(symbol, from_ts, to_ts)
        except Exception as e:
            logger.error(f"Error fetching market stats for {symbol}: {e}")
            return pd.DataFrame()

    def get_option_chain(self, symbol: str, date_str: str) -> Optional[List[Dict[str, Any]]]:
        """
        Retrieves option chain snapshot for a specific date.

        Args:
            symbol (str): Canonical symbol.
            date_str (str): Target date (YYYY-MM-DD).

        Returns:
            Optional[List[Dict[str, Any]]]: List of option strike records.
        """
        try:
            df = self.db.get_option_chain(symbol, date_str)
            if df is not None and not df.empty:
                return df.to_dict('records')
        except Exception as e:
            logger.error(f"Error fetching option chain for {symbol} on {date_str}: {e}")
        return None

    @lru_cache(maxsize=1024)
    def get_closest_stats(self, symbol: str, timestamp: datetime) -> Optional[Dict[str, Any]]:
        """
        Fetches the market stats snapshot closest to the given timestamp.
        Implements LRU caching for high-frequency backtest lookups.

        Args:
            symbol (str): Canonical symbol.
            timestamp (datetime): Target timestamp.

        Returns:
            Optional[Dict[str, Any]]: The closest market stats record.
        """
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

    def clear_cache(self) -> None:
        """Clears the internal retrieval caches."""
        self.get_closest_stats.cache_clear()
