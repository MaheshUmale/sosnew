import argparse
import asyncio
from python_engine.main import run_backtest
from python_engine.live_main import run_live
from SymbolMaster import MASTER as SymbolMaster

def main():
    parser = argparse.ArgumentParser(description="Python Trading Engine")
    parser.add_argument('--mode', type=str, choices=['backtest', 'live'], required=True, help='The mode to run the engine in.')
    parser.add_argument('--symbol', type=str, help='The symbol to run the backtest for (required for backtest mode).')
    parser.add_argument('--from-date', type=str, help='The start date for the backtest (YYYY-MM-DD).')
    parser.add_argument('--to-date', type=str, help='The end date for the backtest (YYYY-MM-DD).')


    args = parser.parse_args()

    SymbolMaster.initialize()

    if args.mode == 'backtest':
        symbol = "NSE_INDEX|Nifty 50" if args.symbol == "NIFTY" else args.symbol
        if not symbol:
            parser.error("--symbol is required for backtest mode.")
        run_backtest(symbol, args.from_date, args.to_date)
    elif args.mode == 'live':
        asyncio.run(run_live())

if __name__ == "__main__":
    main()
