from data_sourcing.database_manager import DatabaseManager
import pandas as pd

db = DatabaseManager()
df = db.get_instrument_master()

indices = df[df['segment'] == 'NSE_INDEX']
print(indices[['trading_symbol', 'name', 'instrument_key']].to_string())
