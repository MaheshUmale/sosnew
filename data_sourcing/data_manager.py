from data_sourcing.tvdatafeed_client import TVDatafeedClient
from data_sourcing.upstox_gateway import UpstoxClient
from data_sourcing.trendlyne_client import TrendlyneClient
from data_sourcing.nse_client import NSEClient
from python_engine.utils.symbol_master import MASTER as SymbolMaster
import pandas as pd
from datetime import datetime, timedelta
from python_engine.utils.instrument_loader import InstrumentLoader
from data_sourcing.database_manager import DatabaseManager
from python_engine.models.data_models import VolumeBar, Sentiment

class DataManager:
    def __init__(self, access_token=None):
        self.db_manager = DatabaseManager()
        self.db_manager.initialize_database()
        self.instrument_loader = InstrumentLoader()
        self.fno_instruments = {}
        from python_engine.engine_config import Config
        try:
            Config.load('config.json')
        except Exception as e:
            print(f"[DataManager] Warning: Could not load config.json: {e}")
            
        self.tv_client = TVDatafeedClient() if Config.get('use_tvdatafeed', False) else None

        self.upstox_client = UpstoxClient(access_token=access_token)
        self.trendlyne_client = TrendlyneClient()
        self.nse_client = NSEClient()
        cached_holidays = self.db_manager.get_holidays()
        if not cached_holidays:
            self.holidays = self.nse_client.get_holiday_list()
            if self.holidays:
                self.db_manager.store_holidays(self.holidays)
        else:
            self.holidays = cached_holidays
            try:
                fresh_holidays = self.nse_client.get_holiday_list()
                if fresh_holidays:
                    new_holidays = [h for h in fresh_holidays if h not in self.holidays]
                    if new_holidays:
                        print(f"[DataManager] Found {len(new_holidays)} new holidays.")
                        self.db_manager.store_holidays(new_holidays)
                        self.holidays.extend(new_holidays)
            except Exception as e:
                pass 
        SymbolMaster.initialize()

    def get_last_traded_price(self, symbol, mode='backtest'):
        canonical_symbol = SymbolMaster.get_canonical_ticker(symbol)
        try:
            instrument_key = SymbolMaster.get_upstox_key(canonical_symbol)
            if instrument_key:
                response = self.upstox_client.get_ltp(instrument_key)
                if response and response.data:
                    resp_key = instrument_key.replace('|', ':')
                    if resp_key in response.data:
                        return response.data[resp_key].last_price
                    if len(response.data) == 1:
                        return list(response.data.values())[0].last_price
        except Exception as e: pass

        if "NIFTY" in canonical_symbol.upper():
            try:
                indices_data = self.nse_client.get_indices()
                if indices_data and 'data' in indices_data:
                    target_name = "NIFTY 50" if "BANK" not in canonical_symbol.upper() else "NIFTY BANK"
                    for index in indices_data['data']:
                        if index.get('index', '').upper() == target_name:
                            return index.get('last')
            except Exception as e: pass

        candles = self.get_historical_candles(symbol, n_bars=1, mode=mode)
        if candles is not None and not candles.empty:
            return candles.iloc[-1]['close']
        return None

    def calculate_atm_strike(self, symbol, spot_price):
        if spot_price is None: return None
        strike_step = 100 if "BANKNIFTY" in symbol.upper() else 50
        return round(spot_price / strike_step) * strike_step

    def _get_strike_range(self, symbol, atm_strike):
        if atm_strike is None: return []
        strike_step = 100 if "BANKNIFTY" in symbol.upper() else 50
        return [atm_strike + i * strike_step for i in range(-5, 6)]

    def get_historical_candles(self, symbol, exchange='NSE', interval='1m', n_bars=100, from_date=None, to_date=None, mode='backtest'):
        canonical_symbol = SymbolMaster.get_canonical_ticker(symbol)
        if isinstance(from_date, str):
            try: from_date = datetime.strptime(from_date, '%Y-%m-%d %H:%M:%S')
            except Exception as e: from_date = datetime.strptime(from_date, '%Y-%m-%d')
        if isinstance(to_date, str):
            try: to_date = datetime.strptime(to_date, '%Y-%m-%d %H:%M:%S')
            except Exception as e: to_date = datetime.strptime(to_date, '%Y-%m-%d')
            
        if to_date is None: to_date = datetime.now()
        if from_date is None: from_date = to_date - timedelta(days=5)

        local_data = self.db_manager.get_historical_candles(canonical_symbol, exchange, interval, from_date, to_date)
        if local_data is not None and not local_data.empty:
            local_data['timestamp_dt'] = pd.to_datetime(local_data['timestamp'])
            sorted_df = local_data.sort_values('timestamp_dt')
            if mode == 'backtest' or len(sorted_df) >= n_bars:
                 return sorted_df.tail(n_bars) if not from_date else sorted_df

        if mode == 'backtest':
            print(f"[DataManager] [ERROR] Historical data for {canonical_symbol} not found in DB during backtest.")
            return None

        # Fetch from remote
        data_to_store = None
        if self.tv_client and self.tv_client.tv:
            from data_sourcing.tvdatafeed_client import Interval
            interval_map = {'1m': Interval.in_1_minute, '5m': Interval.in_5_minute, '1d': Interval.in_daily}
            tv_symbol = "NIFTY" if canonical_symbol == "NSE|INDEX|NIFTY" else "BANKNIFTY" if canonical_symbol == "NSE|INDEX|BANKNIFTY" else canonical_symbol
            
            # Intelligent n_bars calculation
            days_diff = (datetime.now() - from_date).days + 1
            calculated_bars = days_diff * 400 + 100 # buffer
            request_bars = max(n_bars, calculated_bars)

            try:
                data = self.tv_client.get_historical_data(tv_symbol, exchange, interval_map.get(interval, Interval.in_1_minute), request_bars)
                if data is not None and not data.empty:
                    data.reset_index(inplace=True)
                    data.rename(columns={'datetime': 'timestamp'}, inplace=True)
                    data_to_store = data
            except Exception as e: pass

        if data_to_store is None:
            try:
                instrument_key = SymbolMaster.get_upstox_key(canonical_symbol)
                upstox_interval_map = {'1m': '1minute', '5m': '5minute', '1d': 'day'}
                upstox_interval = upstox_interval_map.get(interval, interval)

                if instrument_key:
                    today = datetime.now().date()
                    if to_date.date() < today:
                        response = self.upstox_client.get_historical_candle_data(instrument_key, upstox_interval, to_date.strftime('%Y-%m-%d'), from_date.strftime('%Y-%m-%d'))
                    else:
                        response = self.upstox_client.get_intra_day_candle_data(instrument_key, upstox_interval)

                    if response and hasattr(response, 'data') and response.data.candles:
                        df = pd.DataFrame(response.data.candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'oi'])
                        df['timestamp'] = pd.to_datetime(df['timestamp']).dt.tz_localize(None)
                        data_to_store = df
            except Exception as e: pass

        if data_to_store is not None and not data_to_store.empty:
            self.db_manager.store_historical_candles(canonical_symbol, exchange, interval, data_to_store)
            return data_to_store.tail(n_bars)

        return None

    def get_option_chain(self, symbol, date=None, mode='backtest'):
        target_date = datetime.strptime(date, '%Y-%m-%d') if date else datetime.now()
        date_str = target_date.strftime('%Y-%m-%d')

        local_data = self.db_manager.get_option_chain(symbol, date_str)
        if local_data is not None and not local_data.empty:
            return local_data.to_dict('records')

        if mode == 'backtest':
            print(f"[DataManager] [ERROR] Option chain for {symbol} on {date_str} not found in DB.")
            return None

        # Fetch remote
        if date:
            candles = self.get_historical_candles(symbol, from_date=date, to_date=date, n_bars=1)
            spot_price = candles.iloc[-1]['close'] if candles is not None and not candles.empty else None
        else:
            spot_price = self.get_last_traded_price(symbol)

        if not spot_price: return None
        atm_strike = self.calculate_atm_strike(symbol, spot_price)
        strike_range = self._get_strike_range(symbol, atm_strike)

        chain_data = None
        try:
            instrument_key = SymbolMaster.get_upstox_key(symbol)
            stock_id = self.trendlyne_client.get_stock_id_for_symbol(symbol)
            if instrument_key and stock_id:
                expiries = self.trendlyne_client.get_expiry_dates(stock_id)
                if expiries:
                    response = self.upstox_client.get_put_call_option_chain(instrument_key, expiries[0])
                    if response and response.data:
                        chain = []
                        for item in response.data:
                            strike = float(item.strike_price)
                            if strike in strike_range:
                                chain.append({
                                    "strike": strike,
                                    "call_oi": item.call_options.market_data.oi,
                                    "put_oi": item.put_options.market_data.oi,
                                    "call_oi_chg": item.call_options.market_data.oi - item.call_options.market_data.prev_oi,
                                    "put_oi_chg": item.put_options.market_data.oi - item.put_options.market_data.prev_oi,
                                    "call_instrument_key": item.call_options.instrument_key,
                                    "put_instrument_key": item.put_options.instrument_key,
                                    "call_ltp": getattr(item.call_options.market_data, 'last_price', getattr(item.call_options.market_data, 'ltp', 0)),
                                    "put_ltp": getattr(item.put_options.market_data, 'last_price', getattr(item.put_options.market_data, 'ltp', 0))
                                })
                        chain_data = pd.DataFrame(chain)
        except Exception as e: pass

        if (chain_data is None or chain_data.empty) and stock_id:
            expiries = self.trendlyne_client.get_expiry_dates(stock_id)
            if expiries:
                expiry_date = expiries[0]
                data = self.trendlyne_client.get_live_oi_data(stock_id, expiry_date, "09:15", datetime.now().strftime("%H:%M"))
                if data and data.get('body', {}).get('oiData'):
                    chain = []
                    for strike_str, strike_data in data['body']['oiData'].items():
                        strike = float(strike_str)
                        if strike in strike_range:
                            chain.append({
                                "strike": strike, "expiry": expiry_date,
                                "call_oi": int(strike_data.get('callOi', 0)),
                                "put_oi": int(strike_data.get('putOi', 0)),
                                "call_oi_chg": int(strike_data.get('callOiChange', 0)),
                                "put_oi_chg": int(strike_data.get('putOiChange', 0))
                            })
                    chain_data = pd.DataFrame(chain)

        if chain_data is not None and not chain_data.empty:
            self.db_manager.store_option_chain(symbol, chain_data, date=date_str)
            return chain_data.to_dict('records')
        return None

    def load_and_cache_fno_instruments(self, mode='backtest', target_date=None):
        spots = { "NIFTY": self.get_last_traded_price('NSE|INDEX|NIFTY', mode=mode),
                  "BANKNIFTY": self.get_last_traded_price('NSE|INDEX|BANKNIFTY', mode=mode) }
        self.fno_instruments = self.instrument_loader.get_upstox_instruments(["NIFTY", "BANKNIFTY"], spots, target_date=target_date)
        return self.fno_instruments

    def get_atm_option_details(self, symbol, side, spot_price=None, mode='backtest', target_date=None):
        instrument_data = self.fno_instruments.get(symbol)
        if not instrument_data: return None, None
        if spot_price is None:
            full_symbol = "NSE|INDEX|NIFTY" if symbol == "NIFTY" else "NSE|INDEX|BANKNIFTY"
            if target_date:
                candles = self.get_historical_candles(full_symbol, from_date=target_date, to_date=target_date, n_bars=1, mode=mode)
                spot_price = candles.iloc[-1]['close'] if candles is not None and not candles.empty else None
            if spot_price is None: spot_price = self.get_last_traded_price(full_symbol, mode=mode)
        if not spot_price: return None, None
        try:
            atm_strike = min(instrument_data['options'], key=lambda x: abs(x['strike'] - spot_price))
            return (atm_strike['ce'], atm_strike['ce_trading_symbol']) if side == 'BUY' else (atm_strike['pe'], atm_strike['pe_trading_symbol'])
        except Exception as e: return None, None

    def get_historical_candle_for_timestamp(self, symbol, timestamp):
        dt = datetime.fromtimestamp(timestamp)
        df = self.get_historical_candles(symbol, n_bars=10, from_date=dt-timedelta(seconds=30), to_date=dt+timedelta(seconds=30))
        if df is not None and not df.empty:
            df['diff'] = (pd.to_datetime(df['timestamp']) - dt).abs()
            row = df.sort_values('diff').iloc[0]
            ts = pd.to_datetime(row['timestamp'])
            return VolumeBar(symbol=symbol, timestamp=ts.timestamp(), open=row['open'], high=row['high'], low=row['low'], close=row['close'], volume=row['volume'])
        return None

    def get_atm_option_details_for_timestamp(self, underlying_symbol, side, spot_price, timestamp):
        canonical_symbol = SymbolMaster.get_canonical_ticker(underlying_symbol)
        symbol_prefix = "BANKNIFTY" if "BANK" in underlying_symbol.upper() else "NIFTY"
        datetime_str = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
        try:
            with self.db_manager as db:
                query = "SELECT * FROM option_chain_data WHERE symbol = ? AND timestamp <= ? ORDER BY timestamp DESC LIMIT 500"
                df = pd.read_sql_query(query, db.conn, params=(canonical_symbol, datetime_str))
            if df.empty: return None, None
            expiry_str = df['expiry'].iloc[0]
            atm_strike_val = self.calculate_atm_strike(symbol_prefix, spot_price)
            row = df.iloc[(df['strike'] - atm_strike_val).abs().argsort()[:1]].iloc[0]
            strike_price = int(row['strike'])
            option_type = "CE" if side.upper() == 'BUY' else "PE"
            expiry_dt = pd.to_datetime(expiry_str)
            trading_symbol = f"{symbol_prefix} {strike_price} {option_type} {expiry_dt.strftime('%d %b %y').upper()}"
            key = row.get('call_instrument_key' if option_type == 'CE' else 'put_instrument_key') or SymbolMaster.get_upstox_key(trading_symbol)
            if not key: return None, None
            actual_tsym = SymbolMaster.get_ticker_from_key(key)
            return key, (actual_tsym if actual_tsym and actual_tsym != key else trading_symbol)
        except Exception as e: return None, None

    def get_pcr(self, symbol, date=None, timestamp=None, mode='backtest'):
        target_date = datetime.strptime(date, '%Y-%m-%d') if date else datetime.now()
        try:
            stats = self.db_manager.get_market_stats(symbol, target_date.replace(hour=9, minute=0), target_date.replace(hour=15, minute=45))
            if not stats.empty:
                if timestamp:
                    target_ts = pd.to_datetime(timestamp)
                    return float(stats.iloc[(pd.to_datetime(stats['timestamp']) - target_ts).abs().argsort()[:1]].iloc[0]['pcr'])
                return float(stats.iloc[-1]['pcr'])
        except Exception as e: pass
        if mode == 'backtest': return 1.0
        data = self.nse_client.get_option_chain(symbol, indices=True)
        if data and data.get('filtered'):
            ce, pe = data['filtered'].get('CE', {}).get('totOI', 0), data['filtered'].get('PE', {}).get('totOI', 0)
            if ce > 0: return round(pe / ce, 2)
        return 1.0

    def get_current_sentiment(self, symbol, timestamp=None, mode='backtest'):
        pcr = self.get_pcr(symbol, timestamp=timestamp, mode=mode)
        oi_above, oi_below = 0.0, 0.0
        try:
            full_symbol = "NSE_INDEX|Nifty 50" if "NIFTY" in symbol else "NSE_INDEX|Nifty Bank"
            chain = self.get_option_chain(full_symbol, mode=mode)
            if chain:
                df = pd.DataFrame(chain)
                spot = self.get_last_traded_price(full_symbol)
                if not df.empty and spot:
                    calls, puts = df[df['strike'] > spot], df[df['strike'] < spot]
                    if not calls.empty: oi_above = calls.loc[calls['call_oi'].idxmax()]['strike']
                    if not puts.empty: oi_below = puts.loc[puts['put_oi'].idxmax()]['strike']
        except Exception as e: pass
        smart_trend = "Neutral"
        try:
            date_str = pd.to_datetime(timestamp, unit='s').strftime('%Y-%m-%d')
            stats = self.db_manager.get_market_stats(symbol, date_str, pd.to_datetime(timestamp, unit='s').strftime('%Y-%m-%d %H:%M:%S'))
            if not stats.empty: smart_trend = stats.iloc[-1].get('smart_trend', 'Neutral')
        except Exception as e: pass
        return Sentiment(pcr=pcr, advances=0, declines=0, pcr_velocity=0.0, oi_wall_above=oi_above, oi_wall_below=oi_below, smart_trend=smart_trend)

    def get_option_delta(self, instrument_key):
        """Returns the delta for the given option instrument key from the DB."""
        try:
            with self.db_manager as db:
                query = "SELECT call_delta, put_delta FROM option_chain_data WHERE (call_instrument_key = ? OR put_instrument_key = ?) ORDER BY timestamp DESC LIMIT 1"
                row = db.conn.execute(query, (instrument_key, instrument_key)).fetchone()
                if row:
                    return row[0] if row[0] != 0 else row[1]
        except Exception as e: pass
        return 0.5 # Default
