import pandas as pd
from typing import List, Dict, Optional
from python_engine.models.data_models import MarketEvent, VolumeBar, MessageType

class MarketStructureHandler:
    """
    Handles Market Structure: Swings (Pivots), Hurdles (Support/Resistance),
    and Trend determination based on Price Action.
    """
    def __init__(self, window: int = 5):
        self.window = window
        self.history: List[VolumeBar] = []
        self.pivots_high: List[Dict] = []
        self.pivots_low: List[Dict] = []
        self.support_levels: List[float] = []
        self.resistance_levels: List[float] = []

    def on_event(self, event: MarketEvent):
        if event.type == MessageType.MARKET_UPDATE and event.candle:
            self.history.append(event.candle)
            if len(self.history) > (self.window * 2 + 1):
                self.history.pop(0)
                self._calculate_pivots()
                self._update_hurdles(event)

    def _calculate_pivots(self):
        """Identifies Pivot Highs and Lows in the history window."""
        if len(self.history) < (self.window * 2 + 1):
            return

        mid_idx = self.window
        target = self.history[mid_idx]

        # Check Pivot High
        is_high = True
        for i in range(len(self.history)):
            if i == mid_idx: continue
            if self.history[i].high >= target.high:
                is_high = False
                break
        if is_high:
            pivot = {"price": target.high, "timestamp": target.timestamp}
            if not self.pivots_high or self.pivots_high[-1]["timestamp"] != pivot["timestamp"]:
                self.pivots_high.append(pivot)
                if len(self.pivots_high) > 10: self.pivots_high.pop(0)

        # Check Pivot Low
        is_low = True
        for i in range(len(self.history)):
            if i == mid_idx: continue
            if self.history[i].low <= target.low:
                is_low = False
                break
        if is_low:
            pivot = {"price": target.low, "timestamp": target.timestamp}
            if not self.pivots_low or self.pivots_low[-1]["timestamp"] != pivot["timestamp"]:
                self.pivots_low.append(pivot)
                if len(self.pivots_low) > 10: self.pivots_low.pop(0)

    def _update_hurdles(self, event: MarketEvent):
        """Updates support and resistance levels based on pivots and OI Walls."""
        self.resistance_levels = sorted([p["price"] for p in self.pivots_high], reverse=True)
        self.support_levels = sorted([p["price"] for p in self.pivots_low])

        # Add OI Walls as hurdles if available
        if event.sentiment:
            if event.sentiment.oi_wall_above and event.sentiment.oi_wall_above not in self.resistance_levels:
                self.resistance_levels.append(event.sentiment.oi_wall_above)
            if event.sentiment.oi_wall_below and event.sentiment.oi_wall_below not in self.support_levels:
                self.support_levels.append(event.sentiment.oi_wall_below)

        self.resistance_levels.sort()
        self.support_levels.sort()

    def get_immediate_hurdles(self, current_price: float) -> Dict[str, Optional[float]]:
        """Returns the nearest support and resistance levels."""
        resistance = next((r for r in self.resistance_levels if r > current_price), None)
        support = next((s for s in reversed(self.support_levels) if s < current_price), None)
        return {"support": support, "resistance": resistance}

    def get_structure_sentiment(self, current_price: float) -> str:
        """Determines structure sentiment: BULLISH (Higher Highs/Lows), BEARISH (Lower Highs/Lows), SIDEWAYS."""
        if len(self.pivots_high) < 2 or len(self.pivots_low) < 2:
            return "SIDEWAYS"

        hh = self.pivots_high[-1]["price"] > self.pivots_high[-2]["price"]
        hl = self.pivots_low[-1]["price"] > self.pivots_low[-2]["price"]
        lh = self.pivots_high[-1]["price"] < self.pivots_high[-2]["price"]
        ll = self.pivots_low[-1]["price"] < self.pivots_low[-2]["price"]

        if hh and hl: return "BULLISH"
        if lh and ll: return "BEARISH"
        return "SIDEWAYS"
