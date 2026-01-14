from dataclasses import dataclass, field
from typing import List, Dict, Optional
from enum import Enum

@dataclass
class VolumeBar:
    symbol: str
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: int
    atr: float = 0.0

@dataclass
class Sentiment:
    pcr: float
    advances: int
    declines: int
    pcr_velocity: float = 0.0
    oi_wall_above: float = 0.0
    oi_wall_below: float = 0.0
    regime: Optional[str] = None

@dataclass
class OptionChainData:
    strike: int
    call_oi: int
    put_oi: int
    call_oi_chg: int
    put_oi_chg: int

@dataclass
class RegimeConfig:
    allow_entry: bool = True
    tp_mult: float = 1.0
    quantity_mod: float = 1.0
    buffer_atr: float = 0.5

@dataclass
class Phase:
    id: str
    conditions: List[str]
    capture: Dict[str, str]
    timeout: int

@dataclass
class Execution:
    side: str
    entry: str
    sl: str
    tp: str
    option_selection: str

@dataclass
class PatternDefinition:
    pattern_id: str
    regime_config: Dict[str, RegimeConfig]
    phases: List[Phase]
    execution: Execution

class PatternState:
    def __init__(self, pattern_id: str, symbol: str, initial_phase_id: str):
        self.pattern_id = pattern_id
        self.symbol = symbol
        self.current_phase_id = initial_phase_id
        self.captured_variables: Dict[str, float] = {}
        self.timeout_counter = 0

    def move_to(self, next_phase_id: str):
        self.current_phase_id = next_phase_id
        self.timeout_counter = 0

    def capture(self, variable_name: str, value: float):
        self.captured_variables[variable_name] = value

    def reset(self, initial_phase_id: str):
        self.current_phase_id = initial_phase_id
        self.captured_variables.clear()
        self.timeout_counter = 0

    def increment_timeout(self):
        self.timeout_counter += 1

    def is_timed_out(self, timeout: int) -> bool:
        return timeout > 0 and self.timeout_counter >= timeout

class MessageType(Enum):
    MARKET_UPDATE = 1
    OPTION_CHAIN_UPDATE = 2
    SENTIMENT_UPDATE = 3
    CANDLE_UPDATE = 4
    UNKNOWN = 5

# Forward declaration for type hinting
class PatternStateMachine:
    pass

@dataclass
class MarketEvent:
    type: MessageType
    timestamp: int
    symbol: Optional[str] = None
    candle: Optional[VolumeBar] = None
    sentiment: Optional[Sentiment] = None
    option_chain: Optional[List[OptionChainData]] = None
    screener_data: Optional[Dict[str, float]] = None
    triggered_machine: Optional['PatternStateMachine'] = None
