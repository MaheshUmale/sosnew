import time
import pandas as pd
from datetime import datetime, timedelta
from data_sourcing.data_manager import DataManager
from data_sourcing.database_manager import DatabaseManager
from SymbolMaster import MASTER as SymbolMaster
from engine_config import Config

class IngestionManager:
    def __init__(self, access_token=None):
        if not access_token:
            Config.load('config.json')
            access_token = Config.get('upstox_access_token')

        self.data_manager = DataManager(access_token=access_token)
        self.db_manager = self.data_manager.db_manager

    def ingest_historical_data(self, symbol, from_date, to_date, full_options=False, force=False):
        """
        Comprehensive historical data ingestion:
        1. Index Candles (Upstox)
        2. Index Volume (TVDatafeed)
        3. Option Chains (Trendlyne/Upstox)
        4. Market Stats Calculation (PCR, etc.)
        """
        canonical_symbol = SymbolMaster.get_canonical_ticker(symbol)
        print(f"[*] Starting Ingestion for {canonical_symbol} | {from_date} to {to_date}")

        # 1. Index Candles & Volume
        print("[1/4] Syncing Index Candles...")
        # Use mode='live' to force remote fetch during ingestion
        self.data_manager.get_historical_candles(canonical_symbol, from_date=from_date, to_date=to_date, n_bars=100000, mode='live')

        # 2. Options & Stats
        start_date = datetime.strptime(from_date, '%Y-%m-%d').date()
        end_date = datetime.strptime(to_date, '%Y-%m-%d').date()
        date_range = pd.date_range(start=start_date, end=end_date, freq='B')

        holidays = self.data_manager.holidays

        for target_date in date_range:
            date_str = target_date.strftime('%Y-%m-%d')
            if date_str in holidays:
                continue

            # Check if data already exists for this day
            if not force:
                existing_candles = self.db_manager.get_historical_candles(canonical_symbol, 'NSE', '1m', date_str, date_str)
                if existing_candles is not None and not existing_candles.empty:
                    # Check if stats also exist
                    existing_stats = self.db_manager.get_market_stats(canonical_symbol, date_str, date_str)
                    if not existing_stats.empty:
                        print(f"[*] Skipping {date_str} - Data already exists. Use --force to overwrite.")
                        continue

            print(f"[*] Processing {date_str}...")

            # 1b. Volume from TV
            try:
                from backfill_trendlyne import backfill_index_volume_from_tv
                prefix = "NIFTY" if "NIFTY" in canonical_symbol.upper() and "BANK" not in canonical_symbol.upper() else "BANKNIFTY"
                success = backfill_index_volume_from_tv(self.db_manager, prefix, date_str)
                if not success:
                    print(f"    - [INFO] Index volume not available (TVDatafeed skipped or failed). Index candles will have 0 volume.")
            except Exception as e:
                print(f"    - [WARN] TV Volume sync skipped: {e}")

            # Options Sync
            if full_options:
                print(f"    - Syncing Full-Day Option Chain snapshots...")
                try:
                    from backfill_trendlyne import run_backfill
                    prefix = "NIFTY" if "NIFTY" in canonical_symbol.upper() and "BANK" not in canonical_symbol.upper() else "BANKNIFTY"
                    run_backfill(symbols_list=[prefix], full_run=True, date_override=date_str)

                    # Fix: Also store under canonical name if run_backfill uses prefix
                    with self.db_manager as db:
                        db.conn.execute("INSERT OR REPLACE INTO option_chain_data (symbol, timestamp, strike, expiry, call_oi_chg, put_oi_chg, call_instrument_key, put_instrument_key, call_oi, put_oi) "
                                      "SELECT ?, timestamp, strike, expiry, call_oi_chg, put_oi_chg, call_instrument_key, put_instrument_key, call_oi, put_oi FROM option_chain_data WHERE symbol = ?", (canonical_symbol, prefix))
                        db.conn.commit()

                except Exception as e:
                    print(f"    - [ERROR] run_backfill failed: {e}")
            else:
                print(f"    - Syncing Daily Option Chain snapshot...")
                self.data_manager.get_option_chain(canonical_symbol, date=date_str, mode='live')

            # 3. ATM Option Candles Ingestion
            print(f"    - Syncing ATM Option Candles...")
            self.ingest_atm_option_candles(canonical_symbol, date_str)

            # Enrich Market Stats
            print(f"    - Enriching Market Stats...")
            self.calculate_and_store_stats(canonical_symbol, date_str)

    def ingest_atm_option_candles(self, canonical_symbol, date_str):
        """Fetches historical candles for options that are likely ATM during the day."""
        try:
            # Get index range for the day
            candles = self.data_manager.get_historical_candles(canonical_symbol, from_date=date_str, to_date=date_str, mode='backtest')
            if candles is None or candles.empty: return

            low_strike = self.data_manager.calculate_atm_strike(canonical_symbol, candles['low'].min())
            high_strike = self.data_manager.calculate_atm_strike(canonical_symbol, candles['high'].max())

            strike_step = 100 if "BANK" in canonical_symbol.upper() else 50
            strikes = range(int(low_strike) - strike_step*2, int(high_strike) + strike_step*3, strike_step)

            print(f"      Syncing candles for strikes around {low_strike}-{high_strike}...")

            # We need the instrument keys for these options for this day.
            # If they are missing in option_chain_data (e.g. from Trendlyne), we try to resolve them.
            with self.db_manager as db:
                query = "SELECT DISTINCT strike, expiry, call_instrument_key, put_instrument_key FROM option_chain_data WHERE symbol = ? AND DATE(timestamp) = ? AND strike IN ({})".format(','.join([str(s) for s in strikes]))
                df = pd.read_sql_query(query, db.conn, params=(canonical_symbol, date_str))

            if df.empty:
                print(f"      [WARN] No option chain data found to resolve ATM keys.")
                return

            unique_keys = set()
            symbol_prefix = "BANKNIFTY" if "BANK" in canonical_symbol.upper() else "NIFTY"

            for _, row in df.iterrows():
                if row['call_instrument_key']:
                    unique_keys.add(row['call_instrument_key'])
                if row['put_instrument_key']:
                    unique_keys.add(row['put_instrument_key'])

                # Fallback resolution via symbol construction
                if not row['call_instrument_key'] or not row['put_instrument_key']:
                    if not row['expiry'] or pd.isna(row['expiry']):
                        continue
                    expiry_dt = pd.to_datetime(row['expiry'])
                    expiry_day = expiry_dt.strftime('%d')
                    expiry_month = expiry_dt.strftime('%b').upper()
                    expiry_year = expiry_dt.strftime('%y')

                    for opt_type in ['CE', 'PE']:
                        tsym = f"{symbol_prefix} {int(row['strike'])} {opt_type} {expiry_day} {expiry_month} {expiry_year}"
                        key = SymbolMaster.get_upstox_key(tsym)
                        if key: unique_keys.add(key)

            unique_keys.discard('')
            print(f"      Found {len(unique_keys)} unique option keys to fetch.")

            for key in unique_keys:
                if key:
                    try:
                        self.data_manager.get_historical_candles(key, from_date=date_str, to_date=date_str, mode='live')
                    except Exception as e:
                        print(f"      [WARN] Failed to fetch candles for {key}: {e}")
        except Exception as e:
            print(f"      [WARN] Option candles ingestion failed: {e}")

    def calculate_and_store_stats(self, symbol, date_str):
        """
        Calculates PCR and other stats from stored option chain data for a specific day.
        """
        try:
            # Get all option chain snapshots for this day
            with self.db_manager as db:
                query = "SELECT * FROM option_chain_data WHERE symbol = ? AND DATE(timestamp) = ?"
                df = pd.read_sql_query(query, db.conn, params=(symbol, date_str))

            if df.empty:
                print(f"      [WARN] No option chain data found for {symbol} on {date_str}")
                return

            df['timestamp'] = pd.to_datetime(df['timestamp'])

            # Group by timestamp to calculate PCR per minute
            stats_list = []
            for ts, group in df.groupby('timestamp'):
                total_call_oi = group['call_oi'].sum()
                total_put_oi = group['put_oi'].sum()

                pcr = round(total_put_oi / total_call_oi, 2) if total_call_oi > 0 else 1.0

                # Simple OI wall logic
                oi_wall_above = group.loc[group['call_oi'].idxmax()]['strike'] if not group.empty else 0
                oi_wall_below = group.loc[group['put_oi'].idxmax()]['strike'] if not group.empty else 0

                stats_list.append({
                    'timestamp': ts,
                    'pcr': pcr,
                    'oi_wall_above': oi_wall_above,
                    'oi_wall_below': oi_wall_below,
                    'advances': 0, # Placeholder
                    'declines': 0  # Placeholder
                })

            if stats_list:
                stats_df = pd.DataFrame(stats_list)
                self.db_manager.store_market_stats(symbol, stats_df)
                print(f"      [OK] Stored {len(stats_df)} market stats snapshots.")

        except Exception as e:
            print(f"      [ERROR] Stats enrichment failed for {symbol} on {date_str}: {e}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Unified Data Ingestion")
    parser.add_argument("--symbol", type=str, required=True)
    parser.add_argument("--from_date", type=str, required=True)
    parser.add_argument("--to_date", type=str, required=True)
    parser.add_argument("--full-options", action="store_true", help="Fetch 1-min option snapshots (Trendlyne)")
    parser.add_argument("--force", action="store_true", help="Force re-ingestion of data if it exists")

    args = parser.parse_args()

    SymbolMaster.initialize()
    manager = IngestionManager()
    manager.ingest_historical_data(args.symbol, args.from_date, args.to_date, full_options=args.full_options, force=args.force)
