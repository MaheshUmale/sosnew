from data_sourcing.tvdatafeed_client import TVDatafeedClient
from data_sourcing.upstox_gateway import UpstoxClient
from data_sourcing.trendlyne_client import TrendlyneClient
from data_sourcing.nse_client import NSEClient
from SymbolMaster import MASTER as SymbolMaster
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
        from engine_config import Config
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
            # Periodically update if needed - for now just append new ones if we fetch
            try:
                fresh_holidays = self.nse_client.get_holiday_list()
                if fresh_holidays:
                    new_holidays = [h for h in fresh_holidays if h not in self.holidays]
                    if new_holidays:
                        print(f"[DataManager] Found {len(new_holidays)} new holidays.")
                        self.db_manager.store_holidays(new_holidays)
                        self.holidays.extend(new_holidays)
            except:
                pass 
        SymbolMaster.initialize()

    def get_last_traded_price(self, symbol):
        """
        Fetches the Last Traded Price (LTP) for a given symbol using multiple sources.
        Prioritizes direct LTP APIs over historical candle fetching.
        """
        canonical_symbol = SymbolMaster.get_canonical_ticker(symbol)
        
        # 1. Try Upstox get_ltp if it's an index or we have the key
        try:
            instrument_key = SymbolMaster.get_upstox_key(canonical_symbol)
            if instrument_key:
                response = self.upstox_client.get_ltp(instrument_key)
                if response and response.data:
                    # 1. Try direct replace of | with :
                    resp_key = instrument_key.replace('|', ':')
                    if resp_key in response.data:
                        ltp = response.data[resp_key].last_price
                        print(f"[DataManager] LTP for {canonical_symbol} from Upstox (exact key): {ltp}")
                        return ltp
                    
                    # 2. Try mapped ticker if ISIN was used (for Equities)
                    ticker_key = f"{instrument_key.split('|')[0]}:{canonical_symbol}"
                    if ticker_key in response.data:
                        ltp = response.data[ticker_key].last_price
                        return ltp

                    # 3. Fallback: if only one instrument was requested, it must be the one we want
                    if len(response.data) == 1:
                        return list(response.data.values())[0].last_price
        except Exception as e:
            print(f"[DataManager] Upstox get_ltp failed: {e}")

        # 2. Try NSE get_indices for major indices
        if "NIFTY" in canonical_symbol.upper():
            try:
                indices_data = self.nse_client.get_indices()
                if indices_data and 'data' in indices_data:
                    target_name = "NIFTY 50" if "BANK" not in canonical_symbol.upper() else "NIFTY BANK"
                    for index in indices_data['data']:
                        if index.get('index', '').upper() == target_name:
                            ltp = index.get('last')
                            print(f"[DataManager] LTP for {canonical_symbol} from NSE: {ltp}")
                            return ltp
            except Exception as e:
                print(f"[DataManager] NSE get_indices failed: {e}")

        # 3. Fallback to historical candles (slowest)
        print(f"[DataManager] Falling back to historical candles for {canonical_symbol} LTP")
        candles = self.get_historical_candles(symbol, n_bars=1)
        if candles is not None and not candles.empty:
            ltp = candles.iloc[-1]['close']
            print(f"[DataManager] LTP for {canonical_symbol} from Historical Candles: {ltp}")
            return ltp
        
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

    def get_historical_candles(self, symbol, exchange='NSE', interval='1m', n_bars=100, from_date=None, to_date=None, mode='backtest'):
        print(f"[DataManager] get_historical_candles called for {symbol} | Interval: {interval}")
        
        # 0. Canonicalize Symbol
        canonical_symbol = SymbolMaster.get_canonical_ticker(symbol)
        
        # Ensure from_date and to_date are datetime objects
        if isinstance(from_date, str):
            try:
                from_date = datetime.strptime(from_date, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                from_date = datetime.strptime(from_date, '%Y-%m-%d')
        if isinstance(to_date, str):
            try:
                to_date = datetime.strptime(to_date, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                to_date = datetime.strptime(to_date, '%Y-%m-%d')
            
        if to_date is None:
            to_date = datetime.now()
        if from_date is None:
            from_date = to_date - timedelta(days=5)

        print(f"[DataManager] DB Query: Symbol={canonical_symbol}, From={from_date}, To={to_date}")

        # First, try to get data from the local database
        local_data = self.db_manager.get_historical_candles(canonical_symbol, exchange, interval, from_date, to_date)
        if local_data is not None and not local_data.empty:
            print(f"Loaded {len(local_data)} candles for {canonical_symbol} from local DB.")
            if from_date:
                return local_data
            if len(local_data) >= n_bars:
                return local_data.tail(n_bars)

        if mode == 'backtest':
            print(f"[DataManager] [ERROR] Historical data for {canonical_symbol} not found in DB during backtest.")
            return None

        # If not in DB or not enough data, fetch from external sources (LIVE ONLY)
        print(f"Fetching historical candles for {canonical_symbol} from remote source...")
        data_to_store = None
        
        # Try TVDatafeed first if configured
        if self.tv_client and "NIFTY" in canonical_symbol.upper() and self.tv_client.tv:
            from data_sourcing.tvdatafeed_client import Interval
            interval_map = {'1m': Interval.in_1_minute}
            
            # Map canonical symbol to TVDatafeed friendly symbol
            tv_symbol = "NIFTY" if "NIFTY" in canonical_symbol.upper() and "BANK" not in canonical_symbol.upper() else ("BANKNIFTY" if "BANK" in canonical_symbol.upper() else canonical_symbol)
            
            try:
                data = self.tv_client.get_historical_data(tv_symbol, exchange, interval_map.get(interval, Interval.in_1_minute), n_bars)
                if data is not None and not data.empty:
                    data.reset_index(inplace=True)
                    data.rename(columns={'datetime': 'timestamp'}, inplace=True)
                    data_to_store = data
            except Exception as e:
                print(f"[DataManager] TVDatafeed failed for {tv_symbol}: {e}")

        # If TVDatafeed disabled or failed, try Upstox
        # If TVDatafeed disabled or failed, try Upstox
        if data_to_store is None:
            try:
                instrument_key = SymbolMaster.get_upstox_key(canonical_symbol)
                # Upstox Interval Mapping
                upstox_interval_map = {
                    '1m': '1minute',
                    '5m': '5minute',
                    '15m': '15minute',
                    '30m': '30minute',
                    '1h': '1hour',  # Check API spec, usually 1hour or 60minute
                    '1d': 'day'
                }
                upstox_interval = upstox_interval_map.get(interval, interval)

                if instrument_key:
                    today = datetime.now().date()
                    print(f"[DataManager] Fetching Upstox Data for {canonical_symbol} ({instrument_key}) | Interval: {upstox_interval}")
                    if to_date.date() < today:
                        # get_historical_candle_data usually takes from_date, to_date strings
                        # IMPORTANT: Upstox API often provides data in reverse chrono or specific order.
                        # Ensure string format is correct (YYYY-MM-DD).
                        response = self.upstox_client.get_historical_candle_data(
                            instrument_key, 
                            upstox_interval, 
                            to_date.strftime('%Y-%m-%d'), 
                            from_date.strftime('%Y-%m-%d')
                        )
                    else:
                        response = self.upstox_client.get_intra_day_candle_data(instrument_key, upstox_interval)

                    if response and hasattr(response, 'data') and hasattr(response.data, 'candles') and response.data.candles:
                        # Upstox returns list of lists: [timestamp, open, high, low, close, volume, oi]
                        df = pd.DataFrame(response.data.candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'oi'])
                        
                        # Timestamp cleanup
                        df['timestamp'] = pd.to_datetime(df['timestamp']).dt.tz_localize(None) # Remove TZ if any, to match DB
                        
                        data_to_store = df
                    else:
                         print(f"[DataManager] Upstox returned no candles for {canonical_symbol} ({instrument_key})")
            except Exception as e:
                print(f"[DataManager] Upstox historical data failed for {symbol} (Key: {instrument_key}): {e}")

        if data_to_store is not None and not data_to_store.empty:
            self.db_manager.store_historical_candles(canonical_symbol, exchange, interval, data_to_store)
            print(f"Stored {len(data_to_store)} candles for {canonical_symbol} in local DB.")
            return data_to_store.tail(n_bars)

        return None

    def get_option_chain(self, symbol, date=None, mode='backtest'):
        target_date = datetime.strptime(date, '%Y-%m-%d') if date else datetime.now()
        date_str = target_date.strftime('%Y-%m-%d')

        # Try to get data from the local database first
        local_data = self.db_manager.get_option_chain(symbol, date_str)
        if local_data is not None and not local_data.empty:
            return local_data.to_dict('records')

        if mode == 'backtest':
            print(f"[DataManager] [ERROR] Option chain for {symbol} on {date_str} not found in DB during backtest.")
            return None

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
        print(f"[DataManager] Spot Price: {spot_price}, ATM Strike: {atm_strike}, Strike Range: {strike_range}")

        if not strike_range:
            return None

        chain_data = None
        # Priority: Upstox
        try:
            instrument_key = SymbolMaster.get_upstox_key(symbol)
            stock_id = self.trendlyne_client.get_stock_id_for_symbol(symbol)
            print(f"[DataManager] Upstox Key: {instrument_key}, Stock ID: {stock_id}")
            if instrument_key and stock_id:
                expiries = self.trendlyne_client.get_expiry_dates(stock_id)
                print(f"[DataManager] Expiries: {expiries}")
                if expiries:
                    response = self.upstox_client.get_put_call_option_chain(instrument_key, expiries[0])
                    if response and hasattr(response, 'data') and response.data:
                        print(f"[DataManager] Upstox Chain Data received: {len(response.data)} items")
                        chain = []
                        print(f"[DataManager] First few strikes from API: {[float(x.strike_price) for x in response.data[:5]]}")
                        for item in response.data:
                            strike = float(item.strike_price)
                            if strike in strike_range:
                                chain.append({
                                    "strike": strike,
                                    "call_oi_chg": item.call_options.market_data.oi - item.call_options.market_data.prev_oi,
                                    "put_oi_chg": item.put_options.market_data.oi - item.put_options.market_data.prev_oi,
                                    "call_instrument_key": item.call_options.instrument_key,
                                    "put_instrument_key": item.put_options.instrument_key,
                                    "call_oi": item.call_options.market_data.oi,
                                    "put_oi": item.put_options.market_data.oi
                                })
                        chain_data = pd.DataFrame(chain)
                        print(f"[DataManager] Chain DataFrame created: {len(chain_data)} rows")
                    else:
                        print(f"[DataManager] Upstox API returned no data for {instrument_key}")
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
        nifty_spot = self.get_last_traded_price('NSE|INDEX|NIFTY')
        banknifty_spot = self.get_last_traded_price('NSE|INDEX|BANKNIFTY')

        current_spots = {
            "NIFTY": nifty_spot,
            "BANKNIFTY": banknifty_spot
        }

        self.fno_instruments = self.instrument_loader.get_upstox_instruments(["NIFTY", "BANKNIFTY"], current_spots)
        return self.fno_instruments

    def get_atm_option_details(self, symbol, side, spot_price=None):
        instrument_data = self.fno_instruments.get(symbol)
        if not instrument_data:
            print(f"[DataManager] Error: Instrument data not found for {symbol}. Make sure fno_instruments is loaded.")
            return None, None

        if spot_price is None:
            full_symbol = "NSE|INDEX|NIFTY" if symbol == "NIFTY" else "NSE|INDEX|BANKNIFTY"
            spot_price = self.get_last_traded_price(full_symbol)
        
        if not spot_price:
             print(f"[DataManager] Error: Could not get spot price for {symbol}")
             return None, None

        # Find ATM strike
        # We need to find the strike closest to the spot price
        # instrument_data['options'] is a list of dicts with 'strike', 'ce', 'pe' etc.
        
        try:
            atm_strike = min(instrument_data['options'], key=lambda x: abs(x['strike'] - spot_price))
            print(f"[DataManager] ATM Resolution: Spot={spot_price}, ATM Strike={atm_strike['strike']}, Side={side}")

            if side == 'BUY':
                return atm_strike['ce'], atm_strike['ce_trading_symbol']
            else:
                return atm_strike['pe'], atm_strike['pe_trading_symbol']
        except Exception as e:
            print(f"[DataManager] Error calculating ATM strike: {e}")
            return None, None

    def get_historical_candle_for_timestamp(self, symbol, timestamp):
        dt_object = datetime.fromtimestamp(timestamp)
        from_date = dt_object - timedelta(minutes=1)
        to_date = dt_object + timedelta(minutes=1)

        # Use the existing method to get a range of candles, expecting only one
        candles_df = self.get_historical_candles(symbol, n_bars=1, from_date=from_date, to_date=to_date)

        if candles_df is not None and not candles_df.empty:
            # Since n_bars=1 and the time window is tight, we can assume the last row is the one we want
            candle_row = candles_df.iloc[-1]
            # Ensure timestamp is a datetime object
            ts = candle_row['timestamp']
            if isinstance(ts, str):
                ts = pd.to_datetime(ts)
            return VolumeBar(
                symbol=symbol,
                timestamp=ts.timestamp(),
                open=candle_row['open'],
                high=candle_row['high'],
                low=candle_row['low'],
                close=candle_row['close'],
                volume=candle_row['volume']
            )
        return None

    def get_atm_option_details_for_timestamp(self, underlying_symbol, side, spot_price, timestamp):
        """
        Finds the ATM option instrument key by constructing the symbol from historical
        option chain data and resolving it.
        """
        canonical_symbol = SymbolMaster.get_canonical_ticker(underlying_symbol)
        symbol_prefix = "BANKNIFTY" if "BANK" in underlying_symbol.upper() else "NIFTY"
        dt_object = datetime.fromtimestamp(timestamp)
        datetime_str = dt_object.strftime('%Y-%m-%d %H:%M:%S')

        try:
            # 1. Query the unified DB for the closest option chain snapshot
            with self.db_manager as db:
                query = """
                    SELECT * FROM option_chain_data
                    WHERE symbol = ? AND timestamp <= ?
                    ORDER BY timestamp DESC
                    LIMIT 500
                """ # Limit to nearest 500 to capture full chain even with duplicates
                df = pd.read_sql_query(query, db.conn, params=(canonical_symbol, datetime_str))

            if df.empty:
                print(f"No historical option chain data found for {symbol_prefix} at or before {datetime_str}")
                return None, None

            # The query returns the closest strikes for the latest timestamp.
            # The first row contains the expiry we need.
            expiry_str = df['expiry'].iloc[0]

            # 2. Calculate ATM strike
            atm_strike = self.calculate_atm_strike(symbol_prefix, spot_price)
            if atm_strike is None: return None, None

            # 3. Find the closest strike in the fetched DataFrame
            closest_strike_row = df.iloc[(df['strike'] - atm_strike).abs().argsort()[:1]]
            if closest_strike_row.empty:
                print(f"Could not find a matching strike for ATM {atm_strike} in the chain.")
                return None, None

            strike_price = int(closest_strike_row.iloc[0]['strike'])

            # 4. Construct the historical trading symbol
            option_type = "CE" if side.upper() == 'BUY' else "PE"
            try:
                expiry_dt = pd.to_datetime(expiry_str)
                if pd.isna(expiry_dt):
                    raise ValueError(f"Converted Expiry is NaT. Source: {expiry_str}")
                expiry_day = expiry_dt.strftime('%d')
                expiry_month = expiry_dt.strftime('%b').upper()
                expiry_year = expiry_dt.strftime('%y')
            except Exception as e:
                print(f"[DataManager] Expiry Parsing Error: {e}. Expiry Str: {expiry_str}")
                return None, None
            
            trading_symbol = f"{symbol_prefix} {strike_price} {option_type} {expiry_day} {expiry_month} {expiry_year}"
            
            # 5. Resolve the symbol to get the instrument key
            instrument_key = SymbolMaster.get_upstox_key(trading_symbol)

            if not instrument_key:
                print(f"Could not resolve instrument key for constructed symbol: {trading_symbol}")
                return None, None

            return instrument_key, trading_symbol

        except Exception as e:
            print(f"Error in get_atm_option_details_for_timestamp: {e}")
            return None, None


    def get_pcr(self, symbol, date=None, timestamp=None, mode='backtest'):
        """
        Retrieves PCR from the enriched market_stats table.
        """
        target_date = datetime.strptime(date, '%Y-%m-%d') if date else datetime.now()
        date_str = target_date.strftime('%Y-%m-%d')

        # 1. Try market_stats table (Enriched data)
        try:
            from_dt = target_date.replace(hour=9, minute=0)
            to_dt = target_date.replace(hour=15, minute=45)
            stats = self.db_manager.get_market_stats(symbol, from_dt, to_dt)
            if not stats.empty:
                if timestamp:
                    # Find closest timestamp
                    stats['timestamp'] = pd.to_datetime(stats['timestamp'])
                    target_ts = pd.to_datetime(timestamp)
                    closest_row = stats.iloc[(stats['timestamp'] - target_ts).abs().argsort()[:1]]
                    if not closest_row.empty:
                        return float(closest_row.iloc[0]['pcr'])
                else:
                    return float(stats.iloc[-1]['pcr'])
        except Exception as e:
            print(f"[DataManager] Error fetching PCR from market_stats: {e}")

        if mode == 'backtest':
            return 1.0 # Default

        # 2. Live Fallback: NSE Client
        data = self.nse_client.get_option_chain(symbol, indices=True)
        if data and 'records' in data and data.get('filtered'):
            ce_oi = data['filtered'].get('CE', {}).get('totOI', 0)
            pe_oi = data['filtered'].get('PE', {}).get('totOI', 0)
            if ce_oi > 0:
                pcr = round(pe_oi / ce_oi, 2)
                return pcr
            
        return 1.0
    def get_current_sentiment(self, symbol, timestamp=None, mode='backtest'):
        """
        Calculates and returns the current market sentiment for a given symbol.
        """
        pcr_value = self.get_pcr(symbol, timestamp=timestamp, mode=mode)
        
        # TODO: Implement actual advance/decline fetch logic
        # For now, default to neutral/balanced
        advances = 0
        declines = 0
        
        # Calculate OI walls
        # This is a simplified implementation. Real implementation would scan the whole chain.
        oi_wall_above = 0.0
        oi_wall_below = 0.0
        
        try:
            full_symbol = "NSE_INDEX|Nifty 50" if "NIFTY" in symbol else "NSE_INDEX|Nifty Bank"
            chain = self.get_option_chain(full_symbol)
            if chain:
                # Basic logic to find max OI
                df = pd.DataFrame(chain)
                if not df.empty:
                    spot = self.get_last_traded_price(full_symbol)
                    if spot:
                        # Call Wall (Above Spot)
                        calls = df[df['strike'] > spot]
                        if not calls.empty:
                            oi_wall_above = calls.loc[calls['call_oi'].idxmax()]['strike']
                        
                        # Put Wall (Below Spot)
                        puts = df[df['strike'] < spot]
                        if not puts.empty:
                            oi_wall_below = puts.loc[puts['put_oi'].idxmax()]['strike']
        except Exception as e:
            print(f"[DataManager] Error determining OI walls for {symbol}: {e}")

        # Determine Regime based on PCR
        # 0.7 < PCR < 1.3 -> SIDEWAYS
        # PCR < 0.7 -> BULLISH (Oversold) ? No, typically high PCR is bullish (put writing), low PCR is bearish.
        # Wait, SentimentHandler defines:
        # PCR < 0.7 -> COMPLETE_BULLISH
        # PCR > 1.3 -> COMPLETE_BEARISH
        # This seems inverted? Usually High PCR (>1) = Bullish (More Puts sold), Low PCR (<1) = Bearish.
        # However, checking SentimentHandler:
        # PCR_EXTREME_BULLISH = 0.7  (Check logic later)
        
        return Sentiment(
            pcr=pcr_value,
            advances=advances,
            declines=declines,
            pcr_velocity=0.0,
            oi_wall_above=oi_wall_above,
            oi_wall_below=oi_wall_below
        )
