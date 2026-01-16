import upstox_client
from upstox_client.feeder.market_data_streamer_v3 import MarketDataStreamerV3
import json

def test_connection():
    with open('config.json') as f:
        config = json.load(f)
    
    token = config.get('upstox_access_token')
    print(f"Testing with token: {token[:10]}...")
    
    configuration = upstox_client.Configuration()
    configuration.access_token = token
    api_client = upstox_client.ApiClient(configuration)
    
    # Try to get profile to verify token
    user_api = upstox_client.UserApi(api_client)
    try:
        profile = user_api.get_profile('2.0')
        print(f"Token Valid! User: {profile.data.user_name}")
    except Exception as e:
        print(f"Token Invalid or error: {e}")
        return

    # Try simple streamer
    streamer = MarketDataStreamerV3(api_client, ["NSE_INDEX|Nifty 50"], "full")
    
    def on_message(message):
        print("Received Message") # Streamer usually returns dict
        # print(message)
    
    def on_open():
         print("Connection Opened!")
         streamer.disconnect()

    streamer.on("message", on_message)
    streamer.on("open", on_open)
    streamer.connect()
    
if __name__ == "__main__":
    test_connection()
