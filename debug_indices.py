from SymbolMaster import MASTER
MASTER.initialize()

nifty_key = "NSE_INDEX|Nifty 50"
banknifty_key = "NSE_INDEX|Nifty Bank"

print(f"Key: {nifty_key}, Reverse: {MASTER._reverse_mappings.get(nifty_key)}")
print(f"Key: {banknifty_key}, Reverse: {MASTER._reverse_mappings.get(banknifty_key)}")

print(f"Ticker for {nifty_key}: {MASTER.get_ticker_from_key(nifty_key)}")
print(f"Ticker for {banknifty_key}: {MASTER.get_ticker_from_key(banknifty_key)}")
