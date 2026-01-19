import asyncio
import json
import threading
import time
from datetime import datetime
import pandas as pd

import upstox_client
from upstox_client.feeder.market_data_streamer_v3 import MarketDataStreamerV3

from python_engine.core.option_chain_handler import OptionChainHandler
from python_engine.core.sentiment_handler import SentimentHandler
from python_engine.core.pattern_matcher_handler import PatternMatcherHandler
from python_engine.core.execution_handler import ExecutionHandler
from python_engine.models.data_models import MarketEvent, MessageType, VolumeBar
from python_engine.engine_config import Config
from python_engine.core.order_orchestrator import OrderOrchestrator
from python_engine.core.trade_logger import TradeLog
from data_sourcing.data_manager import DataManager
from python_engine.utils.symbol_master import MASTER as SymbolMaster

# --- Global State for Streamer ---
streamer = None

class LiveTradingEngine:
    def __init__(self, loop):
        self.loop = loop
        self.data_manager = DataManager()
        self.trade_log = TradeLog('live_trades.csv')
        self.order_orchestrator = OrderOrchestrator(self.trade_log, self.data_manager, "live")
        self.option_chain_handler = OptionChainHandler()
        self.sentiment_handler = SentimentHandler()
        self.pattern_matcher_handler = PatternMatcherHandler(Config.get('strategies_dir'))
        self.execution_handler = ExecutionHandler(self.order_orchestrator, self.data_manager)

        self.access_token = Config.get('upstox_access_token')
        self.symbols = {
            'NSE_INDEX|Nifty 50',
            'NSE_INDEX|Nifty Bank',
        }
        self.subscribed_instruments = set()
        self._candle_cache = {}  # {symbol: list of VolumeBar-like dicts}
        self._atr_period = 14

        self._fno_loaded = False
        self._load_instruments()

    def _calculate_atr(self, symbol, current_candle):
        """
        Calculate ATR for a symbol using the last N candles in the cache.
        """
        if symbol not in self._candle_cache:
            self._candle_cache[symbol] = []
        
        # Append the current candle to the cache
        self._candle_cache[symbol].append({
            'high': current_candle['high'],
            'low': current_candle['low'],
            'close': current_candle['close']
        })
        
        # Keep only the last atr_period + 1 candles (need previous close for TR)
        if len(self._candle_cache[symbol]) > self._atr_period + 1:
            self._candle_cache[symbol] = self._candle_cache[symbol][-(self._atr_period + 1):]
        
        candles = self._candle_cache[symbol]
        if len(candles) < 2:
            return 0.0  # Not enough data

        true_ranges = []
        for i in range(1, len(candles)):
            high = candles[i]['high']
            low = candles[i]['low']
            prev_close = candles[i - 1]['close']
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            true_ranges.append(tr)

        if not true_ranges:
            return 0.0
        
        return sum(true_ranges) / len(true_ranges)

    async def _pre_load_history(self):
        """Pre-loads recent historical data to prime the strategy indicators."""
        print("[LiveTradingEngine] Pre-loading historical data for indicators...")
        for symbol in self.symbols:
            try:
                # Fetch last 100 candles for indices
                df = self.data_manager.get_historical_candles(symbol, n_bars=100)
                if df is not None and not df.empty:
                    # Ensure timestamp is datetime
                    df['timestamp'] = pd.to_datetime(df['timestamp'])
                    # Candles are usually DESC in DB/API, we need ASC for heartbeats
                    df = df.sort_values(by='timestamp', ascending=True)
                    print(f"  Loaded {len(df)} candles for {symbol} to prime engine.")
                    for _, row in df.iterrows():
                        # Prime the ATR cache with historical data
                        candle_for_atr = {
                            'high': row['high'],
                            'low': row['low'],
                            'close': row['close']
                        }
                        self._calculate_atr(symbol, candle_for_atr)
                        
                        event = MarketEvent(
                            type=MessageType.CANDLE_UPDATE,
                            timestamp=row['timestamp'].timestamp(),
                            symbol=symbol,
                            candle=VolumeBar(
                                symbol=symbol,
                                timestamp=row['timestamp'].timestamp(),
                                open=row['open'],
                                high=row['high'],
                                low=row['low'],
                                close=row['close'],
                                volume=row['volume']
                            ),
                            sentiment=None
                        )
                        # Only prime the matcher, don't execute trades during priming
                        self.pattern_matcher_handler.on_event(event)
                    print(f"  ATR cache primed for {symbol}: {len(self._candle_cache.get(symbol, []))} candles cached.")
            except Exception as e:
                print(f"  [ERROR] Failed to pre-load history for {symbol}: {e}")


    def _load_instruments(self):
        """Initial instrument loading. Indices are always loaded. Options are +-5 strikes."""
        # 1. Subscribe to Indices
        instrument_keys_to_subscribe = []
        for s in self.symbols:
            key = SymbolMaster.get_upstox_key(s)
            if key:
                instrument_keys_to_subscribe.append(key)
        self.subscribed_instruments.update(instrument_keys_to_subscribe)

        # 2. Subscribe to Options (+-5 strikes)
        try:
            print("[LiveTradingEngine] Loading FNO master to resolve ATM picks and surrounding strikes...")
            # load_and_cache_fno_instruments fetches LTP and calls get_upstox_instruments which now uses +-5 strikes
            self.data_manager.load_and_cache_fno_instruments(mode='live')

            for s in ["NIFTY", "BANKNIFTY"]:
                inst_data = self.data_manager.fno_instruments.get(s)
                if inst_data and 'all_keys' in inst_data:
                    # Filter out futures if we only want options, but user said "PE+CE + NIFTY, banknifty"
                    # all_keys includes current future. Let's keep it for now as it doesn't hurt.
                    # Actually, let's filter to just CE/PE to be precise if needed,
                    # but instrument_loader now provides 11 strikes * 2 = 22 symbols per index.
                    option_keys = [k for k in inst_data['all_keys'] if any(x in k for x in ['CE', 'PE', 'OPT'])]
                    # Wait, Upstox keys might not have CE/PE in the key itself (it's often a number or different format)
                    # Let's use all_keys but we know it has 23 keys (1 fut + 22 options)
                    self.subscribed_instruments.update(inst_data['all_keys'])
                    print(f"  [Live] Subscribed to {len(inst_data['all_keys'])} instruments for {s} (Strikes +-5)")

            self._fno_loaded = True
        except Exception as e:
            print(f"[LiveTradingEngine] Failed to load FNO instruments: {e}")

    def on_message(self, message):
        """Thread-safe callback to schedule message processing on the main event loop."""
        self.loop.call_soon_threadsafe(asyncio.create_task, self.process_message(message))

    async def process_message(self, data):
        """Asynchronously processes the market data."""
        global streamer

        if not data:
            return
            
        if not isinstance(data, dict):
             # print(f"[DEBUG] Received non-dict data: {type(data)}")
             return

        # Periodically fetch option chain data to populate the DB
        now = datetime.now()
        if not hasattr(self, '_last_chain_fetch') or (now - self._last_chain_fetch).total_seconds() > 300: # Every 5 mins
            for symbol in ["NIFTY", "BANKNIFTY"]:
                try:
                    # Pass mode='live' to avoid backtest error logs
                    self.data_manager.get_option_chain(symbol, mode='live')
                    self._last_chain_fetch = now
                except Exception as e:
                    pass

        feeds = data.get('feeds', {})
        if not feeds:
            return

        for symbol_key, feed in feeds.items():
            # Unified OHLC extraction from Upstox SDK v3 feeds
            ohlc_data = []
            if 'fullFeed' in feed:
                ff = feed['fullFeed']
                if 'indexFF' in ff and 'marketOHLC' in ff['indexFF']:
                    ohlc_data = ff['indexFF']['marketOHLC'].get('ohlc', [])
                elif 'marketFF' in ff and 'marketOHLC' in ff['marketFF']:
                    ohlc_data = ff['marketFF']['marketOHLC'].get('ohlc', [])
            elif 'ff' in feed: # Legacy/Alternate key
                ff = feed['ff']
                if 'marketFF' in ff and 'marketOHLC' in ff['marketFF']:
                    ohlc_data = ff['marketFF']['marketOHLC'].get('ohlc', [])

            if not ohlc_data:
                continue

            one_min_candle = None
            for ohlc_item in ohlc_data:
                if ohlc_item.get('interval') == 'I1':
                    one_min_candle = ohlc_item
                    break

            if one_min_candle:
                ticker = SymbolMaster.get_ticker_from_key(symbol_key)
                
                # Normalize ticker for ATR cache consistency with primed symbols
                # Primed symbols: 'NSE_INDEX|Nifty 50', 'NSE_INDEX|Nifty Bank'
                # Live tickers might be: 'NSE|INDEX|NIFTY', 'NSE|INDEX|BANKNIFTY'
                # Normalize to primed format for ATR cache keying
                if ticker in ["NSE|INDEX|NIFTY", "NSE|INDEX|BANKNIFTY", "NIFTY", "BANKNIFTY"]:
                    if "BANK" in ticker.upper():
                        atr_cache_key = "NSE_INDEX|Nifty Bank"
                    else:
                        atr_cache_key = "NSE_INDEX|Nifty 50"
                else:
                    atr_cache_key = ticker
                
                print(f".", end="", flush=True)
 
                
                # Detect if a minute has passed to fetch the finalized candle from API
                candle_ts = int(one_min_candle['ts'])
                if not hasattr(self, '_last_processed_min'):
                    self._last_processed_min = {}
                
                if ticker not in self._last_processed_min:
                    self._last_processed_min[ticker] = candle_ts
                    continue 

                if candle_ts > self._last_processed_min[ticker]:
                    self._last_processed_min[ticker] = candle_ts
                    print(f"\n[LiveTradingEngine] Minute changed for {ticker}. Fetching finalized candle...")
                    
                    # Fetch the most recent 1-min candles from Intraday API
                    # The API returns the last closed 1-min candle as the first item (or last depending on sort)
                    # We fetch 2 bars to be safe
                    intra_resp = self.data_manager.upstox_client.get_intra_day_candle_data(symbol_key, '1m')
                    if intra_resp and hasattr(intra_resp, 'data') and hasattr(intra_resp.data, 'candles'):
                        # Upstox Intraday API returns candles in reverse chronological order
                        # candles[0] is the current forming candle, candles[1] is the last closed candle
                        if len(intra_resp.data.candles) >= 2:
                            final_candle = intra_resp.data.candles[1] # Last closed 1-min candle
                            
                            candle_timestamp = pd.to_datetime(final_candle[0])
                            
                            # Create refined candle data
                            candle_df = pd.DataFrame([{
                                'timestamp': candle_timestamp,
                                'open': float(final_candle[1]),
                                'high': float(final_candle[2]),
                                'low': float(final_candle[3]),
                                'close': float(final_candle[4]),
                                'volume': int(final_candle[5]),
                                'oi': int(final_candle[6]) if len(final_candle) > 6 else 0
                            }])

                            # Store and Dispatch
                            self.data_manager.db_manager.store_historical_candles(ticker, 'NSE', '1m', candle_df)
                            
                            # Calculate ATR for this candle using normalized cache key
                            candle_for_atr = {
                                'high': float(final_candle[2]),
                                'low': float(final_candle[3]),
                                'close': float(final_candle[4])
                            }
                            calculated_atr = self._calculate_atr(atr_cache_key, candle_for_atr)
                            
                            event = MarketEvent(
                                type=MessageType.MARKET_UPDATE,
                                timestamp=datetime.now().timestamp(),
                                symbol=ticker,
                                candle=VolumeBar(
                                    symbol=ticker,
                                    timestamp=candle_timestamp.timestamp(),
                                    open=float(final_candle[1]),
                                    high=float(final_candle[2]),
                                    low=float(final_candle[3]),
                                    close=float(final_candle[4]),
                                    volume=int(final_candle[5]),
                                    atr=calculated_atr
                                ),
                                sentiment=self.data_manager.get_current_sentiment(ticker, mode='live')
                            )

                            
                            print(f"[LiveTradingEngine] Dispatching FINALIZED candle for {ticker}: Close={event.candle.close}, Vol={event.candle.volume}")
                            self.option_chain_handler.on_event(event)
                            self.sentiment_handler.on_event(event)
                            
                            # Pattern Matcher ONLY for Indices
                            if ticker in ["NSE|INDEX|NIFTY", "NSE|INDEX|BANKNIFTY", "NIFTY", "BANKNIFTY", "NSE_INDEX|Nifty 50", "NSE_INDEX|Nifty Bank"]:
                                self.pattern_matcher_handler.on_event(event)
                            
                            self.execution_handler.on_event(event)

    def on_open(self):
        global streamer
        print("Streamer connection opened.")
        try:
            instruments = list(self.subscribed_instruments)
            print(f"Sending On OPEN  subscription for {len(instruments)} instruments...{datetime.now()}")
            streamer.subscribe(instruments, "full")
        except Exception as e:
            print(f"On Open  subscription failed: {e}")

    def on_error(self, error):
        print(f"Streamer Error: {error}")

    def on_close(self, code, reason):
        print(f"Streamer connection closed. Code: {code}, Reason: {reason}")

    def on_auto_reconnect_stopped(self, code, reason):
        print(f"Auto-reconnect stopped. Code: {code}, Reason: {reason}")

    def start_websocket_thread(self):
        """Starts the Upstox SDK MarketDataStreamerV3 in a background thread."""

        def run_streamer():
            global streamer
            print(f"Starting UPSTOX SDK Streamer with {len(self.symbols)} instruments...")

            # Map raw keys back to readable tickers for logging
            readable_subscriptions = [SymbolMaster.get_ticker_from_key(k) for k in self.subscribed_instruments]
            print(f"Subscribed Instruments: {readable_subscriptions}")

            configuration = upstox_client.Configuration()
            configuration.access_token = self.access_token

            try:
                api_client = upstox_client.ApiClient(configuration)
                streamer = MarketDataStreamerV3(api_client, list(self.subscribed_instruments), "full")

                streamer.on("message", self.on_message)
                streamer.on("open", self.on_open)
                streamer.on("error", self.on_error)
                streamer.on("close", self.on_close)
                streamer.on("autoReconnectStopped", self.on_auto_reconnect_stopped)

                streamer.auto_reconnect(True, 5, 5)

                # --- Periodic Subscription (Keep-Alive) ---
                def subscription_keep_alive(streamer_ref):
                    while True:
                        time.sleep(50)
                        try:
                            instruments = list(self.subscribed_instruments)
                            print(f"Sending periodic subscription for {len(instruments)} instruments...{datetime.now()}")
                            streamer_ref.subscribe(instruments, "full")
                        except Exception as e:
                            print(f"Periodic subscription failed: {e}")

                ka_thread = threading.Thread(target=subscription_keep_alive, args=(streamer,), daemon=True)
                ka_thread.start()

                print("Connecting to Upstox V3 via SDK...")
                streamer.connect()

            except Exception as e:
                print(f"SDK Streamer Fatal Error: {e}")

        t = threading.Thread(target=run_streamer, daemon=True)
        t.start()
        return t

    async def start(self):
        if not self.access_token:
            print("[ERROR] Upstox access token not found. Please add it to config.json.")
            print("         'upstox_access_token': 'YOUR_TOKEN'")
            return

        await self._pre_load_history()
        self.start_websocket_thread()
        print("Live trading engine started. Waiting for market data...")
        # Keep the main async thread alive
        while True:
            await asyncio.sleep(1)


async def run_live():
    Config.load('config.json')
    loop = asyncio.get_running_loop()
    engine = LiveTradingEngine(loop)
    await engine.start()
