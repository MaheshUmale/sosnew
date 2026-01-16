import sqlite3
import pandas as pd

conn = sqlite3.connect('sos_master_data.db')
query = "SELECT timestamp, open, high, low, close, volume FROM historical_candles WHERE symbol='NSE_INDEX|Nifty 50' ORDER BY timestamp DESC LIMIT 5"
df = pd.read_sql_query(query, conn)
print("Latest NIFTY 50 Candles:")
print(df)
conn.close()
