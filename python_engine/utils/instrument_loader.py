import pandas as pd
import requests
import gzip
import io

class InstrumentLoader:
    def get_upstox_instruments(self, symbols=["NIFTY", "BANKNIFTY"], spot_prices={"NIFTY": 0, "BANKNIFTY": 0}):
        # 1. Download and Load Instrument Master (NSE_FO for Futures and Options)
        url = "https://assets.upstox.com/market-quote/instruments/exchange/NSE.json.gz"
        response = requests.get(url)
        with gzip.GzipFile(fileobj=io.BytesIO(response.content)) as f:
            df = pd.read_json(f)

        full_mapping = {}

        for symbol in symbols:
            spot = spot_prices.get(symbol)

            # --- 1. Current Month Future ---
            fut_df = df[(df['name'] == symbol) & (df['instrument_type'] == 'FUT')].sort_values(by='expiry')
            try:
                current_fut_key = fut_df.iloc[0]['instrument_key']
            except IndexError:
                print(f"Warning: No future found for {symbol}. Skipping.")
                continue

            # --- 2. Nearest Expiry Options ---
            # Filter for Options for the specific index
            opt_df = df[(df['name'] == symbol) & (df['instrument_type'].isin(['CE', 'PE']))].copy()

            # Ensure expiry is in datetime format for accurate sorting
            opt_df['expiry'] = pd.to_datetime(opt_df['expiry'], origin='unix', unit='ms')
            nearest_expiry = opt_df['expiry'].min()
            near_opt_df = opt_df[opt_df['expiry'] == nearest_expiry]

            # --- 3. Identify the 7 Strikes (3 OTM, 1 ATM, 3 ITM) ---
            unique_strikes = sorted(near_opt_df['strike_price'].unique())

            # Find ATM strike
            atm_strike = min(unique_strikes, key=lambda x: abs(x - spot))
            atm_index = unique_strikes.index(atm_strike)

            # Slice range: Index - 3 to Index + 3 (Total 7 strikes)
            start_idx = max(0, atm_index - 3)
            end_idx = min(len(unique_strikes), atm_index + 4)
            selected_strikes = unique_strikes[start_idx : end_idx]

            # --- 4. Build Result ---
            option_keys = []
            for strike in selected_strikes:
                try:
                    ce_key = near_opt_df[(near_opt_df['strike_price'] == strike) & (near_opt_df['instrument_type'] == 'CE')]['instrument_key'].values[0]
                    ce_trading_symbol = near_opt_df[(near_opt_df['strike_price'] == strike) & (near_opt_df['instrument_type'] == 'CE')]['trading_symbol'].values[0]

                    pe_key = near_opt_df[(near_opt_df['strike_price'] == strike) & (near_opt_df['instrument_type'] == 'PE')]['instrument_key'].values[0]
                    pe_trading_symbol = near_opt_df[(near_opt_df['strike_price'] == strike) & (near_opt_df['instrument_type'] == 'PE')]['trading_symbol'].values[0]
                except IndexError:
                    print(f"Warning: CE or PE key not found for strike {strike} in {symbol}. Skipping.")
                    continue

                option_keys.append({
                    "strike": strike,
                    "ce": ce_key,
                    "ce_trading_symbol" :ce_trading_symbol,
                    "pe": pe_key,
                    "pe_trading_symbol" : pe_trading_symbol
                })

            full_mapping[symbol] = {
                "future": current_fut_key,
                "expiry": nearest_expiry.strftime('%Y-%m-%d'),
                "options": option_keys,
                "all_keys": [current_fut_key] + [opt['ce'] for opt in option_keys] + [opt['pe'] for opt in option_keys]
            }

        return full_mapping
