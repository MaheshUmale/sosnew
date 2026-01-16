
import sqlite3
import pandas as pd
from datetime import datetime

def verify_db():
    conn = sqlite3.connect('sos_master_data.db')
    cursor = conn.cursor()
    
    print("--- Database Verification ---")
    
    # Check Historical Candles
    print("\n[Historical Candles (Today)]")
    try:
        df_candles = pd.read_sql_query("SELECT * FROM historical_candles WHERE timestamp LIKE '2026-01-16%'", conn)
        print(f"  Count: {len(df_candles)}")
        if not df_candles.empty:
            print(f"  Sample: {df_candles.iloc[0]['symbol']} @ {df_candles.iloc[0]['timestamp']}")
    except Exception as e:
        print(f"  Error: {e}")

    # Check Option Chain
    print("\n[Option Chain Data (Today)]")
    try:
        df_chain = pd.read_sql_query("SELECT * FROM option_chain_data WHERE timestamp LIKE '2026-01-16%'", conn)
        print(f"  Count: {len(df_chain)}")
        if not df_chain.empty:
             print(f"  Sample: {df_chain.iloc[0]['symbol']} Strike: {df_chain.iloc[0]['strike']}")
    except Exception as e:
        print(f"  Error: {e}")
        
    conn.close()

if __name__ == "__main__":
    verify_db()
