from data_sourcing.tvdatafeed_client import TVDatafeedClient
from data_sourcing.upstox_client import UpstoxClient
from data_sourcing.trendlyne_client import TrendlyneClient
from data_sourcing.nse_client import NSEClient
from SymbolMaster import MASTER as SymbolMaster
import pandas as pd
from datetime import datetime, timedelta
from python_engine.utils.instrument_loader import InstrumentLoader

class DataManager:
    def __init__(self, access_token=None):
        self.instrument_loader = InstrumentLoader()
        self.fno_instruments = {}
        self.tv_client = TVDatafeedClient()
        self.upstox_client = UpstoxClient(access_token=access_token)
        self.trendlyne_client = TrendlyneClient()
        self.nse_client = NSEClient()
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

    def get_historical_candles(self, symbol, exchange='NSE', interval='1m', n_bars=100):
        from engine_config import Config
        # Prioritize tvDatafeed for index data with volume
        if Config.get('use_tvdatafeed', False) and "NIFTY" in symbol.upper():
            from data_sourcing.tvdatafeed.main import Interval
            interval_map = {'1m': Interval.in_1_minute}
            data = self.tv_client.get_historical_data(symbol, exchange, interval_map.get(interval, Interval.in_1_minute), n_bars)
            if data is not None and not data.empty:
                            
                #convert datetime index to timestamp column so that all sources return same DF columens
                data.reset_index(inplace=True)
                data.rename(columns={'datetime': 'timestamp'}, inplace=True)
                return data

        # Fallback to Upstox for all symbols
        try:
            instrument_key = SymbolMaster.get_upstox_key(symbol)
            if instrument_key:
                from datetime import datetime, timedelta
                to_date = datetime.now().strftime('%Y-%m-%d')
                from_date = (datetime.now() - timedelta(days=5)).strftime('%Y-%m-%d')
                response = self.upstox_client.get_historical_candle_data(instrument_key, interval, to_date, from_date)
                if response and hasattr(response, 'data') and hasattr(response.data, 'candles'):
                    df = pd.DataFrame(response.data.candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'oi'])
                    df['timestamp'] = pd.to_datetime(df['timestamp'])
                    return df
        except Exception as e:
            print(f"[DataManager] Upstox historical data failed for {symbol}: {e}")

        return None

    def get_option_chain(self, symbol):
        spot_price = self.get_last_traded_price(symbol)
        atm_strike = self.calculate_atm_strike(symbol, spot_price)
        strike_range = self._get_strike_range(symbol, atm_strike)

        if not strike_range:
            return None

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
                                    "put_oi_chg": item.put_options.market_data.oi - item.put_options.market_data.prev_oi
                                })
                        return chain
        except Exception as e:
            print(f"[DataManager] Upstox option chain failed for {symbol}: {e}")

        # Fallback to Trendlyne
        stock_id = self.trendlyne_client.get_stock_id_for_symbol(symbol)
        if stock_id:
            expiries = self.trendlyne_client.get_expiry_dates(stock_id)
            if expiries:
                from datetime import datetime
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
                    return chain
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
