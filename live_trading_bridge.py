"""
SOS Live Trading - Startup Script (V3 API)
Connects to Upstox WebSocket for real-time data and starts Java engine
"""
import asyncio
import websockets
import json
import upstox_client
import config
from datetime import datetime
import subprocess
import sys

class LiveTradingBridgeV3:
    def __init__(self):
        # Configure the Upstox API client
        self.api_client = upstox_client.ApiClient(
            configuration=upstox_client.Configuration(),
            header_name='Authorization',
            header_value=f'Bearer {config.ACCESS_TOKEN}'
        )

        # Define the symbols to subscribe to
        self.symbols = ['NSE_INDEX|Nifty 50', 'NSE_INDEX|Nifty Bank']

        # Create an instance of the MarketDataStreamerV3
        self.streamer = upstox_client.MarketDataStreamerV3(
            api_client=self.api_client,
            instrumentKeys=self.symbols,
            mode='full'  # Subscribe to the full market data feed
        )

        self.java_process = None

    def start_java_engine(self):
        """Start the Java backtest engine"""
        print("[Java Engine] Starting...")
        java_dir = "engine"

        try:
            self.java_process = subprocess.Popen(
                ['java', '-jar', 'target/sos-engine-1.0-SNAPSHOT.jar'],
                cwd=java_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            print("[Java Engine] Started (waiting for WebSocket connection...)")
        except FileNotFoundError:
            print("[ERROR] Java engine JAR file not found. Please build the engine first.")
            sys.exit(1)

    async def forward_to_java(self, message):
        """Forward market data to the Java engine's WebSocket server."""
        try:
            async with websockets.connect('ws://localhost:8765') as ws:
                await ws.send(json.dumps(message))
        except ConnectionRefusedError:
            # The Java engine might not be ready yet.
            # In a real application, you'd want a more robust way to handle this.
            pass
        except Exception as e:
            print(f"[Java Forwarding Error] {e}")

    def run(self):
        """Start the live trading system."""
        print("=" * 60)
        print(f"SOS LIVE TRADING (V3) - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)

        # Start the Java engine
        self.start_java_engine()

        # Wait a moment for the Java engine to initialize
        import time
        time.sleep(5)

        # Define the event handlers for the streamer
        def on_open(ws):
            print("[Streamer] Connected! Subscribing to instruments...")
            self.streamer.subscribe(self.symbols, 'full')

        def on_error(ws, error):
            print(f"[Streamer Error] {error}")

        async def on_message(ws, message):
            """
            This is the core of the bridge. It receives data from the Upstox SDK,
            transforms it, and forwards it to the Java engine.
            """
            # The SDK has already decoded the Protobuf message into a Python dict
            for symbol_key, feed in message.get('feeds', {}).items():

                # Check for LTPC data
                ltpc = feed.get('ltpc', {})
                if not ltpc:
                    continue # Skip if there's no price data

                # The 'full' feed might not always have OHLC data in every message.
                # We will extract what we can, and the Java engine will have to handle
                # any missing fields.
                ohlc = {}
                market_ohlc = feed.get('marketOHLC', {}).get('ohlc', [])
                if market_ohlc:
                    # Assuming the first OHLC packet is the most relevant
                    ohlc = {
                        "open": market_ohlc[0].get('open', 0),
                        "high": market_ohlc[0].get('high', 0),
                        "low": market_ohlc[0].get('low', 0),
                        "close": market_ohlc[0].get('close', 0),
                        "volume": market_ohlc[0].get('volume', 0),
                    }

                sos_message = {
                    "type": "MARKET_UPDATE",
                    "timestamp": datetime.now().isoformat(),
                    "data": {
                        "symbol": symbol_key,
                        "candle": {
                            "open": ohlc.get('open', ltpc.get('ltp')),
                            "high": ohlc.get('high', ltpc.get('ltp')),
                            "low": ohlc.get('low', ltpc.get('ltp')),
                            "close": ltpc.get('ltp'), # LTP is the most recent close
                            "volume": ohlc.get('volume', 0)
                        },
                        "ltp": ltpc.get('ltp'),
                        # Sentiment data is not directly available in the V3 feed.
                        # We will send placeholder values.
                        "sentiment": {
                            "upper_circuit": 0,
                            "lower_circuit": 0,
                        }
                    }
                }

                await self.forward_to_java(sos_message)

        # Register the event handlers
        self.streamer.on('open', on_open)
        self.streamer.on('error', on_error)
        self.streamer.on('message', lambda ws, msg: asyncio.run(on_message(ws, msg)))

        # Start the streamer
        # This will block until the connection is closed.
        print("\n[Live Data] Starting real-time feed...")
        self.streamer.connect()

    def stop(self):
        """Stop the live trading system."""
        print("\n[Shutdown] Stopping live trading...")
        if self.streamer:
            self.streamer.disconnect()
        if self.java_process:
            self.java_process.terminate()
            self.java_process.wait()
        print("[Shutdown] Complete.")

if __name__ == "__main__":
    bridge = LiveTradingBridgeV3()
    try:
        bridge.run()
    except KeyboardInterrupt:
        bridge.stop()
        sys.exit(0)
