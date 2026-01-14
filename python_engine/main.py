import asyncio
import json
import websockets
from python_engine.core.option_chain_handler import OptionChainHandler
from python_engine.core.sentiment_handler import SentimentHandler
from python_engine.core.pattern_matcher_handler import PatternMatcherHandler
from python_engine.core.execution_handler import ExecutionHandler
from python_engine.models.data_models import MarketEvent, MessageType, VolumeBar, Sentiment, OptionChainData
from python_engine.config import Config
from python_engine.core.order_orchestrator import OrderOrchestrator

async def main():
    # Load configuration
    Config.load('config.json')

    # Initialize handlers
    order_orchestrator = OrderOrchestrator()
    option_chain_handler = OptionChainHandler()
    sentiment_handler = SentimentHandler()
    pattern_matcher_handler = PatternMatcherHandler(Config.get('strategies_dir'))
    execution_handler = ExecutionHandler(order_orchestrator)

    uri = Config.get('websocket_uri')
    async with websockets.connect(uri) as websocket:
        while True:
            message_str = await websocket.recv()
            message = json.loads(message_str)

            message_type_str = message.get("type", "UNKNOWN").upper()
            try:
                message_type = MessageType[message_type_str]
            except KeyError:
                message_type = MessageType.UNKNOWN

            event = MarketEvent(
                type=message_type,
                timestamp=message.get("timestamp", 0),
                symbol=message.get("symbol"),
                candle=VolumeBar(**message['candle']) if 'candle' in message else None,
                sentiment=Sentiment(**message['sentiment']) if 'sentiment' in message else None,
                option_chain=[OptionChainData(**d) for d in message['chain']] if 'chain' in message else None
            )

            # The processing pipeline
            option_chain_handler.on_event(event)
            sentiment_handler.on_event(event)
            pattern_matcher_handler.on_event(event)
            execution_handler.on_event(event)

if __name__ == "__main__":
    asyncio.run(main())
