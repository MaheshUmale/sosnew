from data_sourcing.data_manager import DataManager
from SymbolMaster import MASTER
import json

def test_ltp():
    MASTER.initialize()
    dm = DataManager()
    
    symbols = ["NSE_INDEX|Nifty 50", "NSE_INDEX|Nifty Bank", "RELIANCE"]
    
    print("\n" + "="*50)
    print("LTP VERIFICATION TEST")
    print("="*50)
    
    for symbol in symbols:
        print(f"\nFetching LTP for: {symbol}")
        ltp = dm.get_last_traded_price(symbol)
        print(f"Resulting LTP: {ltp}")
        
    print("\n" + "="*50)

if __name__ == "__main__":
    test_ltp()
