import re

def upstox_to_tv_option(upstox_symbol):
    """
    Converts an Upstox-style trading symbol to a TradingView-compatible option symbol.

    Example Input: "BANKNIFTY 59500 CE 27 JAN 26" or "BANKNIFTY 27 JAN 26 CE 59500"
    Example Output: "BANKNIFTY260127C59500"
    """
    if not upstox_symbol:
        return upstox_symbol

    parts = upstox_symbol.split()
    if len(parts) < 3:
        return upstox_symbol

    symbol_prefix = parts[0]

    # Check if it's an index first, if so, return the short form
    if symbol_prefix.upper() in ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"]:
        # If it's just the index, return as is (to be handled by index mapping)
        if len(parts) == 1:
            return symbol_prefix.upper()
    else:
        # Not a recognized index prefix for options
        return upstox_symbol

    strike = None
    opt_type = None
    day = None
    month = None
    year = None

    month_map = {
        'JAN': '01', 'FEB': '02', 'MAR': '03', 'APR': '04',
        'MAY': '05', 'JUN': '06', 'JUL': '07', 'AUG': '08',
        'SEP': '09', 'OCT': '10', 'NOV': '11', 'DEC': '12'
    }

    for p in parts:
        p_upper = p.upper()
        if p_upper in ['CE', 'PE']:
            opt_type = 'C' if p_upper == 'CE' else 'P'
        elif p.isdigit() and len(p) >= 3:
            strike = p
        elif p.isdigit() and len(p) <= 2:
            # Usually Day comes before Year or we have context
            if not day:
                day = p.zfill(2)
            else:
                year = p.zfill(2)
        elif p_upper in month_map:
            month = month_map[p_upper]

    # Special case: if Year wasn't filled but we have Day, and Day looks like a year (e.g. 25, 26)
    # This depends on the sequence. In "27 JAN 26", day=27, year=26.
    # In some formats it might be different.

    if symbol_prefix and year and month and day and opt_type and strike:
        # User requested: BANKNIFTY260127C59500
        return f"{symbol_prefix.upper()}{year}{month}{day}{opt_type}{strike}"

    return upstox_symbol

if __name__ == "__main__":
    # Test cases
    print(upstox_to_tv_option("BANKNIFTY 59900 CE 27 JAN 26")) # Expected: BANKNIFTY260127C59900
    print(upstox_to_tv_option("BANKNIFTY 27 JAN 26 CE 59700")) # Expected: BANKNIFTY260127C59700
    print(upstox_to_tv_option("NIFTY 24000 PE 16 JAN 25"))    # Expected: NIFTY250116P24000
