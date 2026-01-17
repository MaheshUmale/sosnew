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
                expiry TEXT,
                call_oi_chg INTEGER,
                put_oi_chg INTEGER,
                call_instrument_key TEXT,
                put_instrument_key TEXT,
                call_oi REAL,
                put_oi REAL,
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

        # Create holidays table
        self._execute_query('''
            CREATE TABLE IF NOT EXISTS holidays (
                holiday_date TEXT PRIMARY KEY
            )
        ''', commit=True)

        # Create market_stats table for enriched data
        self._execute_query('''
            CREATE TABLE IF NOT EXISTS market_stats (
                symbol TEXT,
                timestamp DATETIME,
                pcr REAL,
                pcr_velocity REAL,
                advances INTEGER,
                declines INTEGER,
                oi_wall_above REAL,
                oi_wall_below REAL,
                PRIMARY KEY (symbol, timestamp)
            )
        ''', commit=True)

        # Create trades table
        self._execute_query('''
            CREATE TABLE IF NOT EXISTS trades (
                trade_id TEXT PRIMARY KEY,
                pattern_id TEXT,
                symbol TEXT,
                side TEXT,
                entry_time DATETIME,
                entry_price REAL,
                exit_time DATETIME,
                exit_price REAL,
                stop_loss REAL,
                take_profit REAL,
                outcome TEXT,
                pnl REAL
            )
        ''', commit=True)

    def store_trade(self, trade_data: dict):
        """
        Stores or updates a trade in the database.
        """
        query = '''
            INSERT OR REPLACE INTO trades (
                trade_id, pattern_id, symbol, side, entry_time, entry_price,
                exit_time, exit_price, stop_loss, take_profit, outcome, pnl
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        '''
        params = (
            trade_data.get('trade_id'),
            trade_data.get('pattern_id'),
            trade_data.get('symbol'),
            trade_data.get('side'),
            trade_data.get('entry_time'),
            trade_data.get('entry_price'),
            trade_data.get('exit_time'),
            trade_data.get('exit_price'),
            trade_data.get('stop_loss'),
            trade_data.get('take_profit'),
            trade_data.get('outcome'),
            trade_data.get('pnl')
        )
        self._execute_query(query, params, commit=True)

    def store_historical_candles(self, symbol, exchange, interval, candles_df):
        """
        Stores historical candle data in the database.
        Uses INSERT OR REPLACE to handle duplicate entries based on the primary key.
        """
        from SymbolMaster import MASTER as SymbolMaster
        instrument_key = SymbolMaster.get_upstox_key(symbol)
        if not instrument_key:
            instrument_key = symbol  # Fallback for symbols not in master

        with self as db:
            df_to_insert = candles_df.copy()
            df_to_insert['symbol'] = instrument_key
            df_to_insert['exchange'] = exchange
            df_to_insert['interval'] = interval

            # Data Type Coercion and Formatting
            df_to_insert['timestamp'] = pd.to_datetime(df_to_insert['timestamp']).dt.strftime('%Y-%m-%d %H:%M:%S')
            if 'oi' not in df_to_insert.columns:
                df_to_insert['oi'] = 0
            df_to_insert['oi'] = pd.to_numeric(df_to_insert['oi'], errors='coerce').fillna(0).astype(int)
            for col in ['open', 'high', 'low', 'close']:
                 df_to_insert[col] = pd.to_numeric(df_to_insert[col], errors='coerce')
            df_to_insert['volume'] = pd.to_numeric(df_to_insert['volume'], errors='coerce').fillna(0).astype(int)


            table_cols = ['symbol', 'exchange', 'interval', 'timestamp', 'open', 'high', 'low', 'close', 'volume', 'oi']
            df_to_insert = df_to_insert[table_cols]

            try:
                # Use to_sql with a temporary table for robust insertion
                df_to_insert.to_sql('temp_historical_candles', db.conn, if_exists='replace', index=False)

                # Use INSERT OR REPLACE to merge data from the temp table
                merge_query = f"""
                    INSERT OR REPLACE INTO historical_candles ({', '.join(table_cols)})
                    SELECT {', '.join(table_cols)} FROM temp_historical_candles
                """
                db.conn.execute(merge_query)
                db.conn.commit()

            except Exception as e:
                print(f"Error storing historical candles for {symbol}: {e}")
                db.conn.rollback()
            finally:
                # Clean up the temporary table
                db.conn.execute("DROP TABLE IF EXISTS temp_historical_candles")

    def get_historical_candles(self, symbol, exchange, interval, from_date, to_date):
        from SymbolMaster import MASTER as SymbolMaster
        instrument_key = SymbolMaster.get_upstox_key(symbol)
        if not instrument_key:
            instrument_key = symbol # Fallback

        # Ensure the date range covers the specific time if provided
        ts = pd.to_datetime(from_date)
        if ts.hour == 0 and ts.minute == 0 and ts.second == 0:
             start_date_str = ts.strftime('%Y-%m-%d 00:00:00')
        else:
             start_date_str = ts.strftime('%Y-%m-%d %H:%M:%S')

        ts_end = pd.to_datetime(to_date)
        if ts_end.hour == 0 and ts_end.minute == 0 and ts_end.second == 0:
             end_date_str = ts_end.strftime('%Y-%m-%d 23:59:59')
        else:
             end_date_str = ts_end.strftime('%Y-%m-%d %H:%M:%S')

        with self as db:
            query = """
                SELECT * FROM historical_candles
                WHERE symbol = ? AND exchange = ? AND interval = ? AND timestamp BETWEEN ? AND ?
                ORDER BY timestamp DESC
            """
            return pd.read_sql_query(query, db.conn, params=(instrument_key, exchange, interval, start_date_str, end_date_str))

    def store_option_chain(self, symbol, option_chain_df, date=None):
        with self as db:
            # If date is provided, use it for deletion scope
            date_str = date if date else datetime.now().strftime('%Y-%m-%d')

            try:
                # If we are storing a snapshot with a specific timestamp, we shouldn't wipe the whole day!
                # Logic: If dataframe has 'timestamp' column, assume it's a multi-snapshot or specific snapshot insert.
                # If not, assume it's a legacy daily snapshot and use 'date' or now.

                df_to_insert = option_chain_df.copy()
                df_to_insert['symbol'] = symbol

                if 'timestamp' not in df_to_insert.columns:
                     target_date = datetime.strptime(date, '%Y-%m-%d') if date else datetime.now()
                     df_to_insert['timestamp'] = target_date.strftime('%Y-%m-%d %H:%M:%S')
                     
                     # Only delete existing data if we are overwriting the "daily" snapshot logic
                     # But for backfill, this is risky.
                     # Let's just append. PRIMARY KEY conflict will handle duplicates (if using proper connection setting)
                     # But to be safe and match previous logic:
                     delete_query = "DELETE FROM option_chain_data WHERE symbol = ? AND (timestamp LIKE ? OR timestamp LIKE ?)"
                     db.conn.execute(delete_query, (symbol, f"{date_str}%", f"{date_str}%"))

                print(f"[DatabaseManager] Inserting {len(df_to_insert)} rows into option_chain_data for {symbol}")
                # Use 'append' to avoid wiping other snapshots for the same day
                df_to_insert.to_sql('option_chain_data', db.conn, if_exists='append', index=False)
                db.conn.commit()
            except Exception as e:
                # print(f"Error storing option chain for {symbol}: {e}")
                # Suppress unique constraint errors if we are just overlapping
                pass

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

    def store_holidays(self, holiday_list):
        with self as db:
            cursor = db.conn.cursor()
            for h in holiday_list:
                cursor.execute("INSERT OR IGNORE INTO holidays (holiday_date) VALUES (?)", (h,))
            db.conn.commit()

    def get_holidays(self):
        with self as db:
            cursor = db.conn.cursor()
            cursor.execute("SELECT holiday_date FROM holidays")
            return [row[0] for row in cursor.fetchall()]

    def store_market_stats(self, symbol, stats_df):
        """
        Stores enriched market statistics in the database.
        """
        with self as db:
            df_to_insert = stats_df.copy()
            df_to_insert['symbol'] = symbol

            # Ensure timestamp format
            if 'timestamp' in df_to_insert.columns:
                df_to_insert['timestamp'] = pd.to_datetime(df_to_insert['timestamp']).dt.strftime('%Y-%m-%d %H:%M:%S')

            try:
                df_to_insert.to_sql('temp_market_stats', db.conn, if_exists='replace', index=False)

                cols = ['symbol', 'timestamp', 'pcr', 'pcr_velocity', 'advances', 'declines', 'oi_wall_above', 'oi_wall_below']
                # filter columns that exist in df
                actual_cols = [c for c in cols if c in df_to_insert.columns]

                merge_query = f"""
                    INSERT OR REPLACE INTO market_stats ({', '.join(actual_cols)})
                    SELECT {', '.join(actual_cols)} FROM temp_market_stats
                """
                db.conn.execute(merge_query)
                db.conn.commit()
            except Exception as e:
                print(f"Error storing market stats for {symbol}: {e}")
                db.conn.rollback()
            finally:
                db.conn.execute("DROP TABLE IF EXISTS temp_market_stats")

    def get_market_stats(self, symbol, from_date, to_date):
        """
        Retrieves market statistics for a given symbol and date range.
        """
        start_date_str = pd.to_datetime(from_date).strftime('%Y-%m-%d 00:00:00')
        end_date_str = pd.to_datetime(to_date).strftime('%Y-%m-%d 23:59:59')

        with self as db:
            query = """
                SELECT * FROM market_stats
                WHERE symbol = ? AND timestamp BETWEEN ? AND ?
                ORDER BY timestamp ASC
            """
            return pd.read_sql_query(query, db.conn, params=(symbol, start_date_str, end_date_str))
