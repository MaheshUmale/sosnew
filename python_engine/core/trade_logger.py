import csv
from python_engine.models.trade import Trade, TradeOutcome, TradeSide
import os
from datetime import datetime
class TradeLog:
    def __init__(self, log_file: str):
        self.log_file = log_file
        self._trades = {}

    def log_trade(self, trade: Trade):
        self._trades[trade.trade_id] = trade

    def update_trade(self, trade: Trade):
        if trade.trade_id in self._trades:
            self._trades[trade.trade_id] = trade
        else:
            self.log_trade(trade)

    def get_trade(self, trade_id: str) -> Trade:
        return self._trades.get(trade_id)

    def write_log_file(self):
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
                    trade.trade_id, trade.pattern_id, trade.symbol, trade.side.value, entry_time_str,
                    trade.entry_price, exit_time_str, trade.exit_price,
                    trade.stop_loss, trade.take_profit, trade.outcome.value, pnl
                ])
