import numpy as np
import logging
from typing import List, Dict, Optional, Any
from python_engine.models.data_models import MarketEvent, VolumeBar, MessageType

# Standardized Logging
logger = logging.getLogger(__name__)

class MarketStructureHandler:
    """
    Analyzes Market Structure using vectorized Price Action analysis.

    Attributes:
        window (int): Rolling window size for pivot detection.
        history_high (np.ndarray): Buffer for high prices.
        history_low (np.ndarray): Buffer for low prices.
        pivots_high (List[Dict[str, Any]]): List of identified Pivot Highs.
        pivots_low (List[Dict[str, Any]]): List of identified Pivot Lows.
        resistance_levels (List[float]): Sorted list of resistance hurdles.
        support_levels (List[float]): Sorted list of support hurdles.
    """

    def __init__(self, window: int = 5):
        """
        Initializes the MarketStructureHandler.

        Args:
            window (int): The number of bars on each side to confirm a pivot.
        """
        self.window = window
        self.history_high = np.array([], dtype=float)
        self.history_low = np.array([], dtype=float)
        self.history_ts = np.array([], dtype=int)

        self.pivots_high: List[Dict[str, Any]] = []
        self.pivots_low: List[Dict[str, Any]] = []
        self.support_levels: List[float] = []
        self.resistance_levels: List[float] = []
        self.max_history = window * 2 + 1

    def on_event(self, event: MarketEvent) -> None:
        """
        Processes a market event to update structure.

        Args:
            event (MarketEvent): The incoming market event containing candle data.
        """
        if event.type == MessageType.MARKET_UPDATE and event.candle:
            candle = event.candle
            self.history_high = np.append(self.history_high, candle.high)
            self.history_low = np.append(self.history_low, candle.low)
            self.history_ts = np.append(self.history_ts, candle.timestamp)

            if len(self.history_high) > self.max_history:
                self.history_high = self.history_high[1:]
                self.history_low = self.history_low[1:]
                self.history_ts = self.history_ts[1:]
                self._calculate_pivots_vectorized()
                self._update_hurdles(event)

            # Inject structure into event for downstream handlers
            event.market_structure = self.get_immediate_hurdles(candle.close)
            event.market_structure['regime'] = self.get_structure_sentiment()

    def _calculate_pivots_vectorized(self) -> None:
        """Identifies Pivot Highs and Lows using vectorized numpy operations."""
        mid_idx = self.window

        # Vectorized check: mid point is higher than all others in window
        is_pivot_high = np.all(self.history_high[mid_idx] >= self.history_high)
        if is_pivot_high:
            price = self.history_high[mid_idx]
            ts = self.history_ts[mid_idx]
            if not self.pivots_high or self.pivots_high[-1]["timestamp"] != ts:
                self.pivots_high.append({"price": price, "timestamp": ts})
                if len(self.pivots_high) > 10: self.pivots_high.pop(0)

        # Vectorized check: mid point is lower than all others in window
        is_pivot_low = np.all(self.history_low[mid_idx] <= self.history_low)
        if is_pivot_low:
            price = self.history_low[mid_idx]
            ts = self.history_ts[mid_idx]
            if not self.pivots_low or self.pivots_low[-1]["timestamp"] != ts:
                self.pivots_low.append({"price": price, "timestamp": ts})
                if len(self.pivots_low) > 10: self.pivots_low.pop(0)

    def _update_hurdles(self, event: MarketEvent) -> None:
        """
        Updates support and resistance levels based on pivots and OI Walls.

        Args:
            event (MarketEvent): The event containing sentiment/OI data.
        """
        self.resistance_levels = sorted(list(set([p["price"] for p in self.pivots_high])))
        self.support_levels = sorted(list(set([p["price"] for p in self.pivots_low])))

        # Add OI Walls as institutional hurdles
        if event.sentiment:
            if event.sentiment.oi_wall_above:
                self.resistance_levels.append(event.sentiment.oi_wall_above)
            if event.sentiment.oi_wall_below:
                self.support_levels.append(event.sentiment.oi_wall_below)

        self.resistance_levels.sort()
        self.support_levels.sort()

    def get_immediate_hurdles(self, current_price: float) -> Dict[str, Optional[float]]:
        """
        Returns the nearest support and resistance levels.

        Args:
            current_price (float): The current spot price.

        Returns:
            Dict[str, Optional[float]]: Keys 'support' and 'resistance'.
        """
        resistance = next((r for r in self.resistance_levels if r > current_price), None)
        support = next((s for s in reversed(self.support_levels) if s < current_price), None)
        return {"support": support, "resistance": resistance}

    def get_structure_sentiment(self) -> str:
        """
        Determines market structure sentiment based on Pivot sequences.

        Returns:
            str: 'BULLISH', 'BEARISH', or 'SIDEWAYS'.
        """
        if len(self.pivots_high) < 2 or len(self.pivots_low) < 2:
            return "SIDEWAYS"

        hh = self.pivots_high[-1]["price"] > self.pivots_high[-2]["price"]
        hl = self.pivots_low[-1]["price"] > self.pivots_low[-2]["price"]
        lh = self.pivots_high[-1]["price"] < self.pivots_high[-2]["price"]
        ll = self.pivots_low[-1]["price"] < self.pivots_low[-2]["price"]

        if hh and hl: return "BULLISH"
        if lh and ll: return "BEARISH"
        return "SIDEWAYS"
