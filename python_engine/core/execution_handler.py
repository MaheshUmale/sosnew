from python_engine.models.data_models import MarketEvent

import pandas as pd
from python_engine.models.trade import TradeOutcome

class ExecutionHandler:
    def __init__(self, order_orchestrator, data_manager):
        self._order_orchestrator = order_orchestrator
        self._data_manager = data_manager

    def on_event(self, event: MarketEvent):
        # 1. Update existing positions (Trailing SL, Time-based Exits)
        self._check_active_exits(event)

        # 2. Process new signals
        self._order_orchestrator.on_event(event)

        triggered_machine = event.triggered_machine
        if triggered_machine:
            triggered_state = triggered_machine.state
            definition = triggered_machine.definition
            self._order_orchestrator.execute_trade(
                triggered_state,
                definition,
                event.candle,
                triggered_machine.history,
                triggered_machine.prev_candle
            )
            initial_phase_id = definition.phases[0].id
            triggered_state.reset(initial_phase_id)

    def _check_active_exits(self, event: MarketEvent):
        """
        In-memory check for Trailing SL and Time-based exits.
        Evaluated on every bar for active positions.
        """
        current_time = pd.to_datetime(event.timestamp, unit='s')

        # Iterating over a copy to allow deletion during loop
        for pos_key, position in list(self._order_orchestrator._open_positions.items()):
            # Only process if we have the actual option candle for accurate exit
            opt_candle = self._data_manager.get_historical_candle_for_timestamp(
                symbol=position.instrument_key,
                timestamp=event.timestamp
            )

            if not opt_candle:
                continue

            current_opt_price = opt_candle.close
            entry_price = position.entry_price
            entry_time = pd.to_datetime(position.entry_time, unit='s')

            # 1. Trailing SL (Move to Break-even at 50% of TP target)
            target_diff = abs(position.take_profit - entry_price)
            current_profit = current_opt_price - entry_price

            if current_profit >= (target_diff * 0.5):
                # If SL is still below entry, move it up
                if position.stop_loss < entry_price:
                    print(f"[ExecutionHandler] Moving SL to Break-even ({entry_price}) for {position.symbol}")
                    position.stop_loss = entry_price
                    # Sync with DB
                    trade = self._order_orchestrator._trade_log.get_trade(position.trade_id)
                    if trade:
                        trade.stop_loss = entry_price
                        trade.sl_price = entry_price
                        self._order_orchestrator._trade_log.update_trade(trade)

            # 2. Time-based Exit (30 min limit)
            if (current_time - entry_time).total_seconds() > 1800:
                print(f"[ExecutionHandler] Time-based exit triggered for {position.symbol}")
                self._order_orchestrator._close_position(
                    position,
                    current_opt_price,
                    event.timestamp,
                    TradeOutcome.WIN if current_profit > 0 else TradeOutcome.LOSS
                )
                # Note: _close_position handles deletion from _open_positions
