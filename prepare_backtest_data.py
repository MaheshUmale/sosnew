import argparse
from datetime import datetime, timedelta
import pandas as pd
from data_sourcing.data_manager import DataManager
from SymbolMaster import MASTER as SymbolMaster
from engine_config import Config

def prepare_data(symbol, from_date, to_date):
    """
    Ensures that historical data for the given symbol and its associated options
    are cached in the local database for a specified date range.
    """
    print(f"Preparing data for {symbol} from {from_date} to {to_date}...")

    Config.load('config.json')
    access_token = Config.get('upstox_access_token')
    data_manager = DataManager(access_token=access_token)

    # Get the date range
    start_date = datetime.strptime(from_date, '%Y-%m-%d').date()
    end_date = datetime.strptime(to_date, '%Y-%m-%d').date()
    date_range = pd.date_range(start=start_date, end=end_date, freq='B') # Business days

    # 1. Cache the underlying index data for the entire period
    print(f"\nCaching underlying symbol data for {symbol}...")
    data_manager.get_historical_candles(symbol, from_date=from_date, to_date=to_date, n_bars=100000)

    # 2. Cache option chain data for each business day
    holidays = data_manager.holidays
    print(f"\nCaching option chain data for {symbol}...")
    for target_date in date_range:
        date_str = target_date.strftime('%Y-%m-%d')
        if date_str in holidays:
            print(f"  Skipping holiday: {date_str}")
            continue
        
        print(f"  Syncing option chain for {date_str}...")
        try:
            data_manager.get_option_chain(symbol, date=date_str)
        except Exception as e:
            print(f"  [ERROR] Failed to sync option chain for {date_str}: {e}")

    print("\nData preparation complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Prepare backtest data by caching it into the local database."
    )
    parser.add_argument(
        "--symbol",
        type=str,
        required=True,
        help="Symbol to fetch data for (e.g., 'NSE_INDEX|Nifty 50')"
    )
    parser.add_argument(
        "--from_date",
        type=str,
        required=True,
        help="Start date in YYYY-MM-DD format."
    )
    parser.add_argument(
        "--to_date",
        type=str,
        required=True,
        help="End date in YYYY-MM-DD format."
    )
    args = parser.parse_args()

    SymbolMaster.initialize()
    prepare_data(args.symbol, args.from_date, args.to_date)
