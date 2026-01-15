import uuid
from asteval import Interpreter
from data_sourcing.data_manager import DataManager
from python_engine.models.data_models import PatternState, PatternDefinition, MarketEvent
from python_engine.models.trade import Position, Trade, TradeSide, TradeOutcome
from python_engine.core.trade_logger import TradeLog
from python_engine.utils.dot_dict import DotDict
from python_engine.utils.mvel_functions import MVEL_FUNCTIONS


class OrderOrchestrator:
    def __init__(self, trade_log: TradeLog, data_manager: DataManager, mode: str):
        self._trade_log = trade_log
        self._data_manager = data_manager
        self._mode = mode
        self._open_positions = {}
        self._asteval = Interpreter(symtable=MVEL_FUNCTIONS)

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

    def _get_atm_option_details(self, underlying_symbol, side):
        symbol_map = {
            "NSE_INDEX|Nifty 50": "NIFTY",
            "NSE_INDEX|Nifty Bank": "BANKNIFTY"
        }
        symbol_prefix = symbol_map.get(underlying_symbol)

        if not symbol_prefix:
            return None, None

        instrument_key, trading_symbol = self._data_manager.get_atm_option_details(symbol_prefix, side.value)

        if instrument_key and trading_symbol:
            option_price = self._data_manager.get_last_traded_price(instrument_key)
            return trading_symbol, option_price
        return None, None


    def execute_trade(self, state: PatternState, definition: PatternDefinition, candle, history, prev_candle):
        if state.symbol in self._open_positions:
            return

        self._asteval.symtable.update({
            'candle': candle,
            'vars': DotDict(state.captured_variables),
            'history': history,
            'prev_candle': prev_candle or candle,
            'close': candle.close,
            'high': candle.high,
            'low': candle.low,
            'open': candle.open
        })

        spot_entry_price = self._asteval.eval(definition.execution.entry)
        spot_stop_loss = self._asteval.eval(definition.execution.sl)
        self._asteval.symtable.update({'entry': spot_entry_price, 'sl': spot_stop_loss})
        spot_take_profit = self._asteval.eval(definition.execution.tp)

        side = TradeSide(definition.execution.side.upper())
        original_side = side
        symbol_to_trade = state.symbol
        entry_price = spot_entry_price
        stop_loss = spot_stop_loss
        take_profit = spot_take_profit

        if self._mode == "live" and ("NIFTY" in state.symbol.upper() or "BANKNIFTY" in state.symbol.upper()):
            option_symbol, option_price = self._get_atm_option_details(state.symbol, original_side)
            if option_symbol and option_price:
                if original_side == TradeSide.SELL:
                    side = TradeSide.BUY # We are buying a PE option
                symbol_to_trade = option_symbol
                delta = self._data_manager.get_option_delta(symbol_to_trade)
                price_difference_sl = abs(spot_entry_price - spot_stop_loss) * delta
                price_difference_tp = abs(spot_take_profit - spot_entry_price) * delta

                stop_loss = option_price - price_difference_sl
                take_profit = option_price + price_difference_tp

                entry_price = option_price

        if symbol_to_trade in self._open_positions:
            return

        trade_id = str(uuid.uuid4())
        trade = Trade(
            trade_id=trade_id,
            pattern_id=definition.pattern_id,
            symbol=symbol_to_trade,
            side=side,
            entry_time=candle.timestamp,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit
        )
        self._trade_log.log_trade(trade)

        position = Position(
            symbol=symbol_to_trade,
            side=side,
            entry_price=entry_price,
            entry_time=candle.timestamp,
            stop_loss=stop_loss,
            take_profit=take_profit,
            trade_id=trade_id
        )
        self._open_positions[symbol_to_trade] = position
        print(f"Opened position for {symbol_to_trade} at {entry_price}")

    def _close_position(self, position: Position, exit_price: float, exit_time, outcome: TradeOutcome):
        trade = self._trade_log.get_trade(position.trade_id)
        if trade:
            trade.exit_price = exit_price
            trade.exit_time = exit_time
            trade.outcome = outcome
            self._trade_log.update_trade(trade)
            print(f"Closed position for {position.symbol} at {exit_price} with outcome {outcome}")
