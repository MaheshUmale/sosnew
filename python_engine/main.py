import argparse
import pandas as pd
from python_engine.engine_config import Config
from python_engine.core.order_orchestrator import OrderOrchestrator
from python_engine.core.trade_logger import TradeLog
from python_engine.core.trading_engine import TradingEngine
from data_sourcing.data_manager import DataManager
from data_sourcing.ingestion import IngestionManager
from python_engine.data.repository import DataRepository

def run_backtest(symbol: str, from_date: str = None, to_date: str = None, auto_backfill: bool = True):
    # Load configuration
    Config.load('config.json')
    access_token = Config.get('upstox_access_token')
   
    # Initialize Managers & Repository
    data_manager = DataManager(access_token=access_token)
    repository = DataRepository()

    trade_log = TradeLog(f'backtest_{symbol.replace("|", "_")}.csv')
    order_orchestrator = OrderOrchestrator(trade_log, data_manager, "backtest")

    # Initialize the Unified Engine
    engine = TradingEngine(order_orchestrator, data_manager, Config.get('strategies_dir'))

    # Fetch data from Repository
    candles_df = repository.get_historical_candles(symbol, from_date=from_date, to_date=to_date)
    
    if (candles_df is None or candles_df.empty) and auto_backfill:
        print(f"[*] Data missing for {symbol}. Triggering automatic ingestion...")
        ingest_mgr = IngestionManager(access_token=access_token)
        f_date = from_date or (pd.Timestamp.now() - pd.Timedelta(days=5)).strftime('%Y-%m-%d')
        t_date = to_date or pd.Timestamp.now().strftime('%Y-%m-%d')
        ingest_mgr.ingest_historical_data(symbol, f_date, t_date, full_options=True)

        # Retry fetch
        candles_df = repository.get_historical_candles(symbol, from_date=from_date, to_date=to_date)

    if candles_df is None or candles_df.empty:
        print(f"Could not find historical data for {symbol} in DB. Aborting.")
        return

    # Prepare for processing
    candles_df.set_index('timestamp', inplace=True)
    candles_df.sort_index(inplace=True)

    # Run the Engine
    engine.run_backtest(symbol, candles_df)

    # Finalize
    trade_log.write_log_file()
    print(f"Backtest complete. Log saved to: {trade_log.log_file}")
