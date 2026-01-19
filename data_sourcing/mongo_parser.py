import json
import pandas as pd
from datetime import datetime
from data_sourcing.database_manager import DatabaseManager
from python_engine.utils.symbol_master import MASTER as SymbolMaster
import re

class MongoParser:
    def __init__(self):
        self.db_manager = DatabaseManager()
        SymbolMaster.initialize()

    def parse_snapshot(self, snapshot_json):
        """Parses a single MongoDB snapshot and stores it in the database."""
        current_ts = int(snapshot_json.get('currentTs', 0))
        if not current_ts:
            return

        dt = datetime.fromtimestamp(current_ts / 1000)
        timestamp_str = dt.strftime('%Y-%m-%d %H:%M:%S')
        date_str = dt.strftime('%Y-%m-%d')

        feeds = snapshot_json.get('feeds', {})

        # 1. Identify relevant indices
        index_data = {}
        for key, feed in feeds.items():
            if "NSE_INDEX" in key:
                name = key.split('|')[-1].upper()
                ltpc = feed.get('fullFeed', {}).get('indexFF', {}).get('ltpc', {})
                if ltpc:
                    index_data[name] = ltpc.get('ltp')
                    # Also store index candle if needed, but here we focus on option chain

        # 2. Process Options
        # Group by underlying
        underlying_chains = {} # { underlying: [ {strike, call_oi, ...} ] }

        for key, feed in feeds.items():
            if "NSE_FO" in key:
                ff = feed.get('fullFeed', {}).get('marketFF', {})
                if not ff: continue

                # Resolve ticker
                ticker = SymbolMaster.get_ticker_from_key(key)
                if not ticker:
                    # Try reverse resolution if it's not in master
                    continue

                # Parse ticker: e.g. "NIFTY 25550 PE 20 JAN 26"
                match = re.match(r"^([A-Z]+)\s+(\d+)\s+(CE|PE)\s+(.*)$", ticker)
                if not match: continue

                underlying = match.group(1)
                strike = float(match.group(2))
                opt_type = match.group(3)
                expiry_str = match.group(4)

                # Normalize expiry to YYYY-MM-DD
                try:
                    expiry_dt = pd.to_datetime(expiry_str)
                    expiry_iso = expiry_dt.strftime('%Y-%m-%d')
                except:
                    expiry_iso = expiry_str

                if underlying not in underlying_chains:
                    underlying_chains[underlying] = {}

                if strike not in underlying_chains[underlying]:
                    underlying_chains[underlying][strike] = {
                        "strike": strike,
                        "expiry": expiry_iso,
                        "timestamp": timestamp_str
                    }

                s_data = underlying_chains[underlying][strike]

                prefix = "call" if opt_type == "CE" else "put"
                s_data[f"{prefix}_oi"] = float(ff.get('oi', 0))
                s_data[f"{prefix}_ltp"] = float(ff.get('ltpc', {}).get('ltp', 0))
                s_data[f"{prefix}_instrument_key"] = key

                greeks = ff.get('optionGreeks', {})
                if greeks:
                    s_data[f"{prefix}_delta"] = float(greeks.get('delta', 0))
                    s_data[f"{prefix}_theta"] = float(greeks.get('theta', 0))

                s_data[f"{prefix}_iv"] = float(ff.get('iv', 0))

        # 3. Store in DB
        for underlying, strikes_dict in underlying_chains.items():
            canonical_underlying = "NSE|INDEX|" + underlying
            df = pd.DataFrame(list(strikes_dict.values()))

            # Fill missing columns with defaults to avoid NULLs
            expected_cols = [
                'call_oi', 'put_oi', 'call_ltp', 'put_ltp',
                'call_delta', 'put_delta', 'call_theta', 'put_theta',
                'call_iv', 'put_iv', 'call_oi_chg', 'put_oi_chg'
            ]
            for col in expected_cols:
                if col not in df.columns:
                    df[col] = 0.0
                else:
                    df[col] = df[col].fillna(0.0)

            if 'call_trend' not in df.columns: df['call_trend'] = "Neutral"
            if 'put_trend' not in df.columns: df['put_trend'] = "Neutral"

            self.db_manager.store_option_chain(canonical_underlying, df, date=date_str)
            print(f"[MongoParser] Stored snapshot for {canonical_underlying} at {timestamp_str}")

    def ingest_from_file(self, filepath):
        with open(filepath, 'r') as f:
            data = json.load(f)

        if isinstance(data, list):
            for snapshot in data:
                self.parse_snapshot(snapshot)
        else:
            self.parse_snapshot(data)

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        parser = MongoParser()
        parser.ingest_from_file(sys.argv[1])
