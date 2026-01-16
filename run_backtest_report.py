import subprocess
import sqlite3
import pandas as pd
import sys

def run_backtest():
    # Clear previous trades
    try:
        conn = sqlite3.connect('sos_master_data.db')
        conn.execute("DELETE FROM trades")
        conn.commit()
        conn.close()
        print("Cleared previous trade records.")
    except Exception as e:
        print(f"Warning: Could not clear trades: {e}")

    print("Running Backtest...")
    result = subprocess.run([sys.executable, "run.py", "--mode", "backtest", "--symbol", "NIFTY", "--from-date", "2026-01-16", "--to-date", "2026-01-16"], capture_output=True, text=True)
    print(result.stdout)
    if result.stderr:
        print("ERRORS:", result.stderr)
    
    return result.returncode

def report_pnl():
    print("\ngenerating PnL Report...")
    try:
        conn = sqlite3.connect('sos_master_data.db')
        query = "SELECT * FROM trades"
        df = pd.read_sql_query(query, conn)
        
        if df.empty:
            print("No trades found.")
            return

        # Calculate Total PnL
        df['pnl'] = pd.to_numeric(df['pnl'], errors='coerce').fillna(0)
        total_pnl = df['pnl'].sum()
        win_rate = (len(df[df['pnl'] > 0]) / len(df)) * 100 if len(df) > 0 else 0
        
        print("\n" + "="*40)
        print(f"Total PnL: {total_pnl:.2f}")
        print(f"Total Trades: {len(df)}")
        print(f"Win Rate: {win_rate:.2f}%")
        print("="*40)
        print("\nTrade Details:")
        print(df[['entry_time', 'symbol', 'side', 'entry_price', 'exit_price', 'pnl']])
        
    except Exception as e:
        print(f"Error generating report: {e}")

if __name__ == "__main__":
    ret = run_backtest()
    if ret == 0:
        report_pnl()
    else:
        print("Backtest failed.")
