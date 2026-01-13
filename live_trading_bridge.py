"""
SOS Live Trading - Startup Script
Connects to Upstox WebSocket for real-time data and starts Java engine
"""

import asyncio
import websockets
import json
import upstox_client
from upstox_client.rest import ApiException
import config
from datetime import datetime
import subprocess
import sys

class LiveTradingBridge:
    def __init__(self):
        self.configuration = upstox_client.Configuration()
        self.configuration.access_token = config.ACCESS_TOKEN
        
        # Symbols to subscribe (add your universe)
        self.symbols = [
            'NSE_INDEX|Nifty 50',
            'NSE_INDEX|Nifty Bank',
            # Add more symbols as needed
        ]
        
        self.java_process = None
        self.websocket = None
    
    async def get_market_data_feed_authorize(self):
        """Get authorization for market data feed"""
        api_version = '2.0'
        api_instance = upstox_client.WebsocketApi(upstox_client.ApiClient(self.configuration))
        
        try:
            api_response = await api_instance.get_market_data_feed_authorize(api_version)
            return api_response
        except ApiException as e:
            print(f"Exception when getting WebSocket authorization: {e}")
            return None
    
    def start_java_engine(self):
        """Start the Java backtest engine"""
        print("[Java Engine] Starting...")
        java_dir = "d:/SOS/Scalping-Orchestration-System-SOS-/sos-engine"
        
        self.java_process = subprocess.Popen(
            ['java', '-jar', 'target/sos-engine-1.0-SNAPSHOT.jar'],
            cwd=java_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        print("[Java Engine] Started (waiting for WebSocket connection...)")
    
    async def stream_market_data(self):
        """Stream real-time market data to Java engine"""
        # Get WebSocket authorization
        response = await self.get_market_data_feed_authorize()
        
        if not response or not response.data:
            print("[ERROR] Failed to get WebSocket authorization")
            return
        
        ws_url = response.data.authorized_redirect_uri
        print(f"[WebSocket] Connecting to: {ws_url}")
        
        try:
            async with websockets.connect(ws_url) as websocket:
                self.websocket = websocket
                print("[WebSocket] Connected!")
                
                # Subscribe to market data
                subscribe_message = {
                    "guid": "someguid",
                    "method": "sub",
                    "data": {
                        "mode": "full",
                        "instrumentKeys": self.symbols
                    }
                }
                
                await websocket.send(json.dumps(subscribe_message))
                print(f"[Subscribe] Sent for {len(self.symbols)} symbols")
                
                # Forward data to Java engine via localhost WebSocket
                async for message in websocket:
                    data = json.loads(message)
                    
                    # Transform Upstox format to SOS format
                    if 'feeds' in data:
                        for symbol_key, feed in data['feeds'].items():
                            # Extract relevant data
                            sos_message = {
                                "type": "MARKET_UPDATE",
                                "timestamp": datetime.now().isoformat(),
                                "data": {
                                    "symbol": symbol_key,
                                    "candle": {
                                        "open": feed.get('ohlc', {}).get('open', 0),
                                        "high": feed.get('ohlc', {}).get('high', 0),
                                        "low": feed.get('ohlc', {}).get('low', 0),
                                        "close": feed.get('ohlc', {}).get('close', 0),
                                        "volume": feed.get('volume', 0)
                                    },
                                    "sentiment": {
                                        "upper_circuit": feed.get('upper_circuit_limit', 0),
                                        "lower_circuit": feed.get('lower_circuit_limit', 0)
                                    }
                                }
                            }
                            
                            # Send to Java engine (port 8765)
                            await self.forward_to_java(sos_message)
        
        except Exception as e:
            print(f"[WebSocket Error] {e}")
    
    async def forward_to_java(self, message):
        """Forward market data to Java engine WebSocket server"""
        try:
            async with websockets.connect('ws://localhost:8765') as ws:
                await ws.send(json.dumps(message))
        except Exception as e:
            pass  # Java engine might not be ready yet
    
    def run(self):
        """Start live trading system"""
        print("=" * 60)
        print(f"SOS LIVE TRADING - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)
        
        # Start Java engine
        self.start_java_engine()
        
        # Wait a bit for Java to start
        import time
        time.sleep(3)
        
        # Start data streaming
        print("\n[Live Data] Starting real-time feed...")
        asyncio.run(self.stream_market_data())

if __name__ == "__main__":
    bridge = LiveTradingBridge()
    
    try:
        bridge.run()
    except KeyboardInterrupt:
        print("\n[Shutdown] Stopping live trading...")
        if bridge.java_process:
            bridge.java_process.terminate()
        sys.exit(0)
