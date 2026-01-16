from data_sourcing.data_manager import DataManager
from SymbolMaster import MASTER as SymbolMaster

def test_live_resolution():
    print("Initializing SymbolMaster...")
    SymbolMaster.initialize()
    
    dm = DataManager()
    
    # Mocking what load_and_cache_fno_instruments does
    print("Loading FNO Instruments...")
    try:
        fno_map = dm.load_and_cache_fno_instruments()
        print(f"Loaded FNO Map Keys: {list(fno_map.keys())}")
    except Exception as e:
        print(f"Error loading FNO instruments: {e}")
        return

    for symbol in ["NIFTY", "BANKNIFTY"]:
        print(f"\nTesting {symbol} ATM Resolution (LIVE MODE):")
        # Need to simulate spot price availability if get_last_traded_price relies on cache/API
        # But get_last_traded_price should fetch from API in live mode.
        
        try:
            ce_key, ce_symbol = dm.get_atm_option_details(symbol, "BUY")
            pe_key, pe_symbol = dm.get_atm_option_details(symbol, "SELL")
            
            if ce_key:
                print(f"  CE: {ce_symbol} ({ce_key})")
            else:
                print(f"  CE: FAILED (None)")
                
            if pe_key:
                print(f"  PE: {pe_symbol} ({pe_key})")
            else:
                print(f"  PE: FAILED (None)")

        except Exception as e:
             print(f"  Error resolving {symbol}: {e}")

if __name__ == "__main__":
    test_live_resolution()
