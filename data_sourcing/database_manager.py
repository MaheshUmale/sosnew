import sqlite3
import pandas as pd
from datetime import datetime

class DatabaseManager:
    def __init__(self, db_name='sos_master_data.db'):
        self.db_name = db_name
        self.conn = None

    def __enter__(self):
        self.conn = sqlite3.connect(self.db_name)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            self.conn.close()

    def _execute_query(self, query, params=(), commit=False):
        with self as db:
            cursor = db.conn.cursor()
            cursor.execute(query, params)
            if commit:
                db.conn.commit()
            return cursor

    def initialize_database(self):
        # Create historical_candles table
        self._execute_query('''
            CREATE TABLE IF NOT EXISTS historical_candles (
                symbol TEXT,
                exchange TEXT,
                interval TEXT,
                timestamp DATETIME,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume INTEGER,
                oi INTEGER,
                PRIMARY KEY (symbol, exchange, interval, timestamp)
            )
        ''', commit=True)

        # Create option_chain_data table
        self._execute_query('''
            CREATE TABLE IF NOT EXISTS option_chain_data (
                symbol TEXT,
                timestamp DATETIME,
                strike REAL,
                call_oi_chg INTEGER,
                put_oi_chg INTEGER,
                call_instrument_key TEXT,
                put_instrument_key TEXT,
                PRIMARY KEY (symbol, timestamp, strike)
            )
        ''', commit=True)

        # Create instrument_master table
        self._execute_query('''
            CREATE TABLE IF NOT EXISTS instrument_master (
                trading_symbol TEXT PRIMARY KEY,
                instrument_key TEXT,
                segment TEXT,
                name TEXT
            )
        ''', commit=True)

    def store_historical_candles(self, symbol, exchange, interval, candles_df):
        """
        Stores historical candle data in the database.
        Uses INSERT OR REPLACE to handle duplicate entries based on the primary key.
        """
        from SymbolMaster import MASTER as SymbolMaster
        instrument_key = SymbolMaster.get_upstox_key(symbol)
        if not instrument_key:
            instrument_key = symbol # Fallback for symbols not in master

        with self as db:
            df_to_insert = candles_df.copy()
            df_to_insert['symbol'] = instrument_key
            df_to_insert['exchange'] = exchange
            df_to_insert['interval'] = interval

            # Ensure timestamp column is truncated to the minute for consistent 1m candles
            df_to_insert['timestamp'] = pd.to_datetime(df_to_insert['timestamp']).apply(lambda dt: dt.replace(second=0, microsecond=0))
            # Format for SQLite
            df_to_insert['timestamp'] = df_to_insert['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')

            if 'oi' not in df_to_insert.columns:
                df_to_insert['oi'] = 0 # Default OI to 0 if not provided

            # Reorder columns to match the table schema for executemany
            table_cols = ['symbol', 'exchange', 'interval', 'timestamp', 'open', 'high', 'low', 'close', 'volume', 'oi']
            df_to_insert = df_to_insert[table_cols]

            # Create the INSERT OR REPLACE statement
            insert_query = f"INSERT OR REPLACE INTO historical_candles ({', '.join(table_cols)}) VALUES ({','.join(['?']*len(table_cols))})"

            # Execute using executemany
            cursor = db.conn.cursor()
            cursor.executemany(insert_query, df_to_insert.to_records(index=False))
            db.conn.commit()

    def get_historical_candles(self, symbol, exchange, interval, from_date, to_date):
        from SymbolMaster import MASTER as SymbolMaster
        instrument_key = SymbolMaster.get_upstox_key(symbol)
        if not instrument_key:
            instrument_key = symbol # Fallback

        # Ensure the date range covers the full day(s) for the database query.
        start_date_str = pd.to_datetime(from_date).strftime('%Y-%m-%d 00:00:00')
        end_date_str = pd.to_datetime(to_date).strftime('%Y-%m-%d 23:59:59')

        with self as db:
            query = """
                SELECT * FROM historical_candles
                WHERE symbol = ? AND exchange = ? AND interval = ? AND timestamp BETWEEN ? AND ?
            """
            return pd.read_sql_query(query, db.conn, params=(instrument_key, exchange, interval, start_date_str, end_date_str))

    def store_option_chain(self, symbol, option_chain_df, date=None):
        with self as db:
            target_date = datetime.strptime(date, '%Y-%m-%d') if date else datetime.now()
            date_str = target_date.strftime('%Y-%m-%d')

            # Start a transaction
            cursor = db.conn.cursor()
            cursor.execute('BEGIN TRANSACTION')

            try:
                # Delete old option chain data for the target day
                delete_query = "DELETE FROM option_chain_data WHERE symbol = ? AND DATE(timestamp) = ?"
                cursor.execute(delete_query, (symbol, date_str))

                # Insert new data
                df_to_insert = option_chain_df.copy()
                df_to_insert['symbol'] = symbol
                # Use the target date for the timestamp, preserving the time if it exists, or setting it to a default time
                df_to_insert['timestamp'] = target_date.replace(hour=15, minute=30, second=0, microsecond=0)

                df_to_insert.to_sql('option_chain_data', db.conn, if_exists='append', index=False)

                # Commit the transaction
                db.conn.commit()
            except Exception as e:
                # Rollback the transaction if an error occurs
                db.conn.rollback()
                print(f"Error storing option chain for {symbol}: {e}")

    def get_option_chain(self, symbol, for_date):
        with self as db:
            query = "SELECT * FROM option_chain_data WHERE symbol = ? AND DATE(timestamp) = ?"
            return pd.read_sql_query(query, db.conn, params=(symbol, for_date))

    def get_instrument_master(self):
        with self as db:
            query = "SELECT * FROM instrument_master"
            return pd.read_sql_query(query, db.conn)

    def store_instrument_master(self, df):
        with self as db:
            df.to_sql('instrument_master', db.conn, if_exists='replace', index=False)
