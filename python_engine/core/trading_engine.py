import time
import pandas as pd
import logging
from typing import List, Optional, Dict, Any
from python_engine.models.data_models import MarketEvent, MessageType, VolumeBar, Sentiment
from python_engine.core.market_structure_handler import MarketStructureHandler
from python_engine.core.sentiment_handler import SentimentHandler
from python_engine.core.option_chain_handler import OptionChainHandler
from python_engine.core.pattern_matcher_handler import PatternMatcherHandler
from python_engine.core.execution_handler import ExecutionHandler
from python_engine.data.repository import DataRepository
from python_engine.utils.atr_calculator import calculate_atr

# Standardized Logging
logger = logging.getLogger(__name__)

class TradingEngine:
    """
    Central Orchestrator for the SOS Handler-Based Trading Architecture.

    The TradingEngine manages the sequential pipeline of analysis and execution
    modules, providing a unified interface for both backtest and live operations.
    """

    def __init__(self, order_orchestrator: Any, data_manager: Any, strategy_dir: str):
        """
        Initializes the TradingEngine and its modular handler pipeline.

        Args:
            order_orchestrator (Any): Handler for trade execution and order management.
            data_manager (Any): Manager for remote data fallback (primarily for live).
            strategy_dir (str): Path to the directory containing strategy JSON files.
        """
        self.repository = DataRepository()
        self.data_manager = data_manager
        self.order_orchestrator = order_orchestrator

        # Initialize Core Analysis Pipeline
        self.market_structure = MarketStructureHandler()
        self.sentiment_handler = SentimentHandler()
        self.option_chain_handler = OptionChainHandler()
        self.pattern_matcher = PatternMatcherHandler(strategy_dir)
        self.execution_handler = ExecutionHandler(order_orchestrator, data_manager)

        # Sequential pipeline
        self.pipeline = [
            self.market_structure,
            self.option_chain_handler,
            self.sentiment_handler,
            self.pattern_matcher,
            self.execution_handler
        ]

    def run_backtest(self, symbol: str, candles_df: pd.DataFrame) -> None:
        """
        Executes a vectorized backtest over a dataframe of historical candles.

        Args:
            symbol (str): The symbol to backtest.
            candles_df (pd.DataFrame): Dataframe containing OHLCV data.
        """
        if candles_df is None or candles_df.empty:
            logger.warning("[TradingEngine] No data provided for backtest.")
            return

        logger.info(f"[TradingEngine] Starting vectorized backtest for {symbol} | {len(candles_df)} bars.")

        # Vectorized pre-calculations
        candles_df = candles_df.copy()
        candles_df['atr'] = calculate_atr(candles_df)

        last_date = None
        current_option_chain = None

        for timestamp, row in candles_df.iterrows():
            curr_date = timestamp.date().strftime('%Y-%m-%d')

            # Daily metadata caching
            if curr_date != last_date:
                current_option_chain = self.repository.get_option_chain(symbol, curr_date)
                last_date = curr_date

            # Efficient Sentiment Retrieval (Cached via Repository)
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

            # Construct Immutable MarketEvent for processing
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

            # Process through the sequential pipeline
            for handler in self.pipeline:
                handler.on_event(event)

    async def run_live(self, event_queue: Any) -> None:
        """
        Main asynchronous loop for live trading ingestion and processing.

        Args:
            event_queue (Any): Asyncio queue consuming real-time market events.
        """
        logger.info("[TradingEngine] Live engine pipeline activated.")
        while True:
            event = await event_queue.get()
            if event is None: break

            for handler in self.pipeline:
                handler.on_event(event)

            event_queue.task_done()
