import argparse
from data_sourcing.data_manager import DataManager
from SymbolMaster import MASTER as SymbolMaster
from engine_config import Config

def prepare_data(symbol, n_bars=2000):
    """
    Ensures that historical data for the given symbol is cached in the local database.
    It uses DataManager, which handles fetching from remote sources and storing
    in the database if the data is not already present.
    """
    print(f"Checking and preparing data for {symbol} using DataManager...")

    # Load configuration to get API keys if needed by DataManager
    Config.load('config.json')
    access_token = Config.get('upstox_access_token')

    # Initialize DataManager
    data_manager = DataManager(access_token=access_token)

    # This call will fetch from the DB if available, or fetch from the remote
    # source and store it in the DB if not.
    data = data_manager.get_historical_candles(symbol, n_bars=n_bars)

    if data is not None and not data.empty:
        print(f"Data for {symbol} is available in the local database.")
    else:
        print(f"Could not fetch data for {symbol} using DataManager.")


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
        "--n_bars",
        type=int,
        default=2000,
        help="Number of bars to ensure are cached."
    )
    args = parser.parse_args()

    SymbolMaster.initialize()
    prepare_data(args.symbol, args.n_bars)
