import sqlite3
import os

db_path = 'sos_master_data.db'
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    # Clear option chain data for today
    cursor.execute("DELETE FROM option_chain_data WHERE timestamp LIKE '2026-01-16%'")
    print(f"Deleted {cursor.rowcount} rows from option_chain_data for today.")
    
    # Also clear trades to have a fresh report
    cursor.execute("DELETE FROM trades WHERE entry_time LIKE '2026-01-16%'")
    print(f"Deleted {cursor.rowcount} rows from trades for today.")
    
    conn.commit()
    conn.close()
else:
    print("Database not found.")
