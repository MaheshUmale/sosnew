import time
import pandas as pd
from datetime import datetime, timedelta
from data_sourcing.data_manager import DataManager
from data_sourcing.database_manager import DatabaseManager
from python_engine.utils.symbol_master import MASTER as SymbolMaster
from python_engine.engine_config import Config
from python_engine.utils.math_engine import MathEngine

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
        # Calculate bars needed based on date range
        start_dt = datetime.strptime(from_date, '%Y-%m-%d')
        end_dt = datetime.strptime(to_date, '%Y-%m-%d')
        days = (end_dt - start_dt).days + 1
        bars_needed = days * 400 # ~375 per day + buffer

        self.data_manager.get_historical_candles(canonical_symbol, from_date=from_date, to_date=to_date, n_bars=bars_needed, mode='live')

        # 2. Options & Stats
        date_range = pd.date_range(start=start_dt.date(), end=end_dt.date(), freq='B')
        holidays = self.data_manager.holidays

        for target_date in date_range:
            date_str = target_date.strftime('%Y-%m-%d')
            if date_str in holidays:
                continue

            # Check if data already exists for this day
            if not force:
                existing_candles = self.db_manager.get_historical_candles(canonical_symbol, 'NSE', '1m', date_str, date_str)
                if existing_candles is not None and not existing_candles.empty:
                    existing_stats = self.db_manager.get_market_stats(canonical_symbol, date_str, date_str)
                    has_oi = (existing_candles['oi'] > 0).any()
                    if not existing_stats.empty and has_oi:
                        print(f"[*] Skipping {date_str} - Data already exists and is enriched. Use --force to overwrite.")
                        continue
                    else:
                        print(f"[*] Data for {date_str} exists but is incomplete (missing OI/Stats). Re-processing...")

            print(f"[*] Processing {date_str}...")

            # 1b. Volume from TV (Only if not already fetched or force)
            try:
                # We use DataManager now instead of importing from backfill_trendlyne
                prefix = "NIFTY" if "NIFTY" in canonical_symbol.upper() and "BANK" not in canonical_symbol.upper() else "BANKNIFTY"
                # DataManager logic handles TVVolume internally if configured
                print(f"    - Checking Index Volume (TVDatafeed)...")
                self.data_manager.get_historical_candles(canonical_symbol, from_date=date_str, to_date=date_str, mode='live')
            except Exception as e:
                print(f"    - [WARN] Volume sync skipped: {e}")

            # Options Sync
            if full_options:
                print(f"    - Syncing Full-Day Option Chain snapshots (Trendlyne)...")
                try:
                    from backfill_trendlyne import run_backfill
                    prefix = "NIFTY" if "NIFTY" in canonical_symbol.upper() and "BANK" not in canonical_symbol.upper() else "BANKNIFTY"
                    run_backfill(symbols_list=[prefix], full_run=True, date_override=date_str)

                    # Ensure data is also under canonical symbol
                    with self.db_manager as ctx:
                        ctx.conn.execute("INSERT OR REPLACE INTO option_chain_data (symbol, timestamp, strike, expiry, call_oi_chg, put_oi_chg, call_instrument_key, put_instrument_key, call_oi, put_oi) "
                                      "SELECT ?, timestamp, strike, expiry, call_oi_chg, put_oi_chg, call_instrument_key, put_instrument_key, call_oi, put_oi FROM option_chain_data WHERE symbol = ?", (canonical_symbol, prefix))
                        ctx.conn.commit()
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

    def ingest_from_mongo_json(self, filepath):
        """Ingests data from a MongoDB JSON file."""
        from data_sourcing.mongo_parser import MongoParser
        parser = MongoParser()
        parser.ingest_from_file(filepath)
        print(f"[IngestionManager] MongoDB data ingestion complete from {filepath}")

    def ingest_from_mongo_db(self, mongo_uri="mongodb://localhost:27017/", db_name="upstox_strategy_db", collection_name="raw_tick_data"):
        """Ingests data directly from a MongoDB instance."""
        from data_sourcing.mongo_parser import MongoParser
        parser = MongoParser(mongo_uri=mongo_uri)
        count = parser.ingest_from_db(db_name=db_name, collection_name=collection_name)
        print(f"[IngestionManager] MongoDB data ingestion complete. Processed {count} snapshots.")

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

            with self.db_manager as db:
                query = "SELECT DISTINCT strike, expiry, call_instrument_key, put_instrument_key FROM option_chain_data WHERE symbol = ? AND DATE(timestamp) = ? AND strike IN ({})".format(','.join([str(s) for s in strikes]))
                df = pd.read_sql_query(query, db.conn, params=(canonical_symbol, date_str))

            if df.empty:
                return

            unique_keys = set()
            symbol_prefix = "BANKNIFTY" if "BANK" in canonical_symbol.upper() else "NIFTY"

            for _, row in df.iterrows():
                if row['call_instrument_key']: unique_keys.add(row['call_instrument_key'])
                if row['put_instrument_key']: unique_keys.add(row['put_instrument_key'])

                # Fallback resolution
                if not row['call_instrument_key'] or not row['put_instrument_key']:
                    if not row['expiry'] or pd.isna(row['expiry']): continue
                    expiry_dt = pd.to_datetime(row['expiry'])
                    expiry_day, expiry_month, expiry_year = expiry_dt.strftime('%d'), expiry_dt.strftime('%b').upper(), expiry_dt.strftime('%y')

                    for opt_type in ['CE', 'PE']:
                        tsym = f"{symbol_prefix} {int(row['strike'])} {opt_type} {expiry_day} {expiry_month} {expiry_year}"
                        key = SymbolMaster.get_upstox_key(tsym)
                        if key: unique_keys.add(key)

            unique_keys.discard('')
            for key in unique_keys:
                if key:
                    try:
                        self.data_manager.get_historical_candles(key, from_date=date_str, to_date=date_str, mode='live')
                    except: pass
        except Exception as e:
            print(f"      [WARN] Option candles ingestion failed: {e}")

    def calculate_and_store_stats(self, symbol, date_str):
        """
        Calculates PCR, IV, Greeks, and Trend from stored option chain data.
        Uses 1-minute OI differences for high-precision trend analysis.
        """
        try:
            index_candles = self.data_manager.get_historical_candles(symbol, from_date=date_str, to_date=date_str, mode='backtest')
            if index_candles is None or index_candles.empty:
                print(f"      [WARN] No index candles found for {symbol} on {date_str}. Skipping stats.")
                return
            index_candles['timestamp'] = pd.to_datetime(index_candles['timestamp'])
            index_map = index_candles.set_index('timestamp')['close'].to_dict()
            index_open_map = index_candles.set_index('timestamp')['open'].to_dict()

            with self.db_manager as db:
                query = "SELECT * FROM option_chain_data WHERE symbol = ? AND DATE(timestamp) = ?"
                df = pd.read_sql_query(query, db.conn, params=(symbol, date_str))

            if df.empty: return

            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.sort_values(['timestamp', 'strike'])

            # Calculate 1-minute OI differences for precise trend
            # We group by strike and calculate diff
            df['call_oi_1m'] = df.groupby('strike')['call_oi'].diff().fillna(0)
            df['put_oi_1m'] = df.groupby('strike')['put_oi'].diff().fillna(0)

            processed_snapshots = []
            stats_list = []
            R = 0.1
            prev_pcr = None

            for ts, group in df.groupby('timestamp'):
                spot = index_map.get(ts)
                spot_open = index_open_map.get(ts)
                if not spot:
                    closest_ts = min(index_map.keys(), key=lambda x: abs(x - ts))
                    if abs((closest_ts - ts).total_seconds()) < 300:
                        spot = index_map[closest_ts]
                        spot_open = index_open_map[closest_ts]
                    else: continue

                total_call_oi = group['call_oi'].sum()
                total_put_oi = group['put_oi'].sum()
                pcr = round(total_put_oi / total_call_oi, 4) if total_call_oi > 0 else 1.0
                pcr_velocity = round(pcr - prev_pcr, 4) if prev_pcr is not None else 0.0
                prev_pcr = pcr

                oi_wall_above = group.loc[group['call_oi'].idxmax()]['strike'] if total_call_oi > 0 else 0
                oi_wall_below = group.loc[group['put_oi'].idxmax()]['strike'] if total_put_oi > 0 else 0

                expiry_str = group['expiry'].iloc[0] if 'expiry' in group.columns and group['expiry'].iloc[0] else None
                if expiry_str:
                    expiry_dt = pd.to_datetime(expiry_str).replace(hour=15, minute=30)
                    T = max(0, (expiry_dt - ts).total_seconds() / (365 * 24 * 3600))
                else: T = 0

                group_processed = group.copy()
                for col in ['call_iv', 'put_iv', 'call_delta', 'put_delta', 'call_theta', 'put_theta']:
                    group_processed[col] = 0.0
                for col in ['call_trend', 'put_trend']:
                    group_processed[col] = "Neutral"

                price_dir = 1 if spot > spot_open else -1 if spot < spot_open else 0

                for idx, row in group_processed.iterrows():
                    if row['call_ltp'] > 0 and T > 0:
                        iv_c = MathEngine.calculate_iv(row['call_ltp'], spot, row['strike'], T, R, 'CE')
                        greeks_c = MathEngine.calculate_greeks(spot, row['strike'], T, R, iv_c, 'CE')
                        group_processed.at[idx, 'call_iv'] = round(iv_c, 4)
                        group_processed.at[idx, 'call_delta'] = greeks_c['delta']
                        group_processed.at[idx, 'call_theta'] = greeks_c['theta']

                    if row['put_ltp'] > 0 and T > 0:
                        iv_p = MathEngine.calculate_iv(row['put_ltp'], spot, row['strike'], T, R, 'PE')
                        greeks_p = MathEngine.calculate_greeks(spot, row['strike'], T, R, iv_p, 'PE')
                        group_processed.at[idx, 'put_iv'] = round(iv_p, 4)
                        group_processed.at[idx, 'put_delta'] = greeks_p['delta']
                        group_processed.at[idx, 'put_theta'] = greeks_p['theta']

                    # Use 1m OI change for high-fidelity trend
                    group_processed.at[idx, 'call_trend'] = MathEngine.get_smart_trend(price_dir, row['call_oi_1m'])
                    group_processed.at[idx, 'put_trend'] = MathEngine.get_smart_trend(-price_dir, row['put_oi_1m'])

                processed_snapshots.append(group_processed)

                atm_strike = self.data_manager.calculate_atm_strike(symbol, spot)
                atm_options = group_processed[abs(group_processed['strike'] - atm_strike) <= 100]
                if not atm_options.empty:
                    all_trends = [t for t in (atm_options['call_trend'].tolist() + atm_options['put_trend'].tolist()) if t != 'Neutral']
                    market_trend = max(set(all_trends), key=all_trends.count) if all_trends else "Neutral"
                else: market_trend = "Neutral"

                stats_list.append({
                    'timestamp': ts.strftime('%Y-%m-%d %H:%M:%S'),
                    'pcr': pcr, 'pcr_velocity': pcr_velocity,
                    'oi_wall_above': oi_wall_above, 'oi_wall_below': oi_wall_below,
                    'call_oi': total_call_oi, 'put_oi': total_put_oi,
                    'smart_trend': market_trend, 'advances': 0, 'declines': 0
                })

            if processed_snapshots:
                full_processed_df = pd.concat(processed_snapshots)
                chunk_size = 500
                for i in range(0, len(full_processed_df), chunk_size):
                    self.db_manager.store_option_chain(symbol, full_processed_df.iloc[i:i+chunk_size], date=date_str)

            if stats_list:
                stats_df = pd.DataFrame(stats_list)
                self.db_manager.store_market_stats(symbol, stats_df)
                print(f"      [OK] Stored {len(stats_df)} market stats snapshots.")

                try:
                    instrument_key = SymbolMaster.get_upstox_key(symbol)
                    if instrument_key:
                        with self.db_manager as ctx:
                            enrich_query = """
                                UPDATE historical_candles
                                SET oi = (
                                    SELECT CAST(m.call_oi + m.put_oi AS INTEGER)
                                    FROM market_stats m
                                    WHERE m.symbol = ? AND m.timestamp = historical_candles.timestamp
                                )
                                WHERE symbol = ? AND DATE(timestamp) = ? AND EXISTS (
                                    SELECT 1 FROM market_stats m2
                                    WHERE m2.symbol = ? AND m2.timestamp = historical_candles.timestamp
                                )
                            """
                            ctx.conn.execute(enrich_query, (symbol, instrument_key, date_str, symbol))
                            last_oi = int(stats_df['call_oi'].iloc[-1] + stats_df['put_oi'].iloc[-1])
                            ctx.conn.execute("UPDATE historical_candles SET oi = ? WHERE symbol = ? AND DATE(timestamp) = ? AND (oi = 0 OR oi IS NULL)",
                                          (last_oi, instrument_key, date_str))
                            ctx.conn.commit()
                except: pass
        except Exception as e:
            print(f"      [ERROR] Stats enrichment failed for {symbol} on {date_str}: {e}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Unified Data Ingestion")
    parser.add_argument("--symbol", type=str, required=False)
    parser.add_argument("--from_date", type=str, required=False)
    parser.add_argument("--to_date", type=str, required=False)
    parser.add_argument("--full-options", action="store_true", help="Fetch 1-min option snapshots (Trendlyne)")
    parser.add_argument("--force", action="store_true", help="Force re-ingestion of data if it exists")
    parser.add_argument("--mongo", action="store_true", help="Ingest from MongoDB directly")
    parser.add_argument("--mongo-uri", type=str, default="mongodb://localhost:27017/", help="MongoDB URI")

    args = parser.parse_args()
    SymbolMaster.initialize()
    manager = IngestionManager()

    if args.mongo:
        manager.ingest_from_mongo_db(mongo_uri=args.mongo_uri)
    else:
        if not args.from_date or not args.to_date:
             parser.error("--from_date and --to_date are required unless using --mongo")
        manager.ingest_historical_data(args.symbol, args.from_date, args.to_date, full_options=args.full_options, force=args.force)
