import uuid
from asteval import Interpreter
from python_engine.models.data_models import PatternState, PatternDefinition, MarketEvent
from python_engine.models.trade import Position, Trade, TradeSide, TradeOutcome
from python_engine.core.trade_logger import TradeLog

class OrderOrchestrator:
    def __init__(self, trade_log: TradeLog):
        self._trade_log = trade_log
        self._open_positions = {}
        self._asteval = Interpreter()

    def on_event(self, event: MarketEvent):
        if event.symbol not in self._open_positions:
            return

        position = self._open_positions[event.symbol]
        candle = event.candle
        trade_closed = False

        if position.side == TradeSide.BUY:
            if candle.low <= position.stop_loss:
                self._close_position(position, candle.low, candle.timestamp, TradeOutcome.LOSS)
                trade_closed = True
            elif candle.high >= position.take_profit:
                self._close_position(position, candle.high, candle.timestamp, TradeOutcome.WIN)
                trade_closed = True
        elif position.side == TradeSide.SELL:
            if candle.high >= position.stop_loss:
                self._close_position(position, candle.high, candle.timestamp, TradeOutcome.LOSS)
                trade_closed = True
            elif candle.low <= position.take_profit:
                self._close_position(position, candle.low, candle.timestamp, TradeOutcome.WIN)
                trade_closed = True

        if trade_closed:
            del self._open_positions[event.symbol]

    def execute_trade(self, state: PatternState, definition: PatternDefinition, candle):
        if state.symbol in self._open_positions:
            # Simple logic: don't open a new position if one is already open for this symbol
            return

        # Evaluate expressions
        self._asteval.symtable['candle'] = candle
        self._asteval.symtable['vars'] = state.captured_variables

        entry_price = self._asteval.eval(definition.execution.entry)
        stop_loss = self._asteval.eval(definition.execution.sl)
        take_profit = self._asteval.eval(definition.execution.tp)

        side = TradeSide(definition.execution.side.upper())
        trade_id = str(uuid.uuid4())

        # Create and log the trade entry
        trade = Trade(
            trade_id=trade_id,
            symbol=state.symbol,
            side=side,
            entry_time=candle.timestamp,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit
        )
        self._trade_log.log_trade(trade)

        # Open a new position
        position = Position(
            symbol=state.symbol,
            side=side,
            entry_price=entry_price,
            entry_time=candle.timestamp,
            stop_loss=stop_loss,
            take_profit=take_profit,
            trade_id=trade_id
        )
        self._open_positions[state.symbol] = position
        print(f"Opened position for {state.symbol} at {entry_price}")

    def _close_position(self, position: Position, exit_price: float, exit_time, outcome: TradeOutcome):
        trade = self._trade_log.get_trade(position.trade_id)
        if trade:
            trade.exit_price = exit_price
            trade.exit_time = exit_time
            trade.outcome = outcome
            self._trade_log.update_trade(trade)
            print(f"Closed position for {position.symbol} at {exit_price} with outcome {outcome}")
