import csv
from python_engine.models.trade import Trade, TradeOutcome, TradeSide
import os
from datetime import datetime
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

    def _write_trade(self, trade: Trade, is_new=True):
        pnl = 0
        if trade.outcome != TradeOutcome.IN_PROGRESS and trade.exit_price is not None:
            pnl = trade.exit_price - trade.entry_price if trade.side == TradeSide.BUY else trade.entry_price - trade.exit_price

        # Format timestamps
        entry_time_str = datetime.fromtimestamp(trade.entry_time).strftime('%Y-%m-%d %H:%M:%S') if trade.entry_time else ""
        exit_time_str = datetime.fromtimestamp(trade.exit_time).strftime('%Y-%m-%d %H:%M:%S') if trade.exit_time else ""

        row = [
            trade.trade_id, trade.pattern_id, trade.symbol, trade.side.value, entry_time_str,
            trade.entry_price, exit_time_str, trade.exit_price,
            trade.stop_loss, trade.take_profit, trade.outcome.value, pnl
        ]

        if is_new:
            with open(self.log_file, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(row)
        else:
            # For updates, we read all, find the line, and write back
            self._rewrite_all_trades()
    def _rewrite_all_trades(self):
        """Rewrites the entire log file from the in-memory dictionary of trades."""
        temp_file = self.log_file + '.tmp'
        with open(temp_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'trade_id', 'pattern_id', 'symbol', 'side', 'entry_time', 'entry_price',
                'exit_time', 'exit_price', 'stop_loss', 'take_profit', 'outcome', 'pnl'
            ])
            for trade_id in sorted(self._trades.keys()): # Sort to maintain order
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

        os.replace(temp_file, self.log_file)

    def get_trade(self, trade_id: str) -> Trade:
        return self._trades.get(trade_id)
