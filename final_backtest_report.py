import sqlite3
import pandas as pd
import subprocess
import sys
from python_engine.utils.symbol_master import MASTER as SymbolMaster

def run_symbol_backtest(symbol):
    print(f"\n[*] Running Backtest for {symbol} on 2026-01-16...")
    # Map friendly symbol to canonical if needed
    if symbol == "NIFTY": sym = "NSE|INDEX|NIFTY"
    elif symbol == "BANKNIFTY": sym = "NSE|INDEX|BANKNIFTY"
    else: sym = symbol

    subprocess.run([sys.executable, "run.py", "--mode", "backtest", "--symbol", sym, "--from-date", "2026-01-16", "--to-date", "2026-01-16"], capture_output=False)

def generate_consolidated_report():
    print("\n" + "!"*60)
    print("DETAILED BACKTEST PERFORMANCE REPORT - 16 JAN 2026")
    print("!"*60)

    conn = sqlite3.connect('sos_master_data.db')
    df = pd.read_sql_query("SELECT * FROM trades", conn)
    conn.close()

    if df.empty:
        print("\nNo trades were triggered during this backtest period.")
        print("Reason: Market conditions on Jan 16th may not have met the strict optimized entry criteria (Sentiment + Technical) for the 18 gates.")
        return

    # Cleanup types
    df['pnl'] = pd.to_numeric(df['pnl'], errors='coerce').fillna(0)

    # 1. Overall Stats
    total_trades = len(df)
    winners = df[df['pnl'] > 0]
    losers = df[df['pnl'] <= 0]
    win_rate = (len(winners) / total_trades) * 100
    total_pnl = df['pnl'].sum()

    print(f"\n--- OVERALL SUMMARY ---")
    print(f"Total Trades   : {total_trades}")
    print(f"Total PnL      : {total_pnl:,.2f}")
    print(f"Win Rate       : {win_rate:.2f}%")
    print(f"Avg PnL/Trade  : {(total_pnl/total_trades):.2f}")

    # 2. Per Symbol Stats
    print(f"\n--- PERFORMANCE BY SYMBOL ---")
    symbol_grp = df.groupby('symbol').agg({
        'trade_id': 'count',
        'pnl': 'sum'
    }).rename(columns={'trade_id': 'Trades', 'pnl': 'Net PnL'})
    print(symbol_grp)

    # 3. Per Strategy Stats
    print(f"\n--- PERFORMANCE BY STRATEGY (18 GATES) ---")
    strat_grp = df.groupby('pattern_id').agg({
        'trade_id': 'count',
        'pnl': ['sum', 'mean']
    })
    strat_grp.columns = ['Trades', 'Net PnL', 'Avg PnL']

    # Add Win Rate per Strategy
    strat_grp['Win %'] = df.groupby('pattern_id').apply(lambda x: (len(x[x['pnl'] > 0]) / len(x)) * 100)
    print(strat_grp)

    # 4. Detailed Trade Log
    print(f"\n--- TOP TRADES ---")
    print(df.sort_values('pnl', ascending=False).head(10)[['entry_time', 'symbol', 'pattern_id', 'side', 'entry_price', 'exit_price', 'pnl']])

if __name__ == "__main__":
    # Clear old trades for a clean run
    conn = sqlite3.connect('sos_master_data.db')
    conn.execute("DELETE FROM trades")
    conn.commit()
    conn.close()

    # Run backtests
    run_symbol_backtest("NIFTY")
    run_symbol_backtest("BANKNIFTY")

    # Report
    generate_consolidated_report()
