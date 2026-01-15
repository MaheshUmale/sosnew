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
        # This event is for the underlying index. We need to check if we have any open option positions for it.
        positions_to_check = [p for p in self._open_positions.values() if p.underlying_symbol == event.symbol]

        for position in positions_to_check:
            # For each open option position, get the option's candle for the current timestamp
            option_candle = self._data_manager.get_historical_candle_for_timestamp(
                symbol=position.instrument_key, # Use instrument_key for lookup
                timestamp=event.candle.timestamp
            )

            if not option_candle:
                # Can't get price data for the option at this time, so we can't check SL/TP.
                # Let's print a warning and continue.
                # print(f"Warning: Could not fetch option candle for {position.symbol} at timestamp {event.candle.timestamp}")
                continue

            trade_closed = False
            if position.side == TradeSide.BUY:
                if option_candle.low <= position.stop_loss:
                    self._close_position(position, option_candle.low, option_candle.timestamp, TradeOutcome.LOSS)
                    trade_closed = True
                elif option_candle.high >= position.take_profit:
                    self._close_position(position, option_candle.high, option_candle.timestamp, TradeOutcome.WIN)
                    trade_closed = True
            elif position.side == TradeSide.SELL:
                if option_candle.high >= position.stop_loss:
                    self._close_position(position, option_candle.high, option_candle.timestamp, TradeOutcome.LOSS)
                    trade_closed = True
                elif option_candle.low <= position.take_profit:
                    self._close_position(position, option_candle.low, option_candle.timestamp, TradeOutcome.WIN)
                    trade_closed = True

            if trade_closed:
                del self._open_positions[position.symbol]

    def _get_atm_option_details(self, underlying_symbol, side, candle):
        # Simplify symbol prefix extraction
        symbol_prefix = "BANKNIFTY" if "BANK" in underlying_symbol.upper() else "NIFTY"

        if self._mode == 'live':
            instrument_key, trading_symbol = self._data_manager.get_atm_option_details(symbol_prefix, side.value)
            if instrument_key and trading_symbol:
                option_price = self._data_manager.get_last_traded_price(instrument_key)
                return trading_symbol, option_price, instrument_key
        else:  # backtest mode
            instrument_key, trading_symbol = self._data_manager.get_atm_option_details_for_timestamp(
                underlying_symbol=symbol_prefix,
                side=side.value,
                spot_price=candle.close,
                timestamp=candle.timestamp
            )
            if trading_symbol and instrument_key:
                option_candle = self._data_manager.get_historical_candle_for_timestamp(
                    symbol=instrument_key, # Use instrument_key to be precise
                    timestamp=candle.timestamp
                )
                if option_candle:
                    return trading_symbol, option_candle.close, instrument_key

        return None, None, None


    def execute_trade(self, state: PatternState, definition: PatternDefinition, candle, history, prev_candle):
        # We should not open a new position on an underlying if we already have an option position for it.
        open_underlying_symbols = [p.underlying_symbol for p in self._open_positions.values()]
        if state.symbol in open_underlying_symbols:
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
        underlying_symbol_for_position = state.symbol

        # This logic should apply to both live and backtest modes for index trading
        is_index = "nifty" in state.symbol.lower() or "banknifty" in state.symbol.lower()
        instrument_key_to_trade = symbol_to_trade # Default to the underlying

        if is_index:
            option_symbol, option_price, option_instrument_key = self._get_atm_option_details(state.symbol, original_side, candle)

            if option_symbol and option_price and option_instrument_key:
                # For a SELL signal on the index, we BUY a Put option.
                # For a BUY signal on the index, we BUY a Call option.
                # In both cases, the trade side on the option is BUY.
                side = TradeSide.BUY

                symbol_to_trade = option_symbol
                instrument_key_to_trade = option_instrument_key

                # We need a simple way to estimate the option's SL/TP from the index's SL/TP.
                # Using a fixed delta is a common approximation.
                delta = self._data_manager.get_option_delta(symbol_to_trade)
                price_difference_sl = abs(spot_entry_price - spot_stop_loss)
                price_difference_tp = abs(spot_take_profit - spot_entry_price)

                # For BUY side (on Calls and Puts), SL is below and TP is above.
                stop_loss = option_price - (price_difference_sl * delta)
                take_profit = option_price + (price_difference_tp * delta)

                entry_price = option_price
            else:
                # If we can't get option details, we can't place the trade.
                print(f"Could not get ATM option details for {state.symbol} at timestamp {candle.timestamp}. Skipping trade.")
                return

        if symbol_to_trade in self._open_positions:
            # print(f"Skipping trade for {symbol_to_trade} as a position is already open.")
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
            underlying_symbol=underlying_symbol_for_position,
            instrument_key=instrument_key_to_trade,
            symbol=symbol_to_trade,
            side=side,
            entry_price=entry_price,
            entry_time=candle.timestamp,
            stop_loss=stop_loss,
            take_profit=take_profit,
            trade_id=trade_id
        )
        self._open_positions[symbol_to_trade] = position
        print(f"Opened position for {symbol_to_trade} (underlying: {underlying_symbol_for_position}) at {entry_price}")

    def _close_position(self, position: Position, exit_price: float, exit_time, outcome: TradeOutcome):
        trade = self._trade_log.get_trade(position.trade_id)
        if trade:
            trade.exit_price = exit_price
            trade.exit_time = exit_time
            trade.outcome = outcome
            self._trade_log.update_trade(trade)
            print(f"Closed position for {position.symbol} at {exit_price} with outcome {outcome}")
