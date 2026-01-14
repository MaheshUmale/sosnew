import asyncio
import json
from python_engine.core.option_chain_handler import OptionChainHandler
from python_engine.core.sentiment_handler import SentimentHandler
from python_engine.core.pattern_matcher_handler import PatternMatcherHandler
from python_engine.core.execution_handler import ExecutionHandler
from python_engine.models.data_models import MarketEvent, MessageType, VolumeBar, Sentiment, OptionChainData
from config import Config
from python_engine.core.order_orchestrator import OrderOrchestrator
from data_sourcing.data_manager import DataManager
import upstox_client
from upstox_client.rest import ApiException
import websockets
from datetime import datetime

class LiveTradingEngine:
    def __init__(self):
        # Initialize handlers
        self.order_orchestrator = OrderOrchestrator()
        self.option_chain_handler = OptionChainHandler()
        self.sentiment_handler = SentimentHandler()
        self.pattern_matcher_handler = PatternMatcherHandler(Config.get('strategies_dir'))
        self.execution_handler = ExecutionHandler(self.order_orchestrator)
        self.data_manager = DataManager()

        # Upstox configuration
        self.configuration = upstox_client.Configuration()
        self.configuration.access_token = Config.get('upstox_access_token')

        self.symbols = [
            'NSE_INDEX|Nifty 50',
            'NSE_INDEX|Nifty Bank',
        ]

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

    async def run(self):
        response = await self.get_market_data_feed_authorize()

        if not response or not response.data:
            print("[ERROR] Failed to get WebSocket authorization")
            return

        ws_url = response.data.authorized_redirect_uri

        async with websockets.connect(ws_url) as websocket:
            subscribe_message = {
                "guid": "someguid",
                "method": "sub",
                "data": {
                    "mode": "full",
                    "instrumentKeys": self.symbols
                }
            }
            await websocket.send(json.dumps(subscribe_message))

            async for message in websocket:
                data = json.loads(message)
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


def main():
    Config.load('config.json')
    engine = LiveTradingEngine()
    asyncio.run(engine.run())

if __name__ == "__main__":
    main()
