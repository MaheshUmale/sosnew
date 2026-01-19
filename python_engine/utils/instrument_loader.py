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
            # Map simplified symbol 'NIFTY' to Upstox name 'Nifty 50'
            # NOTE: ExtractInstrumentKeys.py uses 'name' == 'NIFTY' for options, NOT 'Nifty 50'
            # search_name = "Nifty 50" if symbol == "NIFTY" else "Nifty Bank" if symbol == "BANKNIFTY" else symbol
            
            spot = spot_prices.get(symbol)

            # --- 1. Current Month Future ---
            # Future names are typically "NIFTY" or "BANKNIFTY" in the JSON, NOT "Nifty 50"
            # We need to check both or assume standard abbreviations for Futures vs Indices
            # Based on DB dump: "NIFTY FUT..." comes from name="NIFTY" (likely) or just matched on trading symbol.
            # Let's try matching name against the input symbol first for Futures, as they often match "NIFTY" / "BANKNIFTY"
            
            fut_df = df[(df['name'] == symbol) & (df['instrument_type'] == 'FUT')].sort_values(by='expiry')
            
            try:
                current_fut_key = fut_df.iloc[0]['instrument_key']
            except IndexError:
                print(f"Warning: No future found for {symbol}. Skipping.")
                continue

            # --- 2. Nearest Expiry Options ---
            # Options for Nifty are under 'Nifty 50'
            opt_df = df[(df['name'] == symbol) & (df['instrument_type'].isin(['CE', 'PE']))].copy()
            
            if opt_df.empty:
                print(f"[InstrumentLoader] ERROR: No options found for {search_name}. DF Shape: {df.shape}")
                print(f"[InstrumentLoader] Unique Names in DF: {df['name'].unique()[:20]}")
                continue

            # Ensure expiry is in datetime format for accurate sorting
            opt_df['expiry'] = pd.to_datetime(opt_df['expiry'], origin='unix', unit='ms')
            nearest_expiry = opt_df['expiry'].min()
            near_opt_df = opt_df[opt_df['expiry'] == nearest_expiry]

            # --- 3. Identify the 11 Strikes (5 OTM, 1 ATM, 5 ITM) ---
            unique_strikes = sorted(near_opt_df['strike_price'].unique())

            # Find ATM strike
            if spot is None or spot <= 0:
                # If spot is unknown, pick the middle strike as a placeholder
                atm_index = len(unique_strikes) // 2
                atm_strike = unique_strikes[atm_index]
            else:
                atm_strike = min(unique_strikes, key=lambda x: abs(x - spot))
                atm_index = unique_strikes.index(atm_strike)

            # Slice range: Index - 5 to Index + 5 (Total 11 strikes)
            start_idx = max(0, atm_index - 5)
            end_idx = min(len(unique_strikes), atm_index + 6)
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
