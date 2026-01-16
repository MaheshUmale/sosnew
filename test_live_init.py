import asyncio
from python_engine.live_main import LiveTradingEngine
from engine_config import Config
from SymbolMaster import MASTER as SymbolMaster

async def test_init():
    Config.load('config.json')
    SymbolMaster.initialize()
    loop = asyncio.get_event_loop()

    print("Initializing LiveTradingEngine...")
    engine = LiveTradingEngine(loop)

    print(f"Symbols to subscribe: {engine.symbols}")
    from python_engine.live_main import subscribed_instruments
    print(f"Total subscribed instruments: {len(subscribed_instruments)}")

    # Check if NIFTY and BANKNIFTY keys are present
    nifty_key = SymbolMaster.get_upstox_key('NSE|INDEX|NIFTY')
    banknifty_key = SymbolMaster.get_upstox_key('NSE|INDEX|BANKNIFTY')

    print(f"NIFTY key: {nifty_key}")
    print(f"BANKNIFTY key: {banknifty_key}")

    if nifty_key in subscribed_instruments:
        print("✓ NIFTY key in subscription list")
    else:
        print("✗ NIFTY key MISSING from subscription list")

    if banknifty_key in subscribed_instruments:
        print("✓ BANKNIFTY key in subscription list")
    else:
        print("✗ BANKNIFTY key MISSING from subscription list")

    print("\nTesting DataManager fetching...")
    dm = engine.data_manager
    dm.upstox_client.api_client.configuration.access_token = Config.get('upstox_access_token')

    from datetime import datetime, timedelta
    to_date = datetime.now()
    from_date = to_date - timedelta(days=2)

    print(f"Fetching candles for NSE|INDEX|NIFTY from {from_date.date()} to {to_date.date()}...")
    candles = dm.get_historical_candles('NSE|INDEX|NIFTY', from_date=from_date, to_date=to_date)
    if candles is not None:
        print(f"✓ Successfully fetched {len(candles)} candles")
    else:
        print("✗ Failed to fetch candles")

    print("\nTesting Option Chain fetching...")
    chain = dm.get_option_chain('NIFTY')
    if chain:
        print(f"✓ Successfully fetched option chain with {len(chain)} strikes")
    else:
        print("✗ Failed to fetch option chain")

    print("\nTesting PCR...")
    pcr = dm.get_pcr('NIFTY')
    print(f"PCR for NIFTY: {pcr}")

if __name__ == "__main__":
    asyncio.run(test_init())
