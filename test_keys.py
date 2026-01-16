from SymbolMaster import MASTER as SymbolMaster

def test():
    SymbolMaster.initialize()
    symbols = ['NSE_INDEX|Nifty 50', 'NSE_INDEX|Nifty Bank']
    for s in symbols:
        key = SymbolMaster.get_upstox_key(s)
        print(f"Symbol: {s} -> Key: {key}")

if __name__ == "__main__":
    test()
