import argparse
import sqlite3
from datetime import datetime
from data_sourcing.data_manager import DataManager
import pandas as pd

class BacktestDataPreparer:
    def __init__(self, date_str):
        self.date_str = date_str
        self.date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        self.data_manager = DataManager()
        self.db_path = "backtest_data.db"
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS backtest_candles (
                            symbol TEXT, date TEXT, timestamp TEXT, open REAL, high REAL,
                            low REAL, close REAL, volume INTEGER, source TEXT,
                            PRIMARY KEY (symbol, date, timestamp))''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS backtest_option_chain (
                            symbol TEXT, date TEXT, timestamp TEXT, strike REAL,
                            call_oi_chg INTEGER, put_oi_chg INTEGER,
                            PRIMARY KEY (symbol, date, timestamp, strike))''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS backtest_sentiment (
                            symbol TEXT, date TEXT, timestamp TEXT, pcr REAL, regime TEXT,
                            PRIMARY KEY (symbol, date, timestamp))''')
        conn.commit()
        conn.close()

    def run(self, symbols):
        print(f"Preparing backtest data for {self.date_str}...")
        for symbol in symbols:
            print(f"Fetching candle data for {symbol}...")
            candles = self.data_manager.get_historical_candles(symbol, n_bars=1000)
            if candles is not None:
                candles = candles.reset_index()
                candles_for_date = candles[candles['datetime'].dt.date == self.date_obj.date()]
                self._store_candles(symbol, candles_for_date)

                if "NIFTY" in symbol.upper():
                    print(f"Fetching option chain and sentiment data for {symbol}...")
                    for _, candle in candles_for_date.iterrows():
                        timestamp = candle['datetime']
                        option_chain = self.data_manager.get_option_chain(symbol)
                        if option_chain:
                            self._store_option_chain(symbol, option_chain, timestamp)

                        pcr = self.data_manager.get_pcr(symbol)
                        market_breadth = self.data_manager.get_market_breadth()
                        regime = self._calculate_sentiment_regime(pcr, market_breadth)
                        self._store_sentiment(symbol, pcr, regime, timestamp)

        print("Backtest data preparation complete.")

    def _calculate_sentiment_regime(self, pcr, market_breadth):
        if market_breadth and 'advance' in market_breadth:
            adv = market_breadth['advance'].get('count', {}).get('Advances', 0)
            dec = market_breadth['advance'].get('count', {}).get('Declines', 1)
            ratio = adv / dec if dec > 0 else adv

            if pcr < 0.8 and ratio > 1.5: return "COMPLETE_BULLISH"
            if pcr < 0.9 and ratio > 1.2: return "BULLISH"
            if pcr < 1.0 and ratio > 1.0: return "SIDEWAYS_BULLISH"
            if pcr > 1.2 and ratio < 0.7: return "COMPLETE_BEARISH"
            if pcr > 1.1 and ratio < 0.9: return "BEARISH"
            if pcr > 1.0 and ratio < 1.0: return "SIDEWAYS_BEARISH"
        return "SIDEWAYS"

    def _store_sentiment(self, symbol, pcr, regime, timestamp):
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("INSERT OR REPLACE INTO backtest_sentiment VALUES (?, ?, ?, ?, ?)",
                         (symbol, self.date_str, timestamp.strftime('%H:%M'), pcr, regime))
        except Exception as e:
            print(f"Error storing sentiment for {symbol}: {e}")
        conn.commit()
        conn.close()

    def _store_candles(self, symbol, candles_df):
        conn = sqlite3.connect(self.db_path)
        for _, row in candles_df.iterrows():
            try:
                timestamp_col = 'datetime' if 'datetime' in row else 'timestamp'
                conn.execute("INSERT OR REPLACE INTO backtest_candles VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                             (symbol, self.date_str, row[timestamp_col].strftime('%H:%M'),
                              row['open'], row['high'], row['low'], row['close'], row['volume'], 'backtest'))
            except Exception as e:
                print(f"Error storing candle for {symbol}: {e}")
        conn.commit()
        conn.close()

    def _store_option_chain(self, symbol, option_chain, timestamp):
        conn = sqlite3.connect(self.db_path)
        for item in option_chain:
            try:
                conn.execute("INSERT OR REPLACE INTO backtest_option_chain VALUES (?, ?, ?, ?, ?, ?)",
                             (symbol, self.date_str, timestamp.strftime('%H:%M'), item['strike'],
                              item['call_oi_chg'], item['put_oi_chg']))
            except Exception as e:
                print(f"Error storing option chain for {symbol}: {e}")
        conn.commit()
        conn.close()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Prepare backtest data for a specific date.")
    parser.add_argument('date', type=str, help='The date to prepare data for (YYYY-MM-DD).')
    args = parser.parse_args()

    symbols_to_prepare = ['NIFTY', 'BANKNIFTY', 'RELIANCE', 'SBIN']
    preparer = BacktestDataPreparer(args.date)
    preparer.run(symbols_to_prepare)
