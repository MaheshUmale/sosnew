"""
Backfill historical option chain data from Trendlyne SmartOptions API and Index Volume from TVDatafeed.
This populates a local SQLite database (sos_master_data.db) with 1-minute interval historical data.
"""
import requests
import time
import os
import argparse
from datetime import datetime, timedelta, date
import pandas as pd

from python_engine.utils.symbol_master import MASTER as SymbolMaster
from data_sourcing.database_manager import DatabaseManager

# Try importing TVDatafeed
try:
    from tvDatafeed import TvDatafeed, Interval
    TV_AVAILABLE = True
except ImportError:
    TV_AVAILABLE = False
    print("[WARN] tvDatafeed not found. Index Volume backfill will be skipped.")

# Keep a cache to avoid repeated API calls
STOCK_ID_CACHE = {}

def get_stock_id_for_symbol(symbol):
    """Automatically lookup Trendlyne stock ID for a given symbol"""
    if symbol in STOCK_ID_CACHE:
        return STOCK_ID_CACHE[symbol]

    # CLEAN SYMBOL for API call
    clean_symbol = symbol.split('|')[-1] if '|' in symbol else symbol
    if clean_symbol == "NIFTY" and "BANK" not in symbol: clean_symbol = "NIFTY"
    elif "BANK" in clean_symbol: clean_symbol = "BANKNIFTY"

    search_url = "https://smartoptions.trendlyne.com/phoenix/api/search-contract-stock/"
    params = {'query': clean_symbol.lower()}

    try:
        response = requests.get(search_url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data and 'body' in data and 'data' in data['body'] and len(data['body']['data']) > 0:
            # Match strictly or take first
            for item in data['body']['data']:
                if item.get('stock_code', '').upper() == clean_symbol.upper():
                    stock_id = item['stock_id']
                    STOCK_ID_CACHE[symbol] = stock_id
                    return stock_id

            stock_id = data['body']['data'][0]['stock_id']
            STOCK_ID_CACHE[symbol] = stock_id
            return stock_id
        return None
    except Exception as e:
        print(f"[ERROR] Stock Lookup {symbol}: {e}")
        return None

def backfill_from_trendlyne(db_manager, symbol, stock_id, expiry_date_str, timestamp_snapshot, trading_date_override=None):
    """Fetch and save historical OI data from Trendlyne for a specific timestamp snapshot"""

    url = f"https://smartoptions.trendlyne.com/phoenix/api/live-oi-data/"
    params = {
        'stockId': stock_id,
        'expDateList': expiry_date_str,
        'minTime': "09:15",
        'maxTime': timestamp_snapshot
    }
    if trading_date_override:
        params['tradingDate'] = trading_date_override

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data['head']['status'] != '0':
            return False

        body = data['body']
        oi_data = body.get('oiData', {})
        input_data = body.get('inputData', {})

        trading_date = trading_date_override or input_data.get('tradingDate', date.today().strftime("%Y-%m-%d"))
        expiry = input_data.get('expDateList', [expiry_date_str])[0]

        chain = []
        total_call_oi = 0
        total_put_oi = 0

        for strike_str, strike_data in oi_data.items():
            c_oi = int(strike_data.get('callOi', 0))
            p_oi = int(strike_data.get('putOi', 0))
            total_call_oi += c_oi
            total_put_oi += p_oi

            chain.append({
                "strike": float(strike_str),
                "call_oi": c_oi,
                "put_oi": p_oi,
                "call_oi_chg": int(strike_data.get('callOiChange', 0)),
                "put_oi_chg": int(strike_data.get('putOiChange', 0)),
                "call_instrument_key": "", # Trendlyne doesn't give this
                "put_instrument_key": "",
                "expiry": expiry_date_str # CRITICAL: Needed for ATM resolution
            })
        
        if chain:
            df = pd.DataFrame(chain)
            # Add explicit timestamp for accurate historical storage
            # timestamp_snapshot is "HH:MM"
            full_ts = f"{trading_date} {timestamp_snapshot}:00"
            df['timestamp'] = full_ts
            
            # Canonicalize symbol for DB storage
            canonical_symbol = SymbolMaster.get_canonical_ticker(symbol)

            # Store via DatabaseManager
            db_manager.store_option_chain(canonical_symbol, df, date=trading_date)

            # Calculate and Store PCR in market_stats
            current_pcr = round(total_put_oi / total_call_oi, 4) if total_call_oi > 0 else 1.0

            stats_df = pd.DataFrame([{
                'timestamp': full_ts,
                'pcr': current_pcr
            }])
            db_manager.store_market_stats(canonical_symbol, stats_df)

            return True
            
        return False

    except Exception as e:
        print(f"[ERROR] Fetch {symbol} @ {timestamp_snapshot}: {e}")
        return False

def backfill_index_volume_from_tv(db_manager, symbol, trading_date_str):
    """
    Fetches 1-minute historical data (including VOLUME) from TVDatafeed for the specified date
    and stores it in the database.
    """
    if not TV_AVAILABLE:
        return

    # CLEAN SYMBOL for TVDatafeed
    clean_symbol = symbol.split('|')[-1] if '|' in symbol else symbol
    if clean_symbol == "NIFTY" and "BANK" not in symbol: clean_symbol = "NIFTY"
    elif "BANK" in clean_symbol: clean_symbol = "BANKNIFTY"

    print(f"[TVDatafeed] Backfilling volume for {clean_symbol} on {trading_date_str}...")
    try:
        tv = TvDatafeed()
        
        # TV Symbol Mapping
        tv_symbol = clean_symbol
        exchange = "NSE"
        
        # Calculate n_bars (approx coverage for one day is 375 bars)
        target_date = datetime.strptime(trading_date_str, "%Y-%m-%d")
        days_diff = (datetime.now() - target_date).days + 2
        n_bars = days_diff * 375 + 100 # Buffer
        
        print(f"[TVDatafeed] Requesting {n_bars} bars to cover {trading_date_str}...")
        
        # Note: rongard version might use get_hist or get_historical_data
        # We try both if needed, or stick to what user suggested if possible.
        try:
            df = tv.get_hist(symbol=tv_symbol, exchange=exchange, interval=Interval.in_1_minute, n_bars=n_bars)
        except AttributeError:
            df = tv.get_historical_data(tv_symbol, exchange, Interval.in_1_minute, n_bars=n_bars)
        
        if df is not None and not df.empty:
            # Clean and filter for the specific date
            df.reset_index(inplace=True)
            df.rename(columns={'datetime': 'timestamp'}, inplace=True)
            
            # Filter
            df['date_str'] = df['timestamp'].dt.strftime('%Y-%m-%d')
            day_df = df[df['date_str'] == trading_date_str].copy()
            
            if not day_df.empty:
                # Store
                print(f"[TVDatafeed] Found {len(day_df)} bars with volume for {trading_date_str}. Storing...")
                canonical_symbol = SymbolMaster.get_canonical_ticker(symbol)
                db_manager.store_historical_candles(canonical_symbol, exchange, '1m', day_df)
                return True
            else:
                print(f"[TVDatafeed] No data found for date {trading_date_str} in the fetched range.")
        else:
            print("[TVDatafeed] No data returned from API.")

    except Exception as e:
        print(f"[TVDatafeed] Error: {e}")
        
    return False

def generate_time_intervals(start_time="09:15", end_time="15:30", interval_minutes=1):
    """Generate time strings in HH:MM format with 1-minute default"""
    start = datetime.strptime(start_time, "%H:%M")
    end = datetime.strptime(end_time, "%H:%M")
    current = start
    times = []
    while current <= end:
        times.append(current.strftime("%H:%M"))
        current += timedelta(minutes=interval_minutes)
    return times

def run_backfill(symbols_list=None, full_run=False, date_override=None):
    db_manager = DatabaseManager()
    db_manager.initialize_database()

    if not symbols_list:
        symbols_list = ["NSE|INDEX|NIFTY", "NSE|INDEX|BANKNIFTY"]

    print("=" * 60)
    print(f"STARTING BACKFILL (Trendlyne Options + TV Volume) | Date: {date_override or 'Today'}")
    print("=" * 60)

    now = datetime.now()
    trading_date_str = date_override if date_override else now.strftime("%Y-%m-%d")

    # 1. Backfill Volume from TVDatafeed (Indices only)
    for symbol in symbols_list:
        if "NIFTY" in symbol or "BANKNIFTY" in symbol:
             backfill_index_volume_from_tv(db_manager, symbol, trading_date_str)

    # 2. Backfill Options from Trendlyne
    start_time_str = "09:15"
    end_time_str = "15:30"
    
    if not full_run and not date_override:
        # Default to last 15 mins if running for today without full flag
        end_dt = now
        start_dt = end_dt - timedelta(minutes=15)
        start_time_str = start_dt.strftime("%H:%M")
        end_time_str = end_dt.strftime("%H:%M")
    
    time_slots = generate_time_intervals(start_time=start_time_str, end_time=end_time_str)
    
    for symbol in symbols_list:
        stock_id = get_stock_id_for_symbol(symbol)
        if not stock_id:
            print(f"[SKIP] No Stock ID for {symbol}")
            continue

        try:
            # Fetch Expiry
            expiry_url = f"https://smartoptions.trendlyne.com/phoenix/api/fno/get-expiry-dates/?mtype=options&stock_id={stock_id}"
            resp = requests.get(expiry_url, timeout=10)
            expiry_list = resp.json().get('body', {}).get('expiryDates', [])
            if not expiry_list:
                print(f"[SKIP] No Expiry for {symbol}")
                continue

            nearest_expiry = expiry_list[0]
            print(f"Syncing Options {symbol} | Expiry: {nearest_expiry}...")

            success_count = 0
            for ts in time_slots:
                if backfill_from_trendlyne(db_manager, symbol, stock_id, nearest_expiry, ts, trading_date_override=trading_date_str):
                    success_count += 1
                if success_count % 10 == 0:
                    time.sleep(0.1)

            print(f"[OK] {symbol} Options: Captured {success_count}/{len(time_slots)} snapshots")
        except Exception as e:
            print(f"[FAIL] {symbol}: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Data Backfill Script")
    parser.add_argument('--full', action='store_true', help='Perform a full-day backfill.')
    parser.add_argument('--symbol', type=str, help='Symbol to backfill.')
    parser.add_argument('--date', type=str, help='Date to backfill in YYYY-MM-DD format.')
    args = parser.parse_args()

    target_symbols = [args.symbol] if args.symbol else ["NSE|INDEX|NIFTY", "NSE|INDEX|BANKNIFTY"]
    run_backfill(target_symbols, full_run=args.full, date_override=args.date)
    print("\n[DB PATH]:", os.path.abspath("sos_master_data.db"))
