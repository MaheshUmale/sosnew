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

    # 2. Iterate through each day to fetch option chain and option candle data
    symbol_prefix = "NIFTY" if "NIFTY" in symbol.upper() else "BANKNIFTY"
    for single_date in date_range:
        day_str = single_date.strftime('%Y-%m-%d')
        print(f"\nProcessing data for {day_str}...")

        # a. Fetch and cache the option chain for the day.
        print(f"Fetching option chain for {symbol_prefix} for {day_str}...")
        option_chain = data_manager.get_option_chain(symbol_prefix, date=day_str)

        if not option_chain:
            print(f"Could not fetch option chain for {symbol_prefix} on {day_str}. It might be a holiday or weekend.")
            continue

        # b. Get the option chain from the DB to ensure we have the keys
        db_option_chain_df = data_manager.db_manager.get_option_chain(symbol_prefix, day_str)
        if db_option_chain_df is None or db_option_chain_df.empty:
            print(f"No option chain data found in DB for {symbol_prefix} on {day_str} after fetching.")
            continue

        # c. Extract unique instrument keys and cache their candle data
        call_keys = db_option_chain_df['call_instrument_key'].dropna().unique()
        put_keys = db_option_chain_df['put_instrument_key'].dropna().unique()
        all_option_keys = list(call_keys) + list(put_keys)

        print(f"Found {len(all_option_keys)} unique option instruments for {day_str}. Caching candle data...")
        for i, key in enumerate(all_option_keys):
            print(f"  ({i+1}/{len(all_option_keys)}) Caching candles for {key}...")
            # Fetch data for the specific day
            data_manager.get_historical_candles(
                symbol=key,
                from_date=day_str,
                to_date=day_str,
                n_bars=1000 # More than enough for a single day
            )

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
