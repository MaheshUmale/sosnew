import upstox_client
import os
try:
    from engine_config import Config as UpstoxConfig
    UPSTOX_AVAILABLE = True
except ImportError:
    UPSTOX_AVAILABLE = False
    print("[UpstoxClient] engine_config.py not found, Upstox functionality will be disabled.")

class UpstoxClient:
    def __init__(self):
        self.api_client = None
        if UPSTOX_AVAILABLE:
            access_token = os.environ.get('UPSTOX_ACCESS_TOKEN')
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
        interval_unit_map = {
            '1m': ('minutes', '1'),
            '1minute': ('minutes', '1'),
            '30m': ('minutes', '30'),
            '30minute': ('minutes', '30'),
            '1d': ('days', '1'),
            '1day': ('days', '1'),
        }
        interval_unit, interval_val = interval_unit_map.get(interval, ('minute', '1'))
        return history_api.get_historical_candle_data1(
            instrument_key=instrument_key,
            unit=interval_unit,
            interval=interval_val,
            to_date=to_date,
            from_date=from_date
        )

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
