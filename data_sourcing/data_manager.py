from data_sourcing.tvdatafeed_client import TVDatafeedClient
from data_sourcing.upstox_client import UpstoxClient
from data_sourcing.trendlyne_client import TrendlyneClient
from data_sourcing.nse_client import NSEClient
from SymbolMaster import MASTER as SymbolMaster
import pandas as pd
from datetime import datetime, timedelta
from python_engine.utils.instrument_loader import InstrumentLoader
from data_sourcing.database_manager import DatabaseManager
from python_engine.models.data_models import VolumeBar

class DataManager:
    def __init__(self, access_token=None):
        self.db_manager = DatabaseManager()
        self.db_manager.initialize_database()
        self.instrument_loader = InstrumentLoader()
        self.fno_instruments = {}
        self.tv_client = TVDatafeedClient()
        self.upstox_client = UpstoxClient(access_token=access_token)
        self.trendlyne_client = TrendlyneClient()
        self.nse_client = NSEClient()
        self.holidays = self.nse_client.get_holiday_list()
        SymbolMaster.initialize()

    def get_last_traded_price(self, symbol):
        candles = self.get_historical_candles(symbol, n_bars=1)
        if candles is not None and not candles.empty:
            return candles.iloc[-1]['close']
        return None

    def calculate_atm_strike(self, symbol, spot_price):
        if spot_price is None:
            return None
        strike_step = 100 if "BANKNIFTY" in symbol.upper() else 50
        return round(spot_price / strike_step) * strike_step

    def _get_strike_range(self, symbol, atm_strike):
        if atm_strike is None:
            return []
        strike_step = 100 if "BANKNIFTY" in symbol.upper() else 50
        return [atm_strike + i * strike_step for i in range(-5, 6)]

    def get_historical_candles(self, symbol, exchange='NSE', interval='1m', n_bars=100, from_date=None, to_date=None):
        from engine_config import Config
        if to_date is None:
            to_date = datetime.now()
        if from_date is None:
            from_date = to_date - timedelta(days=5)

        # First, try to get data from the local database
        local_data = self.db_manager.get_historical_candles(symbol, exchange, interval, from_date, to_date)
        # If from_date is specified, we assume the user wants data for that specific range from the DB.
        if from_date and local_data is not None and not local_data.empty:
            print(f"Loaded {len(local_data)} candles for {symbol} from local DB for the specified date range.")
            return local_data

        if local_data is not None and not local_data.empty and len(local_data) >= n_bars:
            print(f"Loaded {len(local_data)} candles for {symbol} from local DB.")
            return local_data.tail(n_bars)

        # If not in DB or not enough data, fetch from external sources
        print(f"Fetching historical candles for {symbol} from remote source...")
        data_to_store = None
        if Config.get('use_tvdatafeed', False) and "NIFTY" in symbol.upper():
            from data_sourcing.tvdatafeed.main import Interval
            interval_map = {'1m': Interval.in_1_minute}
            data = self.tv_client.get_historical_data(symbol, exchange, interval_map.get(interval, Interval.in_1_minute), n_bars)
            if data is not None and not data.empty:
                data.reset_index(inplace=True)
                data.rename(columns={'datetime': 'timestamp'}, inplace=True)
                data_to_store = data
        else:
            try:
                instrument_key = SymbolMaster.get_upstox_key(symbol)
                if instrument_key:
                    today = datetime.now().date()
                    if to_date.date() < today:
                        response = self.upstox_client.get_historical_candle_data(instrument_key, interval, to_date.strftime('%Y-%m-%d'), from_date.strftime('%Y-%m-%d'))
                    else:
                        response = self.upstox_client.get_intra_day_candle_data(instrument_key, interval)

                    if response and hasattr(response, 'data') and hasattr(response.data, 'candles'):
                        df = pd.DataFrame(response.data.candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'oi'])
                        df['timestamp'] = pd.to_datetime(df['timestamp'])
                        data_to_store = df
            except Exception as e:
                print(f"[DataManager] Upstox historical data failed for {symbol}: {e}")

        if data_to_store is not None and not data_to_store.empty:
            self.db_manager.store_historical_candles(symbol, exchange, interval, data_to_store)
            print(f"Stored {len(data_to_store)} candles for {symbol} in local DB.")
            return data_to_store.tail(n_bars)

        return None

    def get_option_chain(self, symbol, date=None):
        target_date = datetime.strptime(date, '%Y-%m-%d') if date else datetime.now()
        date_str = target_date.strftime('%Y-%m-%d')

        # Try to get data from the local database first
        local_data = self.db_manager.get_option_chain(symbol, date_str)
        if local_data is not None and not local_data.empty:
            print(f"Loaded option chain for {symbol} on {date_str} from local DB.")
            return local_data.to_dict('records')

        print(f"Fetching option chain for {symbol} for date {date_str} from remote source...")

        # For historical dates, we need to fetch a historical spot price for that day
        if date:
            candles = self.get_historical_candles(symbol, from_date=date, to_date=date, n_bars=1)
            if candles is not None and not candles.empty:
                spot_price = candles.iloc[-1]['close']
            else:
                print(f"Could not fetch historical spot price for {symbol} on {date_str}")
                return None
        else:
            spot_price = self.get_last_traded_price(symbol)
        atm_strike = self.calculate_atm_strike(symbol, spot_price)
        strike_range = self._get_strike_range(symbol, atm_strike)

        if not strike_range:
            return None

        chain_data = None
        # Priority: Upstox
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
                                    "call_oi_chg": item.call_options.market_data.oi - item.call_options.market_data.prev_oi,
                                    "put_oi_chg": item.put_options.market_data.oi - item.put_options.market_data.prev_oi,
                                    "call_instrument_key": item.call_options.instrument_key,
                                    "put_instrument_key": item.put_options.instrument_key
                                })
                        chain_data = pd.DataFrame(chain)
        except Exception as e:
            print(f"[DataManager] Upstox option chain failed for {symbol}: {e}")

        # Fallback to Trendlyne if Upstox fails or returns no data
        if chain_data is None or chain_data.empty:
            stock_id = self.trendlyne_client.get_stock_id_for_symbol(symbol)
            if stock_id:
                expiries = self.trendlyne_client.get_expiry_dates(stock_id)
                if expiries:
                    now = datetime.now()
                    data = self.trendlyne_client.get_live_oi_data(stock_id, expiries[0], "09:15", now.strftime("%H:%M"))
                    if data and data.get('body', {}).get('oiData'):
                        chain = []
                        for strike_str, strike_data in data['body']['oiData'].items():
                            strike = float(strike_str)
                            if strike in strike_range:
                                chain.append({
                                    "strike": strike,
                                    "call_oi_chg": int(strike_data.get('callOiChange', 0)),
                                    "put_oi_chg": int(strike_data.get('putOiChange', 0))
                                })
                        chain_data = pd.DataFrame(chain)

        if chain_data is not None and not chain_data.empty:
            self.db_manager.store_option_chain(symbol, chain_data, date=date_str)
            print(f"Stored option chain for {symbol} for {date_str} in local DB.")
            return chain_data.to_dict('records')

        return None

    def get_market_breadth(self):
        return self.nse_client.get_market_breadth()

    def get_option_delta(self, option_symbol):
        # TODO: In a real implementation, you would fetch the delta from a data provider.
        # For now, we'll return a hardcoded value.
        return 0.5

    def load_and_cache_fno_instruments(self):
        nifty_spot = self.get_last_traded_price('NSE_INDEX|Nifty 50')
        banknifty_spot = self.get_last_traded_price('NSE_INDEX|Nifty Bank')

        current_spots = {
            "NIFTY": nifty_spot,
            "BANKNIFTY": banknifty_spot
        }

        self.fno_instruments = self.instrument_loader.get_upstox_instruments(["NIFTY", "BANKNIFTY"], current_spots)
        return self.fno_instruments

    def get_atm_option_details(self, symbol, side):
        instrument_data = self.fno_instruments.get(symbol)
        if not instrument_data:
            return None, None

        full_symbol = "NSE_INDEX|Nifty 50" if symbol == "NIFTY" else "NSE_INDEX|Nifty Bank"
        spot_price = self.get_last_traded_price(full_symbol)
        atm_strike = min(instrument_data['options'], key=lambda x: abs(x['strike'] - spot_price))

        if side == 'BUY':
            return atm_strike['ce'], atm_strike['ce_trading_symbol']
        else:
            return atm_strike['pe'], atm_strike['pe_trading_symbol']

    def get_historical_candle_for_timestamp(self, symbol, timestamp):
        dt_object = datetime.fromtimestamp(timestamp)
        from_date = dt_object - timedelta(minutes=1)
        to_date = dt_object + timedelta(minutes=1)

        # Use the existing method to get a range of candles, expecting only one
        candles_df = self.get_historical_candles(symbol, n_bars=1, from_date=from_date, to_date=to_date)

        if candles_df is not None and not candles_df.empty:
            # Since n_bars=1 and the time window is tight, we can assume the last row is the one we want
            candle_row = candles_df.iloc[-1]
            return VolumeBar(
                symbol=symbol,
                timestamp=candle_row['timestamp'].timestamp(),
                open=candle_row['open'],
                high=candle_row['high'],
                low=candle_row['low'],
                close=candle_row['close'],
                volume=candle_row['volume']
            )
        return None

    def get_atm_option_details_for_timestamp(self, underlying_symbol, side, spot_price, timestamp):
        """
        Finds the ATM option instrument key from the local database for a given timestamp.
        """
        dt_object = datetime.fromtimestamp(timestamp)
        date_str = dt_object.strftime('%Y-%m-%d')

        # 1. Get option chain for that day from the database
        option_chain_df = self.db_manager.get_option_chain(underlying_symbol, date_str)

        if option_chain_df is None or option_chain_df.empty:
            print(f"No option chain data found in DB for {underlying_symbol} on {date_str}")
            return None, None

        # 2. Calculate ATM strike
        atm_strike = self.calculate_atm_strike(underlying_symbol, spot_price)
        if atm_strike is None:
            return None, None

        # 3. Find the closest strike in the option chain
        closest_strike_row = option_chain_df.iloc[(option_chain_df['strike'] - atm_strike).abs().argsort()[:1]]

        if closest_strike_row.empty:
            print(f"Could not find a matching strike for ATM {atm_strike} in the option chain.")
            return None, None

        # 4. Return the correct instrument key and the trading symbol
        option_row = closest_strike_row.iloc[0]
        instrument_key = option_row['call_instrument_key'] if side.upper() == 'BUY' else option_row['put_instrument_key']

        trading_symbol = SymbolMaster.get_trading_symbol(instrument_key)

        if not trading_symbol:
             trading_symbol = instrument_key # Fallback

        return instrument_key, trading_symbol


    def get_pcr(self, symbol):
        data = self.nse_client.get_option_chain(symbol, indices=True)
        if data and 'records' in data:
            filtered = data.get('filtered', {})
            if filtered:
                ce_oi = filtered.get('CE', {}).get('totOI', 0)
                pe_oi = filtered.get('PE', {}).get('totOI', 0)
                if ce_oi > 0:
                    return round(pe_oi / ce_oi, 2)
        return 1.0
