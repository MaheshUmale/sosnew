import pandas as pd
from datetime import datetime
from python_engine.utils.symbol_master import MASTER as SymbolMaster
from data_sourcing.data_manager import DataManager

SymbolMaster.initialize()
dm = DataManager()

date_str = "2026-01-19"
symbol = "NIFTY"
db_symbol = SymbolMaster.get_upstox_key(symbol)

print(f"Resolving for {symbol} on {date_str} (LIVE)...")
df = dm.get_historical_candles(db_symbol, from_date=date_str, to_date=date_str, mode='live')
if df is not None:
    print(f"Loaded {len(df)} index candles for today.")
else:
    print("Failed to load today's index candles.")
