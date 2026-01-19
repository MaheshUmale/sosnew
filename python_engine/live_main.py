import asyncio
import threading
import time
import pandas as pd
from datetime import datetime
import upstox_client
from upstox_client.feeder.market_data_feeder_v3 import MarketDataFeederV3
from python_engine.models.data_models import MarketEvent, MessageType, VolumeBar
from python_engine.engine_config import Config
from python_engine.core.order_orchestrator import OrderOrchestrator
from python_engine.core.trade_logger import TradeLog
from python_engine.core.trading_engine import TradingEngine
from data_sourcing.data_manager import DataManager
from python_engine.utils.symbol_master import MASTER as SymbolMaster

class LiveTradingEngine:
    def __init__(self, loop):
        self.loop = loop
        self.access_token = Config.get('upstox_access_token')
        self.data_manager = DataManager(access_token=self.access_token)
        self.trade_log = TradeLog('live_trades.csv')
        self.order_orchestrator = OrderOrchestrator(self.trade_log, self.data_manager, "live")
        self.engine = TradingEngine(self.order_orchestrator, self.data_manager, Config.get('strategies_dir'))
        self.symbols = ["NSE|INDEX|NIFTY", "NSE|INDEX|BANKNIFTY"]
        self.subscribed_instruments = self._get_subscriptions()
        self._last_min = {}

    def _get_subscriptions(self):
        subs = {SymbolMaster.get_upstox_key(s) for s in self.symbols if SymbolMaster.get_upstox_key(s)}
        spots = {"NIFTY": self.data_manager.get_last_traded_price("NSE|INDEX|NIFTY", mode='live'),
                 "BANKNIFTY": self.data_manager.get_last_traded_price("NSE|INDEX|BANKNIFTY", mode='live')}
        fno = self.data_manager.instrument_loader.get_upstox_instruments(["NIFTY", "BANKNIFTY"], spots)
        for data in fno.values():
            for opt in data['options']:
                subs.update([opt['ce'], opt['pe']])
        return {s for s in subs if s}

    def on_message(self, message):
        feeds = message.get('feeds', {})
        for key, feed in feeds.items():
            ohlc = feed.get('fullFeed', {}).get('marketOHLC', {}).get('ohlc', [])
            candle_1m = next((o for o in ohlc if o.get('interval') == 'I1'), None)
            if not candle_1m: continue
            
            ts = int(candle_1m['ts'])
            ticker = SymbolMaster.get_ticker_from_key(key)
            if ticker not in self._last_min: self._last_min[ticker] = ts; continue

            if ts > self._last_min[ticker]:
                self._last_min[ticker] = ts
                self.loop.call_soon_threadsafe(lambda: asyncio.create_task(self.process_candle(key, ticker)))

    async def process_candle(self, key, ticker):
        resp = self.data_manager.upstox_client.get_intra_day_candle_data(key, '1m')
        if resp and hasattr(resp, 'data') and len(resp.data.candles) >= 2:
            c = resp.data.candles[1]
            df = pd.DataFrame([{'timestamp': pd.to_datetime(c[0]), 'open': float(c[1]), 'high': float(c[2]), 'low': float(c[3]), 'close': float(c[4]), 'volume': int(c[5])}])
            self.data_manager.db_manager.store_historical_candles(ticker, 'NSE', '1m', df)

            # Use Repository for sentiment to stay consistent with Backtest
            repo = self.engine.repository
            stats = repo.get_closest_stats(ticker, pd.to_datetime(c[0]))

            event = MarketEvent(
                type=MessageType.MARKET_UPDATE,
                timestamp=int(pd.to_datetime(c[0]).timestamp()),
                symbol=ticker,
                candle=VolumeBar(symbol=ticker, timestamp=int(pd.to_datetime(c[0]).timestamp()), open=float(c[1]), high=float(c[2]), low=float(c[3]), close=float(c[4]), volume=int(c[5])),
                sentiment=self.data_manager.get_current_sentiment(ticker, mode='live') # Fallback to live fetch for now
            )
            for handler in self.engine.pipeline:
                handler.on_event(event)

    def start_websocket(self):
        conf = upstox_client.Configuration()
        conf.access_token = self.access_token
        streamer = MarketDataFeederV3(upstox_client.ApiClient(conf), list(self.subscribed_instruments), "full")
        streamer.on("message", self.on_message)
        threading.Thread(target=streamer.connect, daemon=True).start()

    async def start(self):
        self.start_websocket()
        while True: await asyncio.sleep(1)

async def run_live():
    engine = LiveTradingEngine(asyncio.get_running_loop())
    await engine.start()
