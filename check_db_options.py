import sqlite3
conn = sqlite3.connect('backtest_data.db')
res = conn.execute("SELECT DISTINCT symbol FROM backtest_candles WHERE symbol LIKE '%CE%' OR symbol LIKE '%PE%'").fetchall()
print("Option Symbols Found:", res)
conn.close()
