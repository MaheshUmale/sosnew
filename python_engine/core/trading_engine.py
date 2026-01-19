import time
import pandas as pd
from typing import List, Optional, Callable
from python_engine.models.data_models import MarketEvent, MessageType, VolumeBar, Sentiment, OptionChainData
from python_engine.core.market_structure_handler import MarketStructureHandler
from python_engine.core.sentiment_handler import SentimentHandler
from python_engine.core.option_chain_handler import OptionChainHandler
from python_engine.core.pattern_matcher_handler import PatternMatcherHandler
from python_engine.core.execution_handler import ExecutionHandler
from python_engine.data.repository import DataRepository
from python_engine.utils.atr_calculator import calculate_atr

class TradingEngine:
    """
    Unified engine that orchestrates the trading pipeline for both backtest and live modes.
    """
    def __init__(self, order_orchestrator, data_manager, strategy_dir: str):
        self.repository = DataRepository()
        self.data_manager = data_manager # Still needed for remote fallback in live
        self.order_orchestrator = order_orchestrator

        # Core Handlers
        self.market_structure = MarketStructureHandler()
        self.sentiment_handler = SentimentHandler()
        self.option_chain_handler = OptionChainHandler()
        self.pattern_matcher = PatternMatcherHandler(strategy_dir)
        self.execution_handler = ExecutionHandler(order_orchestrator, data_manager)

        self.pipeline = [
            self.market_structure,
            self.option_chain_handler,
            self.sentiment_handler,
            self.pattern_matcher,
            self.execution_handler
        ]

    def run_backtest(self, symbol: str, candles_df: pd.DataFrame):
        """Processes a dataframe of historical candles."""
        if candles_df is None or candles_df.empty:
            print("[TradingEngine] No data to backtest.")
            return

        print(f"[TradingEngine] Starting backtest for {symbol} with {len(candles_df)} bars.")

        # Pre-calculate ATR
        candles_df = candles_df.copy()
        candles_df['atr'] = calculate_atr(candles_df)

        last_date = None
        current_option_chain = None

        for timestamp, row in candles_df.iterrows():
            curr_date = timestamp.date().strftime('%Y-%m-%d')

            # Daily setup
            if curr_date != last_date:
                current_option_chain = self.repository.get_option_chain(symbol, curr_date)
                last_date = curr_date

            # Prepare Sentiment
            stats_dict = self.repository.get_closest_stats(symbol, timestamp)
            sentiment = None
            if stats_dict:
                sentiment = Sentiment(
                    pcr=stats_dict.get('pcr', 1.0),
                    pcr_velocity=stats_dict.get('pcr_velocity', 0.0),
                    oi_wall_above=stats_dict.get('oi_wall_above', 0.0),
                    oi_wall_below=stats_dict.get('oi_wall_below', 0.0),
                    smart_trend=stats_dict.get('smart_trend', 'Neutral'),
                    advances=stats_dict.get('advances', 0),
                    declines=stats_dict.get('declines', 0)
                )

            # Construct MarketEvent
            event = MarketEvent(
                type=MessageType.MARKET_UPDATE,
                timestamp=int(timestamp.timestamp()),
                symbol=symbol,
                candle=VolumeBar(
                    symbol=symbol,
                    timestamp=int(timestamp.timestamp()),
                    open=row['open'],
                    high=row['high'],
                    low=row['low'],
                    close=row['close'],
                    volume=row['volume'],
                    atr=row['atr']
                ),
                sentiment=sentiment,
                option_chain=current_option_chain
            )

            # Inject market structure info into event (optional, but handlers can access it)
            # Actually, we just pass the event through the pipeline
            for handler in self.pipeline:
                handler.on_event(event)

    async def run_live(self, symbol_list: List[str], event_queue):
        """Main loop for live trading, consuming from a queue."""
        print("[TradingEngine] Live engine started.")
        while True:
            event = await event_queue.get()
            if event is None: break

            for handler in self.pipeline:
                handler.on_event(event)

            event_queue.task_done()
