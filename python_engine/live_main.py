import asyncio
import json
import threading
import time
from datetime import datetime

import upstox_client
from upstox_client.feeder.market_data_streamer_v3 import MarketDataStreamerV3

from python_engine.core.option_chain_handler import OptionChainHandler
from python_engine.core.sentiment_handler import SentimentHandler
from python_engine.core.pattern_matcher_handler import PatternMatcherHandler
from python_engine.core.execution_handler import ExecutionHandler
from python_engine.models.data_models import MarketEvent, MessageType, VolumeBar
from engine_config import Config
from python_engine.core.order_orchestrator import OrderOrchestrator
from python_engine.core.trade_logger import TradeLog

# --- Global State for Streamer ---
streamer = None
subscribed_instruments = set()

class LiveTradingEngine:
    def __init__(self, loop):
        self.loop = loop
        self.trade_log = TradeLog('live_trades.csv')
        self.order_orchestrator = OrderOrchestrator(self.trade_log)
        self.option_chain_handler = OptionChainHandler()
        self.sentiment_handler = SentimentHandler()
        self.pattern_matcher_handler = PatternMatcherHandler(Config.get('strategies_dir'))
        self.execution_handler = ExecutionHandler(self.order_orchestrator)

        self.access_token = Config.get('upstox_access_token')
        self.symbols = {
            'NSE_INDEX|Nifty 50',
            'NSE_INDEX|Nifty Bank',
        }
        subscribed_instruments.update(self.symbols)

    def on_message(self, message):
        """Thread-safe callback to schedule message processing on the main event loop."""
        self.loop.call_soon_threadsafe(asyncio.create_task, self.process_message(message))

    async def process_message(self, data):
        """Asynchronously processes the market data."""
        if 'feeds' in data:
            for symbol_key, feed in data['feeds'].items():
                ohlc = feed.get('ff', {}).get('marketFF', {}).get('ohlc')
                if ohlc:
                    event = MarketEvent(
                        type=MessageType.MARKET_UPDATE,
                        timestamp=datetime.now().timestamp(),
                        symbol=symbol_key,
                        candle=VolumeBar(
                            symbol=symbol_key,
                            timestamp=datetime.now().timestamp(),
                            open=ohlc['o'],
                            high=ohlc['h'],
                            low=ohlc['l'],
                            close=ohlc['c'],
                            volume=feed.get('ff', {}).get('marketFF', {}).get('vtt', 0)
                        )
                    )
                    self.option_chain_handler.on_event(event)
                    self.sentiment_handler.on_event(event)
                    self.pattern_matcher_handler.on_event(event)
                    self.execution_handler.on_event(event)

    def on_open(self):
        print("Streamer connection opened.")

    def on_error(self, error):
        print(f"Streamer Error: {error}")

    def on_close(self, code, reason):
        print(f"Streamer connection closed. Code: {code}, Reason: {reason}")

    def on_auto_reconnect_stopped(self, code, reason):
        print(f"Auto-reconnect stopped. Code: {code}, Reason: {reason}")

    def start_websocket_thread(self):
        """Starts the Upstox SDK MarketDataStreamerV3 in a background thread."""

        def run_streamer():
            global streamer
            print(f"Starting UPSTOX SDK Streamer with {len(self.symbols)} instruments...")

            configuration = upstox_client.Configuration()
            configuration.access_token = self.access_token

            try:
                api_client = upstox_client.ApiClient(configuration)
                streamer = MarketDataStreamerV3(api_client, list(subscribed_instruments), "full")

                streamer.on("message", self.on_message)
                streamer.on("open", self.on_open)
                streamer.on("error", self.on_error)
                streamer.on("close", self.on_close)
                streamer.on("autoReconnectStopped", self.on_auto_reconnect_stopped)

                streamer.auto_reconnect(True, 5, 5)

                # --- Periodic Subscription (Keep-Alive) ---
                def subscription_keep_alive(streamer_ref):
                    while True:
                        time.sleep(50)
                        try:
                            instruments = list(subscribed_instruments)
                            print(f"Sending periodic subscription for {len(instruments)} instruments...{datetime.now()}")
                            streamer_ref.subscribe(instruments, "full")
                        except Exception as e:
                            print(f"Periodic subscription failed: {e}")

                ka_thread = threading.Thread(target=subscription_keep_alive, args=(streamer,), daemon=True)
                ka_thread.start()

                print("Connecting to Upstox V3 via SDK...")
                streamer.connect()

            except Exception as e:
                print(f"SDK Streamer Fatal Error: {e}")

        t = threading.Thread(target=run_streamer, daemon=True)
        t.start()
        return t

    async def start(self):
        if not self.access_token:
            print("[ERROR] Upstox access token not found. Please add it to config.json.")
            print("         'upstox_access_token': 'YOUR_TOKEN'")
            return

        self.start_websocket_thread()
        print("Live trading engine started. Waiting for market data...")
        # Keep the main async thread alive
        while True:
            await asyncio.sleep(1)


async def run_live():
    Config.load('config.json')
    loop = asyncio.get_running_loop()
    engine = LiveTradingEngine(loop)
    await engine.start()
