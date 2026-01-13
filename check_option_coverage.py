import sqlite3

# Check backtest_data.db
print("=" * 80)
print("BACKTEST_DATA.DB - Option Coverage")
print("=" * 80)
conn = sqlite3.connect('backtest_data.db')

# Get all option symbols
options = conn.execute("""
    SELECT DISTINCT symbol 
    FROM backtest_candles 
    WHERE (symbol LIKE '%CE%' OR symbol LIKE '%PE%') 
    AND symbol NOT IN ('BAJFINANCE', 'RELIANCE', 'ULTRACEMCO')
""").fetchall()

print(f"\n✅ Option contracts with candles: {len(options)}")
for opt in options:
    count = conn.execute(f"SELECT COUNT(*) FROM backtest_candles WHERE symbol='{opt[0]}'").fetchone()[0]
    print(f"  - {opt[0]}: {count} candles")

conn.close()

# Check timeseries DB
print("\n" + "=" * 80)
print("SOS_TIMESERIES_2026_01.DB - PCR/OI Data")
print("=" * 80)
try:
    conn = sqlite3.connect('sos_timeseries_2026_01.db')
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    print(f"\n✅ Tables: {[t[0] for t in tables]}")
    
    for table in tables:
        count = conn.execute(f"SELECT COUNT(*) FROM {table[0]}").fetchone()[0]
        print(f"  - {table[0]}: {count} rows")
    
    conn.close()
except Exception as e:
    print(f"❌ Error: {e}")
