import argparse
import pandas as pd
from python_engine.core.option_chain_handler import OptionChainHandler
from python_engine.core.sentiment_handler import SentimentHandler
from python_engine.core.pattern_matcher_handler import PatternMatcherHandler
from python_engine.core.execution_handler import ExecutionHandler
from python_engine.models.data_models import MarketEvent, MessageType, VolumeBar, Sentiment, OptionChainData
from engine_config import Config
from python_engine.core.order_orchestrator import OrderOrchestrator
from python_engine.core.trade_logger import TradeLog
from data_sourcing.data_manager import DataManager
from python_engine.utils.atr_calculator import calculate_atr

def run_backtest(symbol: str, from_date: str = None, to_date: str = None):
    # Load configuration
    Config.load('config.json')
    access_token = Config.get('upstox_access_token')
   
    # Initialize handlers
    data_manager = DataManager(access_token=access_token)
    trade_log = TradeLog(f'backtest_{symbol}.csv')
    order_orchestrator = OrderOrchestrator(trade_log, data_manager, "backtest")
    option_chain_handler = OptionChainHandler()
    sentiment_handler = SentimentHandler()
    pattern_matcher_handler = PatternMatcherHandler(Config.get('strategies_dir'))
    execution_handler = ExecutionHandler(order_orchestrator)

    # Fetch and prepare all data before the loop
    candles_df = data_manager.get_historical_candles(symbol, n_bars=1000, from_date=from_date, to_date=to_date)
    

    if candles_df is None or candles_df.empty:
        print("Could not fetch historical data. Aborting.")
        return

    print(candles_df.head())
    candles_df['timestamp'] = pd.to_datetime(candles_df['timestamp'])

    candles_df.set_index('timestamp', inplace=True)
    candles_df.sort_index(inplace=True)

    candles_df['atr'] = calculate_atr(candles_df)

    market_breadth = data_manager.get_market_breadth() # This is less time-sensitive

    # The processing pipeline
    for timestamp, row in candles_df.iterrows():
        current_date_str = timestamp.strftime('%Y-%m-%d')

        # Fetch data specific to the current candle's date
        option_chain = data_manager.get_option_chain(symbol, date=current_date_str)
        pcr = data_manager.get_pcr(symbol, date=current_date_str)

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
            option_chain=option_chain,
            sentiment=Sentiment(pcr=pcr, advances=market_breadth.get('advances', 0), declines=market_breadth.get('declines', 0)) if pcr and market_breadth else None
        )

        # Pass the event through the handlers
        option_chain_handler.on_event(event)
        sentiment_handler.on_event(event)
        pattern_matcher_handler.on_event(event)
        execution_handler.on_event(event)

    trade_log.write_log_file()
