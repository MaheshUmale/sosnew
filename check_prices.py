import sqlite3
conn = sqlite3.connect('backtest_data.db')
res = conn.execute("SELECT symbol, close FROM backtest_candles WHERE symbol='BANKNIFTY' LIMIT 10").fetchall()
print("BANKNIFTY Sample Prices:", res)
res2 = conn.execute("SELECT DISTINCT symbol FROM backtest_candles WHERE symbol LIKE '%NIFTY%'").fetchall()
print("Symbols containing NIFTY:", res2)
conn.close()
