import csv
from python_engine.models.trade import Trade, TradeOutcome
import os

class TradeLog:
    def __init__(self, log_file: str):
        self.log_file = log_file
        self._trades = {}
        self._initialize_log_file()

    def _initialize_log_file(self):
        if not os.path.exists(self.log_file):
            with open(self.log_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'trade_id', 'pattern_id', 'symbol', 'side', 'entry_time', 'entry_price',
                    'exit_time', 'exit_price', 'stop_loss', 'take_profit',
                    'outcome', 'pnl'
                ])

    def log_trade(self, trade: Trade):
        self._trades[trade.trade_id] = trade
        self._write_trade(trade)

    def update_trade(self, trade: Trade):
        if trade.trade_id in self._trades:
            self._trades[trade.trade_id] = trade
            # This is not efficient, but for now it's the simplest
            # In a real high-performance system, we'd update the specific line
            self._rewrite_all_trades()
        else:
            self.log_trade(trade)

    def _write_trade(self, trade: Trade):
        pnl = 0
        if trade.outcome != TradeOutcome.IN_PROGRESS:
            if trade.side.value == 'BUY':
                pnl = trade.exit_price - trade.entry_price
            else:
                pnl = trade.entry_price - trade.exit_price

        with open(self.log_file, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                trade.trade_id, trade.pattern_id, trade.symbol, trade.side, trade.entry_time,
                trade.entry_price, trade.exit_time, trade.exit_price,
                trade.stop_loss, trade.take_profit, trade.outcome, pnl
            ])

    def _rewrite_all_trades(self):
        # This is a temporary inefficient implementation for simplicity
        os.remove(self.log_file)
        self._initialize_log_file()
        for trade_id in self._trades:
            self._write_trade(self._trades[trade_id])

    def get_trade(self, trade_id: str) -> Trade:
        return self._trades.get(trade_id)
