import os
import requests
import gzip
import io
import pandas as pd
import time
import threading
from data_sourcing.database_manager import DatabaseManager

class SymbolMaster:
    _instance = None
    _mappings = {}  # { "STANDARD_SYMBOL": "BROKER_KEY" }
    _reverse_mappings = {}  # { "BROKER_KEY": ("STANDARD_SYMBOL", "SEGMENT") }
    _initialized = False
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SymbolMaster, cls).__new__(cls)
            cls._instance.db_manager = DatabaseManager()
        return cls._instance

    def initialize(self):
        with self._lock:
            if self._initialized:
                return

            print("[SymbolMaster] Initializing Instrument Keys...")
        cache_file = "upstox_instruments.json.gz"
        cache_age_seconds = 24 * 60 * 60

        try:
            df_cache = self.db_manager.get_instrument_master()
            if not df_cache.empty:
                print(f"  [INFO] Loading from SQLite cache")
                self._populate_mappings(df_cache)
                self._initialized = True
                return
        except Exception as e:
            print(f"  [WARN] SQLite cache load failed: {e}")

        content = None
        if os.path.exists(cache_file) and (time.time() - os.path.getmtime(cache_file)) < cache_age_seconds:
            with open(cache_file, "rb") as f: content = f.read()
        else:
            try:
                url = "https://assets.upstox.com/market-quote/instruments/exchange/NSE.json.gz"
                response = requests.get(url, timeout=60)
                content = response.content
                with open(cache_file, "wb") as f: f.write(content)
            except Exception as e:
                if os.path.exists(cache_file):
                    with open(cache_file, "rb") as f: content = f.read()

        if content:
            try:
                with gzip.GzipFile(fileobj=io.BytesIO(content)) as f:
                    df = pd.read_json(f)
                self.db_manager.store_instrument_master(df)
                self._populate_mappings(df)
                self._initialized = True
            except Exception as e:
                print(f"  [ERROR] SymbolMaster initialization failed: {e}")

    def _populate_mappings(self, df):
        for _, row in df.iterrows():
            tradingsymbol = row['trading_symbol'].upper()
            instrument_key = row['instrument_key']
            segment = row['segment']
            name = row.get('name', '')

            # Standardize based on OpenAlgo inspiration
            std_symbol = self._standardize(row)

            self._mappings[std_symbol] = instrument_key
            self._mappings[tradingsymbol] = instrument_key # Support legacy/direct lookups
            self._reverse_mappings[instrument_key] = (std_symbol, segment)

            # Special Index Mappings
            if segment == 'NSE_INDEX':
                if name == "Nifty 50":
                    self._mappings["NIFTY"] = instrument_key
                    self._mappings["NSE|INDEX|NIFTY"] = instrument_key
                elif name == "Nifty Bank":
                    self._mappings["BANKNIFTY"] = instrument_key
                    self._mappings["NSE|INDEX|BANKNIFTY"] = instrument_key

    def _standardize(self, row):
        """Standardizes symbol format: [BASE][EXPIRY][STRIKE][TYPE]"""
        segment = row['segment']
        tradingsymbol = row['trading_symbol'].upper()

        if segment == 'NSE_INDEX':
            if row['name'] == "Nifty 50": return "NIFTY"
            if row['name'] == "Nifty Bank": return "BANKNIFTY"
            return tradingsymbol

        # For Options/Futures, we could parse further, but for now tradingsymbol is close to standard
        return tradingsymbol

    def get_upstox_key(self, symbol):
        if not self._initialized: self.initialize()
        if symbol in self._reverse_mappings: return symbol
        s_upper = symbol.upper()

        # Clean common prefixes
        if s_upper.startswith("NSE|INDEX|"): s_upper = s_upper.split('|')[-1]
        elif s_upper.startswith("NSE_INDEX|"): s_upper = s_upper.split('|')[-1]

        if s_upper == "NIFTY 50": s_upper = "NIFTY"
        if s_upper == "NIFTY BANK": s_upper = "BANKNIFTY"

        return self._mappings.get(s_upper)

    def get_canonical_ticker(self, symbol):
        key = self.get_upstox_key(symbol)
        return self.get_ticker_from_key(key) if key else symbol

    def get_ticker_from_key(self, key):
        if not self._initialized: self.initialize()
        if key in self._reverse_mappings:
            std_symbol, segment = self._reverse_mappings[key]
            if segment == 'NSE_INDEX':
                if std_symbol == "NIFTY": return "NSE|INDEX|NIFTY"
                if std_symbol == "BANKNIFTY": return "NSE|INDEX|BANKNIFTY"
            return std_symbol
        return key

MASTER = SymbolMaster()
