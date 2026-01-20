import sqlite3
import pandas as pd
import argparse
from python_engine.engine_config import Config

def generate_consolidated_report():
    print("\n" + "!"*60)
    print("DETAILED BACKTEST PERFORMANCE REPORT")
    print("!"*60)

    # Load config to get DB path
    try:
        Config.load('config.json')
    except Exception:
        pass
    db_path = Config.get('db_path', 'sos_master_data.db')

    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query("SELECT * FROM trades", conn)
    conn.close()

    if df.empty:
        print("\nNo trades were triggered during this backtest period.")
        return

    # Cleanup types
    df['pnl'] = pd.to_numeric(df['pnl'], errors='coerce').fillna(0)

    # 1. Overall Stats
    total_trades = len(df)
    winners = df[df['pnl'] > 0]
    win_rate = (len(winners) / total_trades) * 100 if total_trades > 0 else 0
    total_pnl = df['pnl'].sum()

    print(f"\n--- OVERALL SUMMARY ---")
    print(f"Total Trades   : {total_trades}")
    print(f"Total Net PnL  : {total_pnl:,.2f}")
    print(f"Win Rate       : {win_rate:.2f}%")
    if total_trades > 0:
        print(f"Avg PnL/Trade  : {(total_pnl/total_trades):.2f}")

    # 2. Performance by Date
    print(f"\n--- PERFORMANCE BY DATE ---")
    df['date'] = pd.to_datetime(df['entry_time']).dt.date
    date_grp = df.groupby('date').agg({
        'trade_id': 'count',
        'pnl': 'sum'
    }).rename(columns={'trade_id': 'Trades', 'pnl': 'Net PnL'})
    print(date_grp)

    # 3. Performance by Strategy (18 Gates)
    print(f"\n--- PERFORMANCE BY STRATEGY (GATE) ---")
    strat_grp = df.groupby('pattern_id').agg({
        'trade_id': 'count',
        'pnl': ['sum', 'mean']
    })
    strat_grp.columns = ['Trades', 'Net PnL', 'Avg PnL']

    # Add Win Rate per Strategy
    strat_grp['Win %'] = df.groupby('pattern_id')['pnl'].apply(lambda x: (len(x[x > 0]) / len(x)) * 100 if len(x) > 0 else 0)
    print(strat_grp)

    # 4. Top 10 Trades
    print(f"\n--- TOP 10 TRADES ---")
    print(df.sort_values('pnl', ascending=False).head(10)[['entry_time', 'symbol', 'pattern_id', 'side', 'entry_price', 'exit_price', 'pnl']])

if __name__ == "__main__":
    generate_consolidated_report()
