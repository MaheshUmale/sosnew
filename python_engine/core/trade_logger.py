import csv
from python_engine.models.trade import Trade, TradeOutcome, TradeSide
import os
from datetime import datetime
from data_sourcing.database_manager import DatabaseManager

class TradeLog:
    def __init__(self, log_file: str):
        self.log_file = log_file
        self._trades = {}
        self._db_manager = DatabaseManager()
        self._db_manager.initialize_database()

    def log_trade(self, trade: Trade):
        self._trades[trade.trade_id] = trade
        self._persist_to_db(trade)

    def update_trade(self, trade: Trade):
        self._trades[trade.trade_id] = trade
        self._persist_to_db(trade)

    def _persist_to_db(self, trade: Trade):
        pnl = 0
        if trade.outcome != TradeOutcome.IN_PROGRESS and trade.exit_price is not None:
            # PnL for 1 lot (assuming option multiplier is 1 for now or handled elsewhere)
            pnl = (trade.exit_price - trade.entry_price) * trade.quantity if trade.side == TradeSide.BUY else (trade.entry_price - trade.exit_price) * trade.quantity

        entry_time_str = datetime.fromtimestamp(trade.entry_time).strftime('%Y-%m-%d %H:%M:%S') if trade.entry_time else None
        exit_time_str = datetime.fromtimestamp(trade.exit_time).strftime('%Y-%m-%d %H:%M:%S') if trade.exit_time else None

        trade_data = {
            'trade_id': trade.trade_id,
            'pattern_id': trade.pattern_id,
            'symbol': trade.symbol,
            'instrument_key': trade.instrument_key,
            'side': trade.side.value if hasattr(trade.side, 'value') else str(trade.side),
            'entry_time': entry_time_str,
            'entry_price': trade.entry_price,
            'exit_time': exit_time_str,
            'exit_price': trade.exit_price,
            'stop_loss': trade.stop_loss,
            'take_profit': trade.take_profit,
            'sl_price': trade.sl_price,
            'tp_price': trade.tp_price,
            'quantity': trade.quantity,
            'status': trade.status,
            'exit_reason': trade.exit_reason,
            'outcome': trade.outcome.value if hasattr(trade.outcome, 'value') else str(trade.outcome),
            'pnl': pnl
        }
        try:
            self._db_manager.store_trade(trade_data)
        except Exception as e:
            print(f"[TradeLog] DB Error: {e}")

    def get_trade(self, trade_id: str) -> Trade:
        return self._trades.get(trade_id)

    def write_log_file(self):
        # Keeps existing CSV functionality for redundancy
        with open(self.log_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'trade_id', 'pattern_id', 'symbol', 'side', 'entry_time', 'entry_price',
                'exit_time', 'exit_price', 'stop_loss', 'take_profit', 'outcome', 'pnl'
            ])
            for trade_id in sorted(self._trades.keys()):
                trade = self._trades[trade_id]
                pnl = 0
                if trade.outcome != TradeOutcome.IN_PROGRESS and trade.exit_price is not None:
                    pnl = trade.exit_price - trade.entry_price if trade.side == TradeSide.BUY else trade.entry_price - trade.exit_price

                entry_time_str = datetime.fromtimestamp(trade.entry_time).strftime('%Y-%m-%d %H:%M:%S') if trade.entry_time else ""
                exit_time_str = datetime.fromtimestamp(trade.exit_time).strftime('%Y-%m-%d %H:%M:%S') if trade.exit_time else ""

                writer.writerow([
                    trade.trade_id, trade.pattern_id, trade.symbol, trade.side.value if hasattr(trade.side, 'value') else str(trade.side), entry_time_str,
                    trade.entry_price, exit_time_str, trade.exit_price,
                    trade.stop_loss, trade.take_profit, trade.outcome.value if hasattr(trade.outcome, 'value') else str(trade.outcome), pnl
                ])
