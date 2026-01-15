from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional

class TradeOutcome(Enum):
    WIN = 'WIN'
    LOSS = 'LOSS'
    IN_PROGRESS = 'IN_PROGRESS'

    def __str__(self):
        return self.value

class TradeSide(Enum):
    BUY = 'BUY'
    SELL = 'SELL'

    def __str__(self):
        return self.value

@dataclass
class Trade:
    trade_id: str
    pattern_id: str
    symbol: str
    side: TradeSide
    entry_time: datetime
    entry_price: float
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    outcome: TradeOutcome = TradeOutcome.IN_PROGRESS

@dataclass
class Position:
    symbol: str
    side: TradeSide
    entry_price: float
    entry_time: datetime
    stop_loss: float
    take_profit: float
    trade_id: str
