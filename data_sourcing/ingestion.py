import time
import pandas as pd
import numpy as np
import traceback
import logging
from datetime import datetime, timedelta
from data_sourcing.data_manager import DataManager
from data_sourcing.database_manager import DatabaseManager
from python_engine.utils.symbol_master import MASTER as SymbolMaster
from python_engine.engine_config import Config
from python_engine.utils.math_engine import MathEngine

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class IngestionManager:
    def __init__(self, access_token=None):
        if not access_token:
            Config.load('config.json')
            access_token = Config.get('upstox_access_token')

        self.data_manager = DataManager(access_token=access_token)
        self.db_manager = self.data_manager.db_manager

    def ingest_historical_data(self, symbol, from_date, to_date, full_options=False, force=False):
        canonical_symbol = SymbolMaster.get_canonical_ticker(symbol)
        logger.info(f"Starting Ingestion for {canonical_symbol} | {from_date} to {to_date}")

        start_dt = datetime.strptime(from_date, '%Y-%m-%d')
        end_dt = datetime.strptime(to_date, '%Y-%m-%d')
        days = (end_dt - start_dt).days + 1
        bars_needed = days * 400

        self.data_manager.get_historical_candles(canonical_symbol, from_date=from_date, to_date=to_date, n_bars=bars_needed, mode='live')

        date_range = pd.date_range(start=start_dt.date(), end=end_dt.date(), freq='B')
        holidays = self.data_manager.holidays

        for target_date in date_range:
            date_str = target_date.strftime('%Y-%m-%d')
            if date_str in holidays:
                continue

            if not force:
                existing_candles = self.db_manager.get_historical_candles(canonical_symbol, 'NSE', '1m', date_str, date_str)
                if existing_candles is not None and not existing_candles.empty:
                    existing_stats = self.db_manager.get_market_stats(canonical_symbol, date_str, date_str)
                    has_oi = (existing_candles['oi'] > 0).any()
                    if not existing_stats.empty and has_oi:
                        logger.info(f"Skipping {date_str} - Data already exists.")
                        continue

            logger.info(f"Processing {date_str}...")

            if full_options:
                logger.info(f"    - Syncing Full-Day Option Chain snapshots (Trendlyne)...")
                try:
                    from backfill_trendlyne import run_backfill
                    prefix = "NIFTY" if "NIFTY" in canonical_symbol.upper() and "BANK" not in canonical_symbol.upper() else "BANKNIFTY"
                    run_backfill(symbols_list=[prefix], full_run=True, date_override=date_str)
                    with self.db_manager as ctx:
                        ctx.conn.execute("INSERT OR REPLACE INTO option_chain_data (symbol, timestamp, strike, expiry, call_oi_chg, put_oi_chg, call_instrument_key, put_instrument_key, call_oi, put_oi) "
                                      "SELECT ?, timestamp, strike, expiry, call_oi_chg, put_oi_chg, call_instrument_key, put_instrument_key, call_oi, put_oi FROM option_chain_data WHERE symbol = ?", (canonical_symbol, prefix))
                        ctx.conn.commit()
                except Exception as e:
                    logger.error(f"    - run_backfill failed: {e}")
            else:
                self.data_manager.get_option_chain(canonical_symbol, date=date_str, mode='live')

            self.ingest_atm_option_candles(canonical_symbol, date_str)
            self.calculate_and_store_stats(canonical_symbol, date_str)

    def ingest_atm_option_candles(self, canonical_symbol, date_str):
        try:
            candles = self.data_manager.get_historical_candles(canonical_symbol, from_date=date_str, to_date=date_str, mode='backtest')
            if candles is None or candles.empty: return
            low_strike = self.data_manager.calculate_atm_strike(canonical_symbol, candles['low'].min())
            high_strike = self.data_manager.calculate_atm_strike(canonical_symbol, candles['high'].max())
            strike_step = 100 if "BANK" in canonical_symbol.upper() else 50
            strikes = range(int(low_strike) - strike_step*2, int(high_strike) + strike_step*3, strike_step)
            with self.db_manager as db:
                query = "SELECT DISTINCT strike, expiry, call_instrument_key, put_instrument_key FROM option_chain_data WHERE symbol = ? AND DATE(timestamp) = ? AND strike IN ({})".format(','.join([str(s) for s in strikes]))
                df = pd.read_sql_query(query, db.conn, params=(canonical_symbol, date_str))
            if df.empty: return
            unique_keys = set()
            for _, row in df.iterrows():
                if row['call_instrument_key']: unique_keys.add(row['call_instrument_key'])
                if row['put_instrument_key']: unique_keys.add(row['put_instrument_key'])
            for key in unique_keys:
                if key: self.data_manager.get_historical_candles(key, from_date=date_str, to_date=date_str, mode='live')
        except Exception as e:
            logger.warning(f"ATM Option candles ingestion warning: {e}")

    def calculate_and_store_stats(self, symbol, date_str):
        try:
            index_candles = self.data_manager.get_historical_candles(symbol, from_date=date_str, to_date=date_str, mode='backtest')
            if index_candles is None or index_candles.empty: return
            index_map = index_candles.set_index('timestamp')['close'].to_dict()
            index_open_map = index_candles.set_index('timestamp')['open'].to_dict()

            with self.db_manager as db:
                query = "SELECT * FROM option_chain_data WHERE symbol = ? AND DATE(timestamp) = ?"
                df = pd.read_sql_query(query, db.conn, params=(symbol, date_str))
            if df.empty: return
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.sort_values(['timestamp', 'strike'])
            df['call_oi_1m'] = df.groupby('strike')['call_oi'].diff().fillna(0)
            df['put_oi_1m'] = df.groupby('strike')['put_oi'].diff().fillna(0)

            processed_snapshots, stats_list = [], []
            R, prev_pcr = 0.1, None

            for ts, group in df.groupby('timestamp'):
                ts_str = ts.strftime('%Y-%m-%d %H:%M:%S')
                spot = index_map.get(ts_str)
                spot_open = index_open_map.get(ts_str)
                if spot is None:
                    # Try to find closest within 5 mins
                    ts_dt = ts.to_pydatetime()
                    closest_ts = min(index_map.keys(), key=lambda x: abs(datetime.strptime(x, '%Y-%m-%d %H:%M:%S') - ts_dt), default=None)
                    if closest_ts and abs((datetime.strptime(closest_ts, '%Y-%m-%d %H:%M:%S') - ts_dt).total_seconds()) < 300:
                        spot = index_map[closest_ts]
                        spot_open = index_open_map[closest_ts]

                if spot is None: continue

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

                group_p = group.copy()
                price_dir = 1 if (spot_open and spot > spot_open) else -1 if (spot_open and spot < spot_open) else 0

                for idx, row in group_p.iterrows():
                    iv_c = MathEngine.calculate_iv(row['call_ltp'], spot, row['strike'], T, R, 'CE') if row['call_ltp'] is not None and row['call_ltp'] > 0 and T > 0 else 0.0
                    g_c = MathEngine.calculate_greeks(spot, row['strike'], T, R, iv_c, 'CE') if iv_c > 0 else {'delta':0, 'theta':0}
                    iv_p = MathEngine.calculate_iv(row['put_ltp'], spot, row['strike'], T, R, 'PE') if row['put_ltp'] is not None and row['put_ltp'] > 0 and T > 0 else 0.0
                    g_p = MathEngine.calculate_greeks(spot, row['strike'], T, R, iv_p, 'PE') if iv_p > 0 else {'delta':0, 'theta':0}

                    group_p.at[idx, 'call_iv'], group_p.at[idx, 'call_delta'], group_p.at[idx, 'call_theta'] = iv_c, g_c['delta'], g_c['theta']
                    group_p.at[idx, 'put_iv'], group_p.at[idx, 'put_delta'], group_p.at[idx, 'put_theta'] = iv_p, g_p['delta'], g_p['theta']
                    group_p.at[idx, 'call_trend'] = MathEngine.get_smart_trend(price_dir, row['call_oi_1m'])
                    group_p.at[idx, 'put_trend'] = MathEngine.get_smart_trend(-price_dir, row['put_oi_1m'])

                processed_snapshots.append(group_p)
                atm_strike = self.data_manager.calculate_atm_strike(symbol, spot)
                atm_options = group_p[abs(group_p['strike'] - atm_strike) <= 100]
                all_trends = [t for t in (atm_options['call_trend'].tolist() + atm_options['put_trend'].tolist()) if t != 'Neutral']
                market_trend = max(set(all_trends), key=all_trends.count) if all_trends else "Neutral"

                stats_list.append({'timestamp': ts_str, 'pcr': pcr, 'pcr_velocity': pcr_velocity, 'oi_wall_above': oi_wall_above, 'oi_wall_below': oi_wall_below, 'call_oi': total_call_oi, 'put_oi': total_put_oi, 'smart_trend': market_trend, 'advances': 0, 'declines': 0})

            if processed_snapshots:
                full_df = pd.concat(processed_snapshots).reset_index(drop=True)
                chunk_size = 500
                for i in range(0, len(full_df), chunk_size):
                    chunk = full_df.iloc[i : i + chunk_size]
                    self.db_manager.store_option_chain(symbol, chunk, date=date_str)
            if stats_list:
                stats_df = pd.DataFrame(stats_list)
                self.db_manager.store_market_stats(symbol, stats_df)
                logger.info(f"      [OK] Stored {len(stats_df)} market stats snapshots.")
        except Exception as e:
            logger.error(f"Stats enrichment failed: {e}")
            traceback.print_exc()

    def ingest_from_mongo_db(self, mongo_uri="mongodb://localhost:27017/", db_name="upstox_strategy_db", collection_name="raw_tick_data"):
        try:
            from data_sourcing.mongo_parser import MongoParser
            parser = MongoParser(mongo_uri=mongo_uri)
            count = parser.ingest_from_db(db_name=db_name, collection_name=collection_name)
            logger.info(f"MongoDB data ingestion complete. Processed {count} snapshots.")
        except Exception as e:
            logger.error(f"MongoDB ingestion failed: {e}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", type=str)
    parser.add_argument("--from_date", type=str)
    parser.add_argument("--to_date", type=str)
    parser.add_argument("--full-options", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--mongo", action="store_true")
    args = parser.parse_args()
    SymbolMaster.initialize()
    manager = IngestionManager()
    if args.mongo: manager.ingest_from_mongo_db()
    else: manager.ingest_historical_data(args.symbol, args.from_date, args.to_date, full_options=args.full_options, force=args.force)
