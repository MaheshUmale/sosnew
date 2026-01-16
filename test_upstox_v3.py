import upstox_client
from engine_config import Config
import json

Config.load('config.json')
access_token = Config.get('upstox_access_token')

configuration = upstox_client.Configuration()
configuration.access_token = access_token
api_client = upstox_client.ApiClient(configuration)

history_api = upstox_client.HistoryV3Api(api_client)

try:
    # Test with 'minute'
    res = history_api.get_historical_candle_data1(
        instrument_key='NSE_INDEX|Nifty 50',
        unit='minute',
        interval='1',
        to_date='2025-02-07',
        from_date='2025-02-07'
    )
    print("Success with unit='minute'")
except Exception as e:
    print(f"Failed with unit='minute': {e}")

try:
    # Test with 'minutes'
    res = history_api.get_historical_candle_data1(
        instrument_key='NSE_INDEX|Nifty 50',
        unit='minutes',
        interval='1',
        to_date='2025-02-07',
        from_date='2025-02-07'
    )
    print("Success with unit='minutes'")
except Exception as e:
    print(f"Failed with unit='minutes': {e}")
