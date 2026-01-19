import sqlite3
import pandas as pd
from datetime import datetime
import threading

class DatabaseManager:
    def __init__(self, db_name='sos_master_data.db'):
        self.db_name = db_name
        self._local = threading.local()

    @property
    def conn(self):
        return getattr(self._local, 'conn', None)

    @conn.setter
    def conn(self, value):
        self._local.conn = value

    def _normalize_df_timestamps(self, df, column='timestamp'):
        """Normalizes timestamps in a DataFrame to the nearest minute (seconds=00)."""
        if df is None or df.empty or column not in df.columns:
            return df
        df[column] = pd.to_datetime(df[column]).dt.floor('min').dt.strftime('%Y-%m-%d %H:%M:%S')
        return df

    def _normalize_timestamp(self, ts, floor=True):
        """Normalizes a single timestamp string or datetime object."""
        if not ts: return ts
        dt = pd.to_datetime(ts)
        # If it's a date-only (00:00:00), we should treat it as start/end of day
        if dt.hour == 0 and dt.minute == 0 and dt.second == 0:
            if floor:
                return dt.strftime('%Y-%m-%d 00:00:00')
            else:
                return dt.strftime('%Y-%m-%d 23:59:59')

        if floor:
            return dt.floor('min').strftime('%Y-%m-%d %H:%M:%S')
        else:
            # For end of range, we might want to include the whole minute
            return dt.floor('min').replace(second=59).strftime('%Y-%m-%d %H:%M:%S')

    def __enter__(self):
        # Using check_same_thread=False with thread-local storage provides maximum compatibility
        self.conn = sqlite3.connect(self.db_name, check_same_thread=False)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            self.conn.close()
            self.conn = None

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
                call_ltp REAL,
                put_ltp REAL,
                call_iv REAL,
                put_iv REAL,
                call_delta REAL,
                put_delta REAL,
                call_theta REAL,
                put_theta REAL,
                call_trend TEXT,
                put_trend TEXT,
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
                call_oi REAL,
                put_oi REAL,
                smart_trend TEXT,
                PRIMARY KEY (symbol, timestamp)
            )
        ''', commit=True)

        # Create trades table
        self._execute_query('''
            CREATE TABLE IF NOT EXISTS trades (
                trade_id TEXT PRIMARY KEY,
                pattern_id TEXT,
                symbol TEXT,
                instrument_key TEXT,
                side TEXT,
                entry_time DATETIME,
                entry_price REAL,
                exit_time DATETIME,
                exit_price REAL,
                stop_loss REAL,
                take_profit REAL,
                sl_price REAL,
                tp_price REAL,
                quantity INTEGER,
                status TEXT DEFAULT 'OPEN',
                exit_reason TEXT,
                outcome TEXT,
                pnl REAL
            )
        ''', commit=True)

        # Migration: Ensure tables have latest columns
        self._run_migrations()

    def _run_migrations(self):
        """Ensures that all required columns exist in tables for users with older DB versions."""
        try:
            with self as db:
                cursor = db.conn.cursor()

                # 1. Check option_chain_data
                cursor.execute("PRAGMA table_info(option_chain_data)")
                oc_columns = [info[1] for info in cursor.fetchall()]
                new_oc_cols = {
                    'call_ltp': 'REAL', 'put_ltp': 'REAL',
                    'call_iv': 'REAL', 'put_iv': 'REAL',
                    'call_delta': 'REAL', 'put_delta': 'REAL',
                    'call_theta': 'REAL', 'put_theta': 'REAL',
                    'call_trend': 'TEXT', 'put_trend': 'TEXT'
                }
                for col, dtype in new_oc_cols.items():
                    if col not in oc_columns:
                        print(f"[DatabaseManager] Migrating option_chain_data: adding {col} column")
                        db.conn.execute(f"ALTER TABLE option_chain_data ADD COLUMN {col} {dtype}")

                # 2. Check market_stats
                cursor.execute("PRAGMA table_info(market_stats)")
                ms_columns = [info[1] for info in cursor.fetchall()]
                new_ms_cols = {
                    'call_oi': 'REAL',
                    'put_oi': 'REAL',
                    'smart_trend': 'TEXT',
                    'pcr_velocity': 'REAL'
                }
                for col, dtype in new_ms_cols.items():
                    if col not in ms_columns:
                        print(f"[DatabaseManager] Migrating market_stats: adding {col} column")
                        db.conn.execute(f"ALTER TABLE market_stats ADD COLUMN {col} {dtype}")

                # 3. Check trades
                cursor.execute("PRAGMA table_info(trades)")
                tr_columns = [info[1] for info in cursor.fetchall()]
                new_tr_cols = {
                    'instrument_key': 'TEXT',
                    'sl_price': 'REAL',
                    'tp_price': 'REAL',
                    'quantity': 'INTEGER',
                    'status': "TEXT DEFAULT 'OPEN'",
                    'exit_reason': 'TEXT'
                }
                for col, dtype in new_tr_cols.items():
                    if col not in tr_columns:
                        print(f"[DatabaseManager] Migrating trades: adding {col} column")
                        db.conn.execute(f"ALTER TABLE trades ADD COLUMN {col} {dtype}")

                db.conn.commit()
        except Exception as e:
            print(f"[DatabaseManager] Migration failed: {e}")

    def store_trade(self, trade_data: dict):
        """
        Stores or updates a trade in the database.
        """
        query = '''
            INSERT OR REPLACE INTO trades (
                trade_id, pattern_id, symbol, instrument_key, side, entry_time, entry_price,
                exit_time, exit_price, stop_loss, take_profit, sl_price, tp_price,
                quantity, status, exit_reason, outcome, pnl
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        '''
        params = (
            trade_data.get('trade_id'),
            trade_data.get('pattern_id'),
            trade_data.get('symbol'),
            trade_data.get('instrument_key'),
            trade_data.get('side'),
            trade_data.get('entry_time'),
            trade_data.get('entry_price'),
            trade_data.get('exit_time'),
            trade_data.get('exit_price'),
            trade_data.get('stop_loss'),
            trade_data.get('take_profit'),
            trade_data.get('sl_price'),
            trade_data.get('tp_price'),
            trade_data.get('quantity'),
            trade_data.get('status', 'OPEN'),
            trade_data.get('exit_reason'),
            trade_data.get('outcome'),
            trade_data.get('pnl')
        )
        self._execute_query(query, params, commit=True)

    def store_historical_candles(self, symbol, exchange, interval, candles_df):
        """
        Stores historical candle data in the database.
        Uses INSERT OR REPLACE to handle duplicate entries based on the primary key.
        """
        from python_engine.utils.symbol_master import MASTER as SymbolMaster
        instrument_key = SymbolMaster.get_upstox_key(symbol)
        if not instrument_key:
            instrument_key = symbol  # Fallback for symbols not in master

        with self as db:
            df_to_insert = candles_df.copy()
            df_to_insert['symbol'] = instrument_key
            df_to_insert['exchange'] = exchange
            df_to_insert['interval'] = interval

            # Data Type Coercion and Formatting
            df_to_insert = self._normalize_df_timestamps(df_to_insert)
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

                # Compatible Upsert Pattern (Works on SQLite < 3.24)
                # 1. Update existing rows with data from temp table
                # We protect OI and Volume by only updating them if the new value is > 0
                update_query = f"""
                    UPDATE historical_candles
                    SET
                        open = (SELECT t.open FROM temp_historical_candles t WHERE t.symbol = historical_candles.symbol AND t.exchange = historical_candles.exchange AND t.interval = historical_candles.interval AND t.timestamp = historical_candles.timestamp),
                        high = (SELECT t.high FROM temp_historical_candles t WHERE t.symbol = historical_candles.symbol AND t.exchange = historical_candles.exchange AND t.interval = historical_candles.interval AND t.timestamp = historical_candles.timestamp),
                        low = (SELECT t.low FROM temp_historical_candles t WHERE t.symbol = historical_candles.symbol AND t.exchange = historical_candles.exchange AND t.interval = historical_candles.interval AND t.timestamp = historical_candles.timestamp),
                        close = (SELECT t.close FROM temp_historical_candles t WHERE t.symbol = historical_candles.symbol AND t.exchange = historical_candles.exchange AND t.interval = historical_candles.interval AND t.timestamp = historical_candles.timestamp),
                        volume = COALESCE((SELECT t.volume FROM temp_historical_candles t WHERE t.symbol = historical_candles.symbol AND t.exchange = historical_candles.exchange AND t.interval = historical_candles.interval AND t.timestamp = historical_candles.timestamp AND t.volume > 0), historical_candles.volume),
                        oi = COALESCE((SELECT t.oi FROM temp_historical_candles t WHERE t.symbol = historical_candles.symbol AND t.exchange = historical_candles.exchange AND t.interval = historical_candles.interval AND t.timestamp = historical_candles.timestamp AND t.oi > 0), historical_candles.oi)
                    WHERE EXISTS (
                        SELECT 1 FROM temp_historical_candles t
                        WHERE t.symbol = historical_candles.symbol AND t.exchange = historical_candles.exchange AND t.interval = historical_candles.interval AND t.timestamp = historical_candles.timestamp
                    )
                """
                db.conn.execute(update_query)

                # 2. Insert new rows that don't exist yet
                insert_query = f"""
                    INSERT OR IGNORE INTO historical_candles ({', '.join(table_cols)})
                    SELECT {', '.join(table_cols)} FROM temp_historical_candles
                """
                db.conn.execute(insert_query)
                db.conn.commit()

            except Exception as e:
                print(f"Error storing historical candles for {symbol}: {e}")
                db.conn.rollback()
            finally:
                # Clean up the temporary table
                db.conn.execute("DROP TABLE IF EXISTS temp_historical_candles")

    def get_historical_candles(self, symbol, exchange, interval, from_date, to_date):
        from python_engine.utils.symbol_master import MASTER as SymbolMaster
        instrument_key = SymbolMaster.get_upstox_key(symbol)
        if not instrument_key:
            instrument_key = symbol # Fallback

        # Ensure the date range covers the specific time if provided
        start_date_str = self._normalize_timestamp(from_date)
        end_date_str = self._normalize_timestamp(to_date, floor=False)

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
                df_to_insert = option_chain_df.copy()
                df_to_insert['symbol'] = symbol

                if 'timestamp' not in df_to_insert.columns:
                     target_date = datetime.strptime(date_str, '%Y-%m-%d')
                     df_to_insert['timestamp'] = target_date.strftime('%Y-%m-%d %H:%M:%S')

                # Ensure timestamp is string for DB comparison and normalized
                df_to_insert = self._normalize_df_timestamps(df_to_insert)

                # Use temp table for merging
                df_to_insert.to_sql('temp_option_chain', db.conn, if_exists='replace', index=False)

                cols = ['symbol', 'timestamp', 'strike', 'expiry', 'call_oi_chg', 'put_oi_chg',
                        'call_instrument_key', 'put_instrument_key', 'call_oi', 'put_oi',
                        'call_ltp', 'put_ltp', 'call_iv', 'put_iv', 'call_delta', 'put_delta',
                        'call_theta', 'put_theta', 'call_trend', 'put_trend']
                actual_cols = [c for c in cols if c in df_to_insert.columns]

                # Compatible Upsert for option_chain_data
                update_query = f"""
                    UPDATE option_chain_data
                    SET {", ".join([f"{c} = (SELECT t.{c} FROM temp_option_chain t WHERE t.symbol = option_chain_data.symbol AND t.timestamp = option_chain_data.timestamp AND t.strike = option_chain_data.strike)" for c in actual_cols if c not in ['symbol', 'timestamp', 'strike']])}
                    WHERE EXISTS (SELECT 1 FROM temp_option_chain t WHERE t.symbol = option_chain_data.symbol AND t.timestamp = option_chain_data.timestamp AND t.strike = option_chain_data.strike)
                """
                db.conn.execute(update_query)

                insert_query = f"""
                    INSERT OR IGNORE INTO option_chain_data ({', '.join(actual_cols)})
                    SELECT {', '.join(actual_cols)} FROM temp_option_chain
                """
                db.conn.execute(insert_query)
                db.conn.commit()
                # print(f"[DatabaseManager] Stored {len(df_to_insert)} rows into option_chain_data for {symbol}")
            except Exception as e:
                print(f"Error storing option chain for {symbol}: {e}")
                db.conn.rollback()
            finally:
                db.conn.execute("DROP TABLE IF EXISTS temp_option_chain")

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
            # DON'T NORMALIZE if it's already string formatted from outside to avoid floor(min) issues if it was already floored
            # df_to_insert = self._normalize_df_timestamps(df_to_insert)

            try:
                df_to_insert.to_sql('temp_market_stats', db.conn, if_exists='replace', index=False)

                cols = ['symbol', 'timestamp', 'pcr', 'pcr_velocity', 'advances', 'declines', 'oi_wall_above', 'oi_wall_below', 'call_oi', 'put_oi', 'smart_trend']
                # filter columns that exist in df
                actual_cols = [c for c in cols if c in df_to_insert.columns]

                update_query = f"""
                    UPDATE market_stats
                    SET {", ".join([f"{c} = (SELECT t.{c} FROM temp_market_stats t WHERE t.symbol = market_stats.symbol AND t.timestamp = market_stats.timestamp)" for c in actual_cols if c not in ['symbol', 'timestamp']])}
                    WHERE EXISTS (SELECT 1 FROM temp_market_stats t WHERE t.symbol = market_stats.symbol AND t.timestamp = market_stats.timestamp)
                """
                db.conn.execute(update_query)

                insert_query = f"""
                    INSERT OR IGNORE INTO market_stats ({', '.join(actual_cols)})
                    SELECT {', '.join(actual_cols)} FROM temp_market_stats
                """
                db.conn.execute(insert_query)
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
        start_date_str = self._normalize_timestamp(from_date)
        end_date_str = self._normalize_timestamp(to_date, floor=False)

        with self as db:
            query = """
                SELECT * FROM market_stats
                WHERE symbol = ? AND timestamp BETWEEN ? AND ?
                ORDER BY timestamp ASC
            """
            return pd.read_sql_query(query, db.conn, params=(symbol, start_date_str, end_date_str))
