from SymbolMaster import MASTER
import pandas as pd

MASTER.initialize()

print("NIFTY key:", MASTER.get_upstox_key("NIFTY"))
print("BANKNIFTY key:", MASTER.get_upstox_key("BANKNIFTY"))
print("Nifty 50 key:", MASTER.get_upstox_key("Nifty 50"))
print("Nifty Bank key:", MASTER.get_upstox_key("Nifty Bank"))

# Let's see some entries
count = 0
for k, v in MASTER._mappings.items():
    if "NIFTY" in k or "BANK" in k:
        print(f"{k}: {v}")
        count += 1
        if count > 20:
            break
