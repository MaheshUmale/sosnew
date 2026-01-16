from data_sourcing.data_manager import DataManager
from SymbolMaster import MASTER as SymbolMaster
import datetime
import pandas as pd

def test_resolution():
    print("Initializing SymbolMaster...")
    SymbolMaster.initialize()
    
    dm = DataManager()
    
    # Simulate a timestamp (e.g., today or a known trading day)
    # We use a timestamp corresponding to 2026-01-16 10:00:00
    ts = pd.Timestamp("2026-01-16 10:00:00").timestamp()
    
    spot_price = 25750.0 # Hypothetical Nifty Spot
    side = "BUY" # Calls
    
    print(f"Testing Resolution for NIFTY at {spot_price}, Side: {side}")
    
    key, symbol = dm.get_atm_option_details_for_timestamp("NIFTY", side, spot_price, ts)
    
    if key and symbol:
        print(f"SUCCESS: Resolved to {symbol} (Key: {key})")
    else:
        print("FAILURE: Could not resolve symbol.")

if __name__ == "__main__":
    test_resolution()
