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

class SOSDataBridgeServer:
    def __init__(self, symbols, host='localhost', port=8765):
        self.host = host
        self.port = port
        self.symbols = symbols
        self.nse = NSEHistoricalAPI()
        self.tickers = [f"NSE:{s}" for s in symbols]
        self.connected_clients = set()
        self.pcr_data = {"NIFTY": 1.0, "BANKNIFTY": 1.0}
        self.market_breadth = {"advances": 0, "declines": 0}
        self.db_path = "backtest_data.db"
        self._init_db()

    def _init_db(self):
        """Initializes the SQLite database for candle persistence."""
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS backtest_candles (
                            symbol TEXT,
                            date TEXT,
                            timestamp TEXT,
                            open REAL,
                            high REAL,
                            low REAL,
                            close REAL,
                            volume INTEGER,
                            source TEXT,
                            PRIMARY KEY (symbol, date, timestamp)
                          )''')
        conn.commit()
        conn.close()

    def _persist_candle(self, symbol, timestamp_ms, candle_data):
        """Saves a single candle update to the database."""
        import sqlite3
        try:
            dt = datetime.fromtimestamp(timestamp_ms / 1000)
            date_str = dt.strftime("%Y-%m-%d")
            time_str = dt.strftime("%H:%M")
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""INSERT OR REPLACE INTO backtest_candles 
                              VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                           (symbol, date_str, time_str,
                            candle_data['open'], candle_data['high'], 
                            candle_data['low'], candle_data['close'],
                            candle_data['volume'], 'live_bridge'))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[DB ERROR] Failed to persist candle for {symbol}: {e}")

    async def connection_handler(self, websocket):
        """Handles a new client connection, managing its lifecycle."""
        print(f"[CONNECTION] Client connected from {websocket.remote_address}. Total clients: {len(self.connected_clients) + 1}")
        self.connected_clients.add(websocket)
        try:
            await websocket.wait_closed()
        finally:
            print(f"[CONNECTION] Client disconnected from {websocket.remote_address}. Total clients: {len(self.connected_clients) - 1}")
            self.connected_clients.remove(websocket)

    async def send_to_all(self, message):
        """
        Sends a JSON message to all connected clients concurrently.
        Handles disconnections gracefully.
        """
        if not self.connected_clients:
            return

        message_str = json.dumps(message)
        tasks = [client.send(message_str) for client in self.connected_clients]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        disconnected_clients = set()
        client_list = list(self.connected_clients)
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                client = client_list[i]
                disconnected_clients.add(client)
                # Optionally log the error: print(f"Error sending to {client.remote_address}: {result}")

        # Remove clients that failed to send
        self.connected_clients.difference_update(disconnected_clients)


    async def fetch_all_candles(self):
        """Orchestrates fetching candles from multiple sources with fallbacks."""
        # Run synchronous network calls in threads to avoid blocking the event loop
        if UPSTOX_AVAILABLE and hasattr(config, 'ACCESS_TOKEN') and config.ACCESS_TOKEN:
            try:
                data = await asyncio.to_thread(self._fetch_candles_upstox)
                if data: return data
            except Exception as e: print(f"[WARN] Upstox fetch failed: {e}")
        
        try:
            data = await asyncio.to_thread(self._fetch_candles_tv)
            if data: return data
        except Exception as e: print(f"[WARN] TradingView fetch failed: {e}")
        
        return []

    async def publish_sentiment_update(self):
        """Calculates and broadcasts the `SENTIMENT_UPDATE` message every 30 seconds."""
        while True:
            # Run the synchronous update in a separate thread
            await asyncio.to_thread(self.update_pcr_and_breadth_sync)
            
            pcr = self.pcr_data.get("NIFTY", 1.0)
            adv = self.market_breadth.get("advances", 0)
            dec = self.market_breadth.get("declines", 1)
            regime = self._calculate_sentiment_regime()
            ratio = adv / dec if dec > 0 else adv

            message = {
                "type": "SENTIMENT_UPDATE", 
                "timestamp": int(time.time() * 1000), 
                "data": {
                    "regime": regime,
                    "pcr": pcr,
                    "advances": adv,
                    "declines": dec,
                    "pcrVelocity": 0.0,
                    "oiWallAbove": 0.0,
                    "oiWallBelow": 0.0
                }
            }
            await self.send_to_all(message)
            if self.connected_clients:
                print(f"[SENTIMENT] Broadcast update: {regime} (PCR: {pcr}, ADV/DEC: {round(ratio, 2)})")

            await asyncio.sleep(30)

    def update_pcr_and_breadth_sync(self):
        """Internal method to fetch latest PCR and Breadth data (Synchronous version)."""
        try:
            data = self.nse.get_market_breadth()
            if data and 'advance' in data:
                counts = data['advance'].get('count', {})
                self.market_breadth['advances'] = counts.get('Advances', 0)
                self.market_breadth['declines'] = counts.get('Declines', 0)
        except Exception as e:
            print(f"[WARN] NSE Breadth fetch failed: {e}")

        try:
            for sym in ["NIFTY", "BANKNIFTY"]:
                data = self.nse.get_option_chain_v3(sym, indices=True)
                if data and 'records' in data:
                    filtered = data.get('filtered', {})
                    if filtered:
                        ce_oi = filtered.get('CE', {}).get('totOI', 0)
                        pe_oi = filtered.get('PE', {}).get('totOI', 0)
                        if ce_oi > 0: self.pcr_data[sym] = round(pe_oi / ce_oi, 2)
        except Exception as e:
            print(f"[WARN] PCR update failed: {e}")

    async def publish_candles(self):
        """Continuously fetches and broadcasts `CANDLE_UPDATE` messages."""
        while True:
            all_candles_data = await self.fetch_all_candles()
            if all_candles_data:
                for candle_info in all_candles_data:
                    candle_data = candle_info["1m"]
                    sym = candle_info["symbol"]
                    ts = candle_info["timestamp"]
                    
                    # Persist to DB
                    self._persist_candle(sym, ts, candle_data)

                    message = {
                        "type": "CANDLE_UPDATE",
                        "timestamp": ts,
                        "data": {
                            "symbol": sym,
                            "candle": {
                                "open": float(candle_data.get("open", 0.0)),
                                "high": float(candle_data.get("high", 0.0)),
                                "low": float(candle_data.get("low", 0.0)),
                                "close": float(candle_data.get("close", 0.0)),
                                "volume": int(candle_data.get("volume", 0))
                            }
                        }
                    }
                    await self.send_to_all(message)
                if self.connected_clients:
                    print(f"[CANDLE] Broadcast and persisted {len(all_candles_data)} symbols.")
            await asyncio.sleep(10)

    def _calculate_sentiment_regime(self):
        """Calculates the current market regime based on PCR and market breadth."""
        pcr = self.pcr_data.get("NIFTY", 1.0)
        adv = self.market_breadth.get("advances", 0)
        dec = self.market_breadth.get("declines", 1)
        ratio = adv / dec if dec > 0 else adv

        if pcr < 0.8 and ratio > 1.5: return "COMPLETE_BULLISH"
        if pcr < 0.9 and ratio > 1.2: return "BULLISH"
        if pcr < 1.0 and ratio > 1.0: return "SIDEWAYS_BULLISH"
        if pcr > 1.2 and ratio < 0.7: return "COMPLETE_BEARISH"
        if pcr > 1.1 and ratio < 0.9: return "BEARISH"
        if pcr > 1.0 and ratio < 1.0: return "SIDEWAYS_BEARISH"
        return "SIDEWAYS"

    async def publish_market_updates(self):
        """
        Continuously fetches, combines, and broadcasts `MARKET_UPDATE` messages
        every 15 seconds, conforming to the primary data contract.
        """
        while True:
            pcr = self.pcr_data.get("NIFTY", 1.0)
            regime = self._calculate_sentiment_regime()

            all_candles_data = await self.fetch_all_candles()

            if all_candles_data:
                for candle_info in all_candles_data:
                    candle_data = candle_info["1m"]
                    sym = candle_info["symbol"]
                    ts = candle_info["timestamp"]
                    
                    # Persist to DB
                    self._persist_candle(sym, ts, candle_data)

                    message = {
                        "type": "MARKET_UPDATE",
                        "timestamp": ts,
                        "data": {
                            "symbol": sym,
                            "candle": {
                                "open": float(candle_data.get("open", 0.0)),
                                "high": float(candle_data.get("high", 0.0)),
                                "low": float(candle_data.get("low", 0.0)),
                                "close": float(candle_data.get("close", 0.0)),
                                "volume": int(candle_data.get("volume", 0))
                            },
                            "sentiment": {
                                "pcr": pcr,
                                "regime": regime
                            }
                        }
                    }
                    await self.send_to_all(message)
                if self.connected_clients:
                    print(f"[MARKET] Broadcast and persisted {len(all_candles_data)} symbols.")
            
            await asyncio.sleep(15)

    def _fetch_candles_upstox(self):
        """PRIMARY: Fetch historical candles for a specific date using Upstox API."""
        # This logic remains unchanged
        if not UPSTOX_AVAILABLE: return []
        upstox_candles = []
        try:
            configuration = upstox_client.Configuration()
            configuration.access_token = config.ACCESS_TOKEN
            history_api = upstox_client.HistoryV3Api(upstox_client.ApiClient(configuration))
            target_date = datetime.now().strftime("%Y-%m-%d")
            ts = int(datetime.strptime(target_date, "%Y-%m-%d").timestamp() * 1000)
            for sym in self.symbols:
                u_key = SymbolMaster.get_upstox_key(sym)
                if not u_key: continue
                try:
                    response = history_api.get_historical_candle_data1(instrument_key=u_key, unit='minutes', interval='1', to_date=target_date, from_date=target_date)
                    if response and hasattr(response, 'data') and hasattr(response.data, 'candles') and response.data.candles:
                        timestamp, op, hi, lo, ltp, vol, *_ = response.data.candles[-1]
                        upstox_candles.append({"symbol": sym, "timestamp": ts, "1m": {"open": float(op), "high": float(hi), "low": float(lo), "close": float(ltp), "volume": int(vol)}})
                except Exception as inner_e:
                     print(f"[UPSTOX INNER ERROR] {sym}: {inner_e}")
            if upstox_candles: print(f"[UPSTOX PRIMARY] Recovered {len(upstox_candles)} symbols for {target_date}.")
            return upstox_candles
        except Exception as e:
            print(f"[CRITICAL] Upstox Primary Failed: {e}")
            return []

    def _fetch_candles_tv(self):
        """Secondary: Fetch from TradingView Screener."""
        # This logic remains unchanged
        scanner = Query().select('name', 'open|1', 'high|1', 'low|1', 'close|1', 'volume|1').set_tickers(*self.tickers)
        data = scanner.get_scanner_data(cookies=None)
        candles = []
        if data and len(data) > 1:
            ts = int(time.time() * 1000)
            for _, row in data[1].iterrows():
                candles.append({"symbol": row['name'].split(':')[-1], "timestamp": ts, "1m": {"open": row['open|1'], "high": row['high|1'], "low": row['low|1'], "close": row['close|1'], "volume": row['volume|1']}})
        return candles

    async def publish_option_chain(self):
        """
        Periodically fetches and sends `OPTION_CHAIN_UPDATE` messages.
        """
        loop = asyncio.get_running_loop()
        while True:
            if TrendlyneDB and fetch_live_snapshot:
                for sym in ["NIFTY", "BANKNIFTY"]:
                    try:
                        chain = await loop.run_in_executor(None, fetch_live_snapshot, sym)
                        if chain:
                            message = {
                                "type": "OPTION_CHAIN_UPDATE",
                                "timestamp": int(time.time() * 1000),
                                "data": {
                                    "symbol": sym,
                                    "chain": chain
                                }
                            }
                            await self.send_to_all(message)
                    except Exception as e:
                        print(f"[OCR ERROR] {sym}: {e}")

            await asyncio.sleep(60) # Update chain every 60 seconds

    async def start(self):
        """Starts the WebSocket server and the data publishing tasks."""
        print(f"Starting SOS Data Bridge Server on ws://{self.host}:{self.port}")

        # Start data producers as background tasks
        asyncio.create_task(self.publish_candles())
        asyncio.create_task(self.publish_sentiment_update())
        asyncio.create_task(self.publish_option_chain())
        asyncio.create_task(self.publish_market_updates())

        # Start the WebSocket server
        server = await websockets.serve(self.connection_handler, "0.0.0.0", self.port)
        await server.wait_closed()

    def run(self):
        """Entry point for the server."""
        try:
            asyncio.run(self.start())
        except KeyboardInterrupt:
            print("\nShutting down server.")
        except Exception as e:
            print(f"Fatal error in run: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SOS Engine Data Bridge Server")
    parser.add_argument('--host', type=str, default='localhost', help='Host to bind the WebSocket server to')
    parser.add_argument('--port', type=int, default=8765, help='Port to bind the WebSocket server to')
    args = parser.parse_args()

    server = SOSDataBridgeServer(SYMBOLS, host=args.host, port=args.port)
    server.run()
