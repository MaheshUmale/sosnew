"""
SOS Engine Data Bridge - WebSocket Server

Listens for connections from the SOS Engine to provide real-time market data
with a multi-source redundancy strategy.

Data Feeds Sent:
- `CANDLE_UPDATE`: Per-symbol 1-minute OHLCV snapshots.
- `SENTIMENT_UPDATE`: Market sentiment regime derived from PCR and market breadth.

Redundancy Tiers:
- Candles: Upstox (Primary) -> TradingView (Secondary) -> Yahoo Finance (Tertiary)
- Breadth/PCR: NSE API (Primary) -> Trendlyne DB/TV Screener (Fallbacks)

Usage:
    python tv_data_bridge.py --port 8765
    # Starts server on ws://localhost:8765 by default

Dependencies:
    - websockets, pandas, requests
    - tradingview-screener, yfinance
    - upstox-client (optional, for primary data source)
    - backfill_trendlyne (optional, for historical option chain)

Author: Mahesh
Version: 3.1 (Server-Side Refactor)
"""
print("--- Data Bridge Server script started ---")
import time
import json
import argparse
import asyncio
import websockets
import pandas as pd
from datetime import datetime
from tradingview_screener import Query, col
from NSEAPICLient import NSEHistoricalAPI
from SymbolMaster import MASTER as SymbolMaster

# Upstox SDK Imports
try:
    import upstox_client
    import config
    UPSTOX_AVAILABLE = True
except ImportError:
    UPSTOX_AVAILABLE = False
    print("[WARN] Upstox SDK or config not found. Fundamental data source disabled.")

try:
    from backfill_trendlyne import DB as TrendlyneDB, fetch_live_snapshot
except ImportError:
    TrendlyneDB = None
    fetch_live_snapshot = None
    print("[WARN] could not import backfill_trendlyne. Option chain data will be missing.")

# Configuration
SYMBOLS = [
    'RELIANCE', 'SBIN', 'ADANIENT', 'NIFTY', 'BANKNIFTY',
    'HDFCBANK', 'ICICIBANK', 'INFY', 'TCS', 'BHARTIARTL',
    'ITC', 'KOTAKBANK', 'HINDUNILVR', 'LT', 'AXISBANK',
    'MARUTI', 'SUNPHARMA', 'TITAN', 'ULTRACEMCO', 'WIPRO',
    'BAJFINANCE', 'ASIANPAINT', 'HCLTECH', 'NTPC', 'POWERGRID'
]

async def run_backtest_server(websocket, path, date):
    import sqlite3
    db_path = "backtest_data.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM backtest_candles WHERE date = ? ORDER BY timestamp", (date,))
    candle_rows = cursor.fetchall()

    cursor.execute("SELECT * FROM backtest_option_chain WHERE date = ? ORDER BY timestamp", (date,))
    option_rows = cursor.fetchall()

    cursor.execute("SELECT * FROM backtest_sentiment WHERE date = ? ORDER BY timestamp", (date,))
    sentiment_rows = cursor.fetchall()
    conn.close()

    if not candle_rows:
        print(f"No candle data found for date {date}. Aborting backtest.")
        await websocket.close()
        return

    sentiment_map = {(row[0], row[2]): row for row in sentiment_rows}
    option_map = {}
    for row in option_rows:
        key = (row[0], row[2])
        if key not in option_map:
            option_map[key] = []
        option_map[key].append(row)


    for row in candle_rows:
        symbol, date, timestamp, open_price, high_price, low_price, close_price, volume, source = row
        ts = int(time.time() * 1000)
        candle_data = {
            "open": open_price,
            "high": high_price,
            "low": low_price,
            "close": close_price,
            "volume": volume
        }

        sentiment = sentiment_map.get((symbol, timestamp))
        pcr = sentiment[3] if sentiment else 1.0
        regime = sentiment[4] if sentiment else "SIDEWAYS"

        message = {
            "type": "MARKET_UPDATE",
            "timestamp": ts,
            "data": {
                "symbol": symbol,
                "candle": candle_data,
                "sentiment": {"pcr": pcr, "regime": regime}
            }
        }
        await websocket.send(json.dumps(message))

        if (symbol, timestamp) in option_map:
            chain = []
            for option_row in option_map[(symbol, timestamp)]:
                chain.append({
                    "strike": option_row[3],
                    "call_oi_chg": option_row[4],
                    "put_oi_chg": option_row[5]
                })

            option_message = {
                "type": "OPTION_CHAIN_UPDATE",
                "timestamp": ts,
                "data": {
                    "symbol": symbol,
                    "chain": chain
                }
            }
            await websocket.send(json.dumps(option_message))

        await asyncio.sleep(0.1)

async def run_server(port=8765, date=None):
    if not date:
        print("Live mode not implemented. Please provide a --date for backtesting.")
        return

    handler = lambda ws, path: run_backtest_server(ws, path, date)
    print(f"Backtest mode enabled for date: {date}")

    async with websockets.serve(handler, "localhost", port):
        await asyncio.Future()  # Run forever

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SOS Engine Data Bridge Server")
    parser.add_argument('--port', type=int, default=8765, help='Port to bind the WebSocket server to')
    parser.add_argument('--date', type=str, help='Date for backtesting in YYYY-MM-DD format')
    args = parser.parse_args()

    if not args.date:
        print("Error: The --date argument is required for backtesting.")
    else:
        try:
            asyncio.run(run_server(port=args.port, date=args.date))
        except RuntimeError as e:
            print(f"Asyncio runtime error: {e}")
        except KeyboardInterrupt:
            print("Server stopped manually.")
