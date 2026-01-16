from SymbolMaster import MASTER
MASTER.initialize()
print(f"RELIANCE Key: {MASTER.get_upstox_key('RELIANCE')}")
print(f"NIFTY Key: {MASTER.get_upstox_key('NIFTY')}")
