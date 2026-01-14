import json
import os
from typing import Dict, Optional
from python_engine.models.data_models import MarketEvent, MessageType, PatternDefinition
from python_engine.core.pattern_state_machine import PatternStateMachine
from python_engine.core.price_registry import PriceRegistry
from python_engine.utils.dataclass_factory import from_dict

class PatternMatcherHandler:
    def __init__(self, strategies_dir: str):
        self._pattern_definitions = self._load_patterns(strategies_dir)
        self._active_state_machines: Dict[str, PatternStateMachine] = {}

    def _load_patterns(self, strategies_dir: str) -> Dict[str, PatternDefinition]:
        definitions = {}
        for filename in os.listdir(strategies_dir):
            if filename.endswith(".json"):
                with open(os.path.join(strategies_dir, filename)) as f:
                    data = json.load(f)
                    definitions[data["pattern_id"]] = from_dict(PatternDefinition, data)
        return definitions

    def on_event(self, event: MarketEvent):
        event.triggered_machine = None
        if event.type in (MessageType.MARKET_UPDATE, MessageType.CANDLE_UPDATE):
            candle = event.candle
            if candle:
                PriceRegistry.update_price(candle.symbol, candle.close)
                for definition in self._pattern_definitions.values():
                    machine_key = f"{candle.symbol}:{definition.pattern_id}"
                    state_machine = self._active_state_machines.setdefault(
                        machine_key, PatternStateMachine(definition, candle.symbol)
                    )
                    state_machine.evaluate(candle, event.sentiment, event.screener_data)
                    if state_machine.is_triggered():
                        event.triggered_machine = state_machine
                        state_machine.consume_trigger()
                        break
