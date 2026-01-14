import argparse
import asyncio
from python_engine.main import run_backtest
from python_engine.live_main import run_live

def main():
    parser = argparse.ArgumentParser(description="Python Trading Engine")
    parser.add_argument('--mode', type=str, choices=['backtest', 'live'], required=True, help='The mode to run the engine in.')
    parser.add_argument('--symbol', type=str, help='The symbol to run the backtest for (required for backtest mode).')

    args = parser.parse_args()

    if args.mode == 'backtest':
        if not args.symbol:
            parser.error("--symbol is required for backtest mode.")
        run_backtest(args.symbol)
    elif args.mode == 'live':
        asyncio.run(run_live())

if __name__ == "__main__":
    main()
