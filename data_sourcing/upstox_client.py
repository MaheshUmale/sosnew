import upstox_client
import os
try:
    from engine_config import Config as UpstoxConfig
    UPSTOX_AVAILABLE = True
except ImportError:
    UPSTOX_AVAILABLE = False
    print("[UpstoxClient] engine_config.py not found, Upstox functionality will be disabled.")

class UpstoxClient:
    def __init__(self, access_token=None):
        self.api_client = None
        if UPSTOX_AVAILABLE:
            if not access_token:
                from engine_config import Config
                access_token = Config.get('upstox_access_token')

            if access_token:
                self.configuration = upstox_client.Configuration()
                self.configuration.access_token = access_token
                self.api_client = upstox_client.ApiClient(self.configuration)
            else:
                print("[UpstoxClient] Not initialized due to missing 'upstox_access_token' in config.json.")
        else:
            print("[UpstoxClient] Not initialized due to missing config or library.")

    def get_historical_candle_data(self, instrument_key, interval, to_date, from_date):
        if not self.api_client: return None
        history_api = upstox_client.HistoryV3Api(self.api_client)

        # More robust interval mapping
        if 'm' in interval:
            unit = 'minutes'
            value = interval.replace('m', '')
        elif 'd' in interval:
            unit = 'day'
            value = interval.replace('d', '')
        else:
            unit = 'minutes'
            value = '1'

        try:
            return history_api.get_historical_candle_data1(
                instrument_key=instrument_key,
                unit=unit,
                interval=value,
                to_date=to_date,
                from_date=from_date
            )
        except upstox_client.ApiException as e:
            print(f"[UpstoxClient] API Error in get_historical_candle_data: {e.body}")
            return None

    def get_intra_day_candle_data(self, instrument_key, interval):
        if not self.api_client: return None
        history_api = upstox_client.HistoryV3Api(self.api_client)

        if 'm' in interval:
            unit = 'minutes'
            value = interval.replace('m', '')
        else: # Default to 1 minute for intraday
            unit = 'minutes'
            value = '1'

        try:
            return history_api.get_intra_day_candle_data(
                instrument_key=instrument_key,
                unit=unit,
                interval=value
            )
        except upstox_client.ApiException as e:
            print(f"[UpstoxClient] API Error in get_intra_day_candle_data: {e.body}")
            return None

    def get_market_data_feed_authorize(self):
        if not self.api_client: return None
        websocket_api = upstox_client.WebsocketApi(self.api_client)
        return websocket_api.get_market_data_feed_authorize(api_version='2.0')

    def get_put_call_option_chain(self, instrument_key, expiry_date):
        if not self.api_client: return None
        options_api = upstox_client.OptionsApi(self.api_client)
        return options_api.get_put_call_option_chain(
            instrument_key=instrument_key,
            expiry_date=expiry_date
        )

    def get_ltp(self, instrument_keys):
        """
        Fetches the last traded price for one or more instrument keys.
        instrument_keys can be a single string or a comma-separated string of keys.
        """
        if not self.api_client: return None
        try:
            api_instance = upstox_client.MarketQuoteV3Api(self.api_client)
            return api_instance.get_ltp(instrument_key=instrument_keys)
        except upstox_client.ApiException as e:
            print(f"[UpstoxClient] API Error in get_ltp: {e.body}")
            return None
