import argparse
import pandas as pd
import sqlite3
from python_engine.core.option_chain_handler import OptionChainHandler
from python_engine.core.sentiment_handler import SentimentHandler
from python_engine.core.pattern_matcher_handler import PatternMatcherHandler
from python_engine.core.execution_handler import ExecutionHandler
from python_engine.models.data_models import MarketEvent, MessageType, VolumeBar, Sentiment, OptionChainData
from python_engine.engine_config import Config
from python_engine.core.order_orchestrator import OrderOrchestrator
from python_engine.core.trade_logger import TradeLog
from data_sourcing.data_manager import DataManager
from data_sourcing.ingestion import IngestionManager
from python_engine.utils.atr_calculator import calculate_atr

def run_backtest(symbol: str, from_date: str = None, to_date: str = None, auto_backfill: bool = True):
    # Load configuration
    Config.load('config.json')
    access_token = Config.get('upstox_access_token')
   
    # Initialize handlers
    data_manager = DataManager(access_token=access_token)
    trade_log = TradeLog(f'backtest_{symbol.replace("|", "_")}.csv')
    order_orchestrator = OrderOrchestrator(trade_log, data_manager, "backtest")
    option_chain_handler = OptionChainHandler()
    sentiment_handler = SentimentHandler()
    pattern_matcher_handler = PatternMatcherHandler(Config.get('strategies_dir'))
    execution_handler = ExecutionHandler(order_orchestrator)

    # Fetch and prepare all data before the loop
    candles_df = data_manager.get_historical_candles(symbol, n_bars=1000, from_date=from_date, to_date=to_date)
    
    if (candles_df is None or candles_df.empty) and auto_backfill:
        print(f"[*] Data missing for {symbol}. Triggering automatic ingestion...")
        ingest_mgr = IngestionManager(access_token=access_token)
        # Default to reasonable dates if None
        f_date = from_date or (pd.Timestamp.now() - pd.Timedelta(days=5)).strftime('%Y-%m-%d')
        t_date = to_date or pd.Timestamp.now().strftime('%Y-%m-%d')
        ingest_mgr.ingest_historical_data(symbol, f_date, t_date, full_options=True)

        # Retry fetch
        candles_df = data_manager.get_historical_candles(symbol, n_bars=1000, from_date=from_date, to_date=to_date)

    if candles_df is None or candles_df.empty:
        print("Could not fetch historical data. Aborting.")
        return

    print(candles_df.head())
    candles_df['timestamp'] = pd.to_datetime(candles_df['timestamp'])

    candles_df.set_index('timestamp', inplace=True)
    candles_df.sort_index(inplace=True)

    candles_df['atr'] = calculate_atr(candles_df)

    market_breadth = data_manager.get_market_breadth() # This is less time-sensitive

    # The processing pipeline
    last_processed_date = None
    option_chain = None
    pcr = 1.0

    for timestamp, row in candles_df.iterrows():
        current_date_str = timestamp.strftime('%Y-%m-%d')

        if current_date_str != last_processed_date:
            # Fetch data specific to the current candle's date
            option_chain = data_manager.get_option_chain(symbol, date=current_date_str)
            pcr = data_manager.get_pcr(symbol, date=current_date_str)

            # Auto-backfill missing daily data
            if (not option_chain or pcr == 1.0) and auto_backfill:
                 print(f"[*] Options/PCR data missing for {current_date_str}. Triggering targeted ingestion...")
                 ingest_mgr = IngestionManager(access_token=access_token)
                 ingest_mgr.ingest_historical_data(symbol, current_date_str, current_date_str, full_options=True)
                 # Retry
                 option_chain = data_manager.get_option_chain(symbol, date=current_date_str)
                 pcr = data_manager.get_pcr(symbol, date=current_date_str)

            last_processed_date = current_date_str

        # Create a MarketEvent from the row
        event = MarketEvent(
            type=MessageType.MARKET_UPDATE,
            timestamp=timestamp.timestamp(),
            symbol=symbol,
            candle=VolumeBar(
                symbol=symbol,
                timestamp=timestamp.timestamp(),
                open=row['open'],
                high=row['high'],
                low=row['low'],
                close=row['close'],
                volume=row['volume'],
                atr=row['atr']
            ),
            option_chain=option_chain,
            sentiment=data_manager.get_current_sentiment(symbol, timestamp=timestamp, mode="backtest")
        )


        # Pass the event through the handlers
        option_chain_handler.on_event(event)
        sentiment_handler.on_event(event)
        pattern_matcher_handler.on_event(event)
        execution_handler.on_event(event)

        # Optimization: Trailing SL and Time-based exit
        _check_exits(trade_log, timestamp, row['close'])

    trade_log.write_log_file()

def _check_exits(trade_log, current_time, current_price):
    # Process open trades for Trailing SL and Time-based exits
    conn = sqlite3.connect(Config.get('db_path', 'sos_master_data.db'))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM trades WHERE status = 'OPEN'")
    open_trades = [dict(row) for row in cursor.fetchall()]

    for trade in open_trades:
        trade_id = trade['trade_id']
        entry_price = trade['entry_price']
        entry_time = pd.to_datetime(trade['entry_time'])
        side = trade['side']
        sl_price = trade.get('sl_price')
        tp_price = trade.get('tp_price')

        if tp_price is None or entry_price is None:
            continue

        # 1. Trailing SL (Move to Break-even at 50% TP)
        target_diff = abs(tp_price - entry_price)
        current_pnl = (current_price - entry_price) if side == 'BUY' else (entry_price - current_price)

        if current_pnl >= target_diff * 0.5:
            if (side == 'BUY' and sl_price < entry_price) or (side == 'SELL' and sl_price > entry_price):
                print(f"[Optimization] Moving SL to Break-even for trade {trade_id}")
                cursor.execute("UPDATE trades SET sl_price = ? WHERE trade_id = ?", (entry_price, trade_id))

        # 2. Time-based Exit (30 min limit)
        if (current_time - entry_time).total_seconds() > 1800:
            print(f"[Optimization] Time-based exit for trade {trade_id}")
            pnl = (current_price - entry_price) if side == 'BUY' else (entry_price - current_price)
            outcome = 'PROFIT' if pnl > 0 else 'LOSS'
            cursor.execute("""
                UPDATE trades
                SET status = 'CLOSED', exit_price = ?, exit_time = ?, exit_reason = 'TIME_EXIT', outcome = ?, pnl = ?
                WHERE trade_id = ?
            """, (current_price, current_time.strftime('%Y-%m-%d %H:%M:%S'), outcome, pnl, trade_id))

    conn.commit()
    conn.close()
