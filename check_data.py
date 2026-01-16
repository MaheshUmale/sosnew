import pandas as pd
from data_sourcing.database_manager import DatabaseManager

db = DatabaseManager()
print("Checking data for 2026-01-16...")
candles = db.get_historical_candles("NSE|INDEX|NIFTY", "NSE", "1m", "2026-01-16", "2026-01-16")
print(f"Candles found: {len(candles) if candles is not None else 0}")
if candles is not None and not candles.empty:
    print(candles.head())
    print("\nVolume Analysis:")
    print(candles['volume'].describe())

print("\nChecking option_chain_data Schema...")
query = "PRAGMA table_info(option_chain_data)"
try:
    with db as database:
        df = pd.read_sql_query(query, database.conn)
        print(df)
except Exception as e:
    print(f"Error: {e}")
