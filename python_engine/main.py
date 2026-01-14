import argparse
import pandas as pd
from python_engine.core.option_chain_handler import OptionChainHandler
from python_engine.core.sentiment_handler import SentimentHandler
from python_engine.core.pattern_matcher_handler import PatternMatcherHandler
from python_engine.core.execution_handler import ExecutionHandler
from python_engine.models.data_models import MarketEvent, MessageType, VolumeBar, Sentiment, OptionChainData
from python_engine.config import Config
from python_engine.core.order_orchestrator import OrderOrchestrator
from data_sourcing.data_manager import DataManager
from python_engine.utils.atr_calculator import calculate_atr

def main(symbol: str):
    # Load configuration
    Config.load('config.json')

    # Initialize handlers
    order_orchestrator = OrderOrchestrator()
    option_chain_handler = OptionChainHandler()
    sentiment_handler = SentimentHandler()
    pattern_matcher_handler = PatternMatcherHandler(Config.get('strategies_dir'))
    execution_handler = ExecutionHandler(order_orchestrator)
    data_manager = DataManager()

    # Fetch all data before the loop
    candles_df = data_manager.get_historical_candles(symbol, n_bars=1000)

    # Calculate ATR
    candles_df['atr'] = calculate_atr(candles_df)

    # The processing pipeline
    if candles_df is not None and not candles_df.empty:
        for timestamp, row in candles_df.iterrows():
            # Fetch fresh data for each timestamp
            option_chain = data_manager.get_option_chain(symbol)
            pcr = data_manager.get_pcr(symbol)
            market_breadth = data_manager.get_market_breadth()

            # Create a MarketEvent from the row
            event = MarketEvent(
                type=MessageType.MARKET_UPDATE,
                timestamp=timestamp.timestamp(),
                symbol=symbol,
                candle=VolumeBar(
                    symbol=symbol,
                    timestamp=timestamp.timestamp(),
                    open=row['open'],
                    high=row['high'],
                    low=row['low'],
                    close=row['close'],
                    volume=row['volume'],
                    atr=row['atr']
                ),
                option_chain=[OptionChainData(**d) for d in option_chain] if option_chain else None,
                sentiment=Sentiment(pcr=pcr, advances=market_breadth.get('advances', 0), declines=market_breadth.get('declines', 0)) if pcr and market_breadth else None
            )

            # Pass the event through the handlers
            option_chain_handler.on_event(event)
            sentiment_handler.on_event(event)
            pattern_matcher_handler.on_event(event)
            execution_handler.on_event(event)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the Python trading engine for a specific symbol.")
    parser.add_argument('symbol', type=str, help='The symbol to run the backtest for.')
    args = parser.parse_args()
    main(args.symbol)
