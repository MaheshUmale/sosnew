from python_engine.models.data_models import PatternDefinition, PatternState, VolumeBar, Sentiment, Phase
from python_engine.utils.mvel_functions import MVEL_FUNCTIONS
from python_engine.utils.dot_dict import DotDict
from typing import Dict, Optional, List
import logging
from asteval import Interpreter

class PatternStateMachine:
    def __init__(self, definition: PatternDefinition, symbol: str, initial_state: Optional[PatternState] = None):
        self._definition = definition
        self._symbol = symbol
        self._state = initial_state if initial_state else PatternState(definition.pattern_id, symbol, definition.phases[0].id)
        self._is_triggered = False
        self._history: List[VolumeBar] = []
        self._prev_candle: Optional[VolumeBar] = None
        self._MAX_HISTORY = 200
        self._asteval = Interpreter(symtable=MVEL_FUNCTIONS)

    def evaluate(self, candle: VolumeBar, sentiment: Sentiment, screener_data: Dict[str, float]):
        self._history.append(candle)
        if len(self._history) > self._MAX_HISTORY:
            self._history.pop(0)

        current_phase = self._get_current_phase()
        if not current_phase:
            return

        self._build_context(candle, sentiment, screener_data)

        if self._check_conditions(current_phase.conditions):
            self._capture_variables(current_phase.capture)
            self._move_to_next_phase()
        else:
            self._state.increment_timeout()
            if self._state.is_timed_out(current_phase.timeout):
                self._state.reset(self._definition.phases[0].id)

        self._prev_candle = candle

    def _check_conditions(self, conditions: List[str]) -> bool:
        if not conditions:
            return True

        for condition in conditions:
            try:
                if not self._asteval.eval(condition):
                    return False
            except Exception as e:
                logging.error(f"Error evaluating condition '{condition}': {e}")
                return False
        return True

    def _capture_variables(self, captures: Dict[str, str]):
        if not captures:
            return

        for name, expression in captures.items():
            try:
                value = self._asteval.eval(expression)
                if isinstance(value, (int, float)):
                    self._state.capture(name, float(value))
            except Exception as e:
                logging.error(f"Error capturing variable '{name}': {e}")

    def _build_context(self, candle: VolumeBar, sentiment: Sentiment, screener_data: Dict[str, float]):
        self._asteval.symtable['candle'] = candle
        self._asteval.symtable['sentiment'] = sentiment
        self._asteval.symtable['vars'] = DotDict(self._state.captured_variables)
        self._asteval.symtable['screener'] = screener_data or {}
        self._asteval.symtable['prev_candle'] = self._prev_candle or candle
        self._asteval.symtable['history'] = self._history
        self._asteval.symtable['volume'] = float(candle.volume)
        self._asteval.symtable['close'] = candle.close
        self._asteval.symtable['high'] = candle.high
        self._asteval.symtable['low'] = candle.low
        self._asteval.symtable['open'] = candle.open

    def _get_current_phase(self) -> Optional[Phase]:
        for phase in self._definition.phases:
            if phase.id == self._state.current_phase_id:
                return phase
        return None

    def _move_to_next_phase(self):
        current_phase_index = self._find_phase_index(self._state.current_phase_id)
        if current_phase_index < len(self._definition.phases) - 1:
            next_phase_id = self._definition.phases[current_phase_index + 1].id
            self._state.move_to(next_phase_id)
        else:
            self._is_triggered = True
            logging.info(f"TRIGGER for {self._definition.pattern_id} on {self._state.symbol}")

    def _find_phase_index(self, phase_id: str) -> int:
        for i, phase in enumerate(self._definition.phases):
            if phase.id == phase_id:
                return i
        return -1

    def is_triggered(self) -> bool:
        return self._is_triggered

    def consume_trigger(self):
        self._is_triggered = False

    @property
    def state(self) -> PatternState:
        return self._state

    @property
    def definition(self) -> PatternDefinition:
        return self._definition

    @property
    def history(self) -> List[VolumeBar]:
        return self._history

    @property
    def prev_candle(self) -> Optional[VolumeBar]:
        return self._prev_candle
