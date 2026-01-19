import pandas as pd
from datetime import datetime
from python_engine.utils.symbol_master import MASTER as SymbolMaster
from data_sourcing.data_manager import DataManager

SymbolMaster.initialize()
dm = DataManager()
date = datetime.strptime("2026-01-16", "%Y-%m-%d").date()
canonical = "NSE|INDEX|NIFTY"
df = dm.get_historical_candles(canonical, from_date="2026-01-16", to_date="2026-01-16", mode='backtest')
print("Columns:", df.columns.tolist())
df['time'] = pd.to_datetime(df['timestamp']).dt.strftime('%Y-%m-%d %H:%M:%S')
print("Sample time:", df['time'].iloc[0])
