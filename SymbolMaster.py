"""
SymbolMaster - Centralized Instrument Key Resolution

This singleton class provides a unified interface for resolving instrument symbols
across different data providers (TradingView, NSE, Upstox).

Key Features:
- Downloads and caches Upstox NSE instrument master (8,792+ instruments)
- Bidirectional mapping: Symbol ↔ Instrument Key
- Special handling for index instruments (NIFTY, BANKNIFTY)

Usage:
    from SymbolMaster import MASTER

    MASTER.initialize()  # Downloads instrument master (one-time)

    # Resolve symbol to Upstox key
    key = MASTER.get_upstox_key("RELIANCE")  # Returns: NSE_EQ|INE002A01018

    # Reverse lookup
    symbol = MASTER.get_ticker_from_key(key)  # Returns: RELIANCE

Architecture:
    - Singleton pattern ensures single download per session
    - Filters for NSE_EQ and NSE_INDEX segments only
    - Caches mappings in-memory for O(1) lookups

Author: Mahesh
Version: 1.0
"""

import sqlite3
import requests
import gzip
import io
import pandas as pd
import os
import time

class SymbolMaster:
    _instance = None
    _mappings = {} # { "RELIANCE": "NSE_EQ|INE002A01018" }
    _reverse_mappings = {} # { "NSE_EQ|INE002A01018": "RELIANCE" }
    _initialized = False

    def __new__(cls):
        """Singleton pattern implementation."""
        if cls._instance is None:
            cls._instance = super(SymbolMaster, cls).__new__(cls)
        return cls._instance

    def _init_sqlite_cache(self):
        """Initialize the SQLite database for instrument mappings."""
        db_path = "sos_master_data.db"
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS instrument_master (
                            trading_symbol TEXT PRIMARY KEY,
                            instrument_key TEXT,
                            segment TEXT,
                            name TEXT
                          )''')
        conn.commit()
        return conn

    def initialize(self):
        """
        Loads instrument keys with multi-level caching (SQLite > Disk GZ > Network).
        """
        if self._initialized:
            return

        import sqlite3
        print("[SymbolMaster] Initializing Instrument Keys...")
        db_path = "sos_master_data.db"
        cache_file = "upstox_instruments.json.gz"
        cache_age_seconds = 24 * 60 * 60  # 24 hours
        
        # 1. Try SQLite Cache first
        try:
            if os.path.exists(db_path):
                conn = sqlite3.connect(db_path)
                df_cache = pd.read_sql_query("SELECT * FROM instrument_master", conn)
                conn.close()
                
                if not df_cache.empty:
                    print(f"  [INFO] Loading from SQLite cache: {db_path}")
                    for _, row in df_cache.iterrows():
                        name = row['trading_symbol'].upper()
                        key = row['instrument_key']
                        segment = row['segment']
                        self._mappings[name] = key
                        self._reverse_mappings[key] = (name, segment)
                        if segment == 'NSE_INDEX':
                            if row['name'] == "Nifty 50": self._mappings["NIFTY"] = key
                            elif row['name'] == "Nifty Bank": self._mappings["BANKNIFTY"] = key
                    
                    print(f"  ✓ Loaded {len(self._mappings)} keys from SQLite.")
                    self._initialized = True
                    return
        except Exception as e:
            print(f"  [WARN] SQLite cache load failed: {e}")

        # 2. Check GZ Cache Validity or Download
        content = None
        if os.path.exists(cache_file) and (time.time() - os.path.getmtime(cache_file)) < cache_age_seconds:
            print(f"  [INFO] Loading from disk GZ cache: {cache_file}")
            with open(cache_file, "rb") as f:
                content = f.read()
        else:
            try:
                print("  [INFO] Fetching fresh instrument master from Upstox...")
                url = "https://assets.upstox.com/market-quote/instruments/exchange/NSE.json.gz"
                response = requests.get(url, timeout=60)
                response.raise_for_status()
                content = response.content
                with open(cache_file, "wb") as f:
                    f.write(content)
            except Exception as e:
                print(f"  [WARN] Download failed: {e}")
                if os.path.exists(cache_file):
                    print(f"  [INFO] Fallback to stale GZ cache: {cache_file}")
                    with open(cache_file, "rb") as f: content = f.read()

        if not content:
            raise Exception("Failed to load instrument master from any source.")

        # 3. Parse and Populate SQLite
        try:
            with gzip.GzipFile(fileobj=io.BytesIO(content)) as f:
                df = pd.read_json(f)

            df_filtered = df[df['segment'].isin(['NSE_EQ', 'NSE_INDEX', 'NSE_FO'])][['trading_symbol', 'instrument_key', 'segment', 'name']].copy()
            
            # Save to SQLite for next time
            conn = self._init_sqlite_cache()
            df_filtered.to_sql('instrument_master', conn, if_exists='replace', index=False)
            conn.close()

            for _, row in df_filtered.iterrows():
                name = row['trading_symbol'].upper()
                key = row['instrument_key']
                segment = row['segment']
                self._mappings[name] = key
                self._reverse_mappings[key] = (name, segment)
                if segment == 'NSE_INDEX':
                    if row['name'] == "Nifty 50": self._mappings["NIFTY"] = key
                    elif row['name'] == "Nifty Bank": self._mappings["BANKNIFTY"] = key

            print(f"  ✓ Parsed and cached {len(self._mappings)} keys to SQLite.")
            self._initialized = True

        except Exception as e:
            print(f"[SymbolMaster] Parsing Failed: {e}")
            raise e

    def get_upstox_key(self, symbol):
        """
        Resolves a trading symbol to its Upstox instrument key.

        Args:
            symbol (str): Trading symbol (e.g., 'RELIANCE', 'NIFTY', 'SBIN')

        Returns:
            str: Upstox instrument key (e.g., 'NSE_EQ|INE002A01018') or None if not found

        Example:
            >>> MASTER.get_upstox_key('RELIANCE')
            'NSE_EQ|INE002A01018'
        """
        if not self._initialized:
            self.initialize()

        # 1. Handle unified format
        s_upper = symbol.upper()
        if s_upper.startswith("NSE|INDEX|"):
            s_upper = s_upper.split('|')[-1]

        # 2. Direct Match
        if s_upper in self._mappings:
            return self._mappings[s_upper]

        return None

    def get_ticker_from_key(self, key):
        """
        Reverse lookup: Upstox instrument key to trading symbol.

        Args:
            key (str): Upstox instrument key (e.g., 'NSE_EQ|INE002A01018')

        Returns:
            str: Trading symbol (unified for indices) or the original key if not found

        Example:
            >>> MASTER.get_ticker_from_key('NSE_INDEX|Nifty 50')
            'NSE|INDEX|NIFTY'
        """
        if not self._initialized:
            self.initialize()
        if key in self._reverse_mappings:
            name, segment = self._reverse_mappings[key]
            if segment == 'NSE_INDEX':
                if name == "Nifty 50":
                    return "NSE|INDEX|NIFTY"
                if name == "NIFTY BANK":
                    return "NSE|INDEX|BANKNIFTY"
            return name

        return key

# Singleton Instance
MASTER = SymbolMaster()
