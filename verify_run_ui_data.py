import pandas as pd
from datetime import datetime
from python_engine.utils.symbol_master import MASTER as SymbolMaster
from data_sourcing.data_manager import DataManager
import os

SymbolMaster.initialize()
dm = DataManager()

date_str = "2026-01-16"
symbol = "NIFTY"
db_symbol = SymbolMaster.get_upstox_key(symbol)

print(f"Resolving for {symbol} on {date_str}...")
print(f"DB Symbol: {db_symbol}")

# Test index candle loading
df = dm.get_historical_candles(db_symbol, from_date=date_str, to_date=date_str, mode='backtest')
if df is not None:
    print(f"Loaded {len(df)} index candles.")
else:
    print("Failed to load index candles.")

# Test ATM resolution
from data_sourcing.database_manager import DatabaseManager
db_manager = DatabaseManager('sos_master_data.db')
query = f"SELECT close FROM historical_candles WHERE symbol = '{db_symbol}' AND DATE(timestamp) = '{date_str}' ORDER BY timestamp DESC LIMIT 1"
with db_manager as db:
    res = pd.read_sql(query, db.conn)

if not res.empty:
    spot = res.iloc[0]['close']
    print(f"Spot price: {spot}")
    dm.load_and_cache_fno_instruments(target_date=date_str)
    ce_key, ce_name = dm.get_atm_option_details(symbol, 'BUY', spot, target_date=date_str)
    print(f"Resolved ATM CE: {ce_name} ({ce_key})")

    # Check if ce_key is valid
    opt_df = dm.get_historical_candles(ce_key, from_date=date_str, to_date=date_str, mode='backtest')
    if opt_df is not None:
        print(f"Loaded {len(opt_df)} CE candles.")
    else:
        print("Failed to load CE candles.")
else:
    print("No spot price found in DB.")
