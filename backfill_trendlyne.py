"""
Backfill historical option chain data from Trendlyne SmartOptions API.
This populates a local SQLite database with 1-minute interval historical data.
"""
import requests
import time
import sqlite3
import os
import json
import argparse
from datetime import datetime, timedelta, date


from SymbolMaster import MASTER as SymbolMaster

# Upstox SDK
try:
    import upstox_client
    from upstox_client.rest import ApiException
    import config
    UPSTOX_AVAILABLE = True
except ImportError:
    UPSTOX_AVAILABLE = False
    print("[WARN] Upstox SDK not found. Option Chain will rely on Trendlyne only.")

# ==========================================================================
# 1. DATABASE LAYER (SQLite)
# ==========================================================================
class OptionDatabase:
    def __init__(self, db_path="sos_master_data.db"):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        """Establishes a connection and enables WAL mode."""
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn

    def _init_db(self):
        conn = self._get_connection()
        cursor = conn.cursor()
        # This is the unified table for option chain data from all sources
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS option_chain_data (
                symbol TEXT,
                timestamp DATETIME,
                strike REAL,
                expiry TEXT,
                call_oi INTEGER,
                put_oi INTEGER,
                call_oi_chg INTEGER,
                put_oi_chg INTEGER,
                call_instrument_key TEXT,
                put_instrument_key TEXT,
                PRIMARY KEY (symbol, timestamp, strike)
            )
        ''')
        conn.commit()
        conn.close()

    def save_snapshot(self, symbol, trading_date, timestamp, expiry, aggregates, details):
        conn = self._get_connection()
        cursor = conn.cursor()

        # Combine date and time to create a full ISO timestamp for the database
        datetime_str = f"{trading_date} {timestamp}"

        records_to_insert = []
        for strike, d in details.items():
            record = (
                symbol,
                datetime_str,
                float(strike),
                expiry,
                d['call_oi'],
                d['put_oi'],
                d['call_oi_chg'],
                d['put_oi_chg']
            )
            records_to_insert.append(record)

        try:
            cursor.executemany("""
                INSERT OR REPLACE INTO option_chain_data
                (symbol, timestamp, strike, expiry, call_oi, put_oi, call_oi_chg, put_oi_chg)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, records_to_insert)
            conn.commit()
        except Exception as e:
            print(f"[DB ERROR] {e}")
            conn.rollback()
        finally:
            conn.close()

# Keep a cache to avoid repeated API calls
STOCK_ID_CACHE = {}
EXPIRY_CACHE = {}  # Cache for expiry dates
DB = OptionDatabase()

def get_stock_id_for_symbol(symbol):
    """Automatically lookup Trendlyne stock ID for a given symbol"""
    if symbol in STOCK_ID_CACHE:
        return STOCK_ID_CACHE[symbol]

    search_url = "https://smartoptions.trendlyne.com/phoenix/api/search-contract-stock/"
    params = {'query': symbol.lower()}

    try:
        response = requests.get(search_url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data and 'body' in data and 'data' in data['body'] and len(data['body']['data']) > 0:
            # Match strictly or take first
            for item in data['body']['data']:
                if item.get('stock_code', '').upper() == symbol.upper():
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

def backfill_from_trendlyne(symbol, stock_id, expiry_date_str, timestamp_snapshot, trading_date_override=None):
    """Fetch and save historical OI data from Trendlyne for a specific timestamp snapshot"""

    url = f"https://smartoptions.trendlyne.com/phoenix/api/live-oi-data/"
    params = {
        'stockId': stock_id,
        'expDateList': expiry_date_str,
        'minTime': "09:15",
        'maxTime': timestamp_snapshot
    }

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

        total_call_oi = 0
        total_put_oi = 0
        details = {}

        for strike_str, strike_data in oi_data.items():
            c_oi = int(strike_data.get('callOi', 0))
            p_oi = int(strike_data.get('putOi', 0))
            total_call_oi += c_oi
            total_put_oi += p_oi

            details[strike_str] = {
                'call_oi': c_oi,
                'put_oi': p_oi,
                'call_oi_chg': int(strike_data.get('callOiChange', 0)),
                'put_oi_chg': int(strike_data.get('putOiChange', 0))
            }

        pcr = round(total_put_oi / total_call_oi, 2) if total_call_oi > 0 else 1.0

        aggregates = {
            'call_oi': total_call_oi,
            'put_oi': total_put_oi,
            'pcr': pcr
        }

        DB.save_snapshot(symbol, trading_date, timestamp_snapshot, expiry, aggregates, details)
        return True

    except Exception as e:
        print(f"[ERROR] Fetch {symbol} @ {timestamp_snapshot}: {e}")
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
    if not symbols_list:
        symbols_list = ["NIFTY", "BANKNIFTY", "RELIANCE", "SBIN", "HDFCBANK"]

    print("=" * 60)
    if full_run:
        print("STARTING TRENDLYNE BACKFILL (FULL DAY)")
    else:
        print("STARTING TRENDLYNE BACKFILL (LAST 15 MINS)")
    print("=" * 60)

    now = datetime.now()
    market_open = now.replace(hour=9, minute=15, second=0, microsecond=0)

    start_time_str = "09:15"

    if now < market_open:
        end_time_str = "15:30"
    elif now > now.replace(hour=15, minute=30, second=0, microsecond=0):
        end_time_str = "15:30"
    else:
        end_time_str = now.strftime("%H:%M")

    if not full_run:
        end_dt = datetime.strptime(end_time_str, "%H:%M")
        start_dt = end_dt - timedelta(minutes=15)
        start_time_str = start_dt.strftime("%H:%M")

        # Ensure we don't request data from before market open
        if start_dt.time() < market_open.time():
            start_time_str = "09:15"

    time_slots = generate_time_intervals(start_time=start_time_str, end_time=end_time_str)
    print(f"Time Slots: {len(time_slots)} ({start_time_str} to {end_time_str}) | Symbols: {len(symbols_list)}")

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
            print(f"Syncing {symbol} | Expiry: {nearest_expiry}...")

            success_count = 0
            for ts in time_slots:
                if backfill_from_trendlyne(symbol, stock_id, nearest_expiry, ts, trading_date_override=date_override):
                    success_count += 1

                # Sleep briefly to avoid rate limits
                if success_count % 10 == 0:
                    time.sleep(0.1)

            print(f"[OK] {symbol}: Captured {success_count}/{len(time_slots)} points")
        except Exception as e:
            print(f"[FAIL] {symbol}: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Trendlyne Data Backfill Script")
    parser.add_argument('--full', action='store_true', help='Perform a full-day backfill instead of the default last 15 minutes.')
    parser.add_argument('--symbol', type=str, default="BANKNIFTY", help='Symbol to backfill.')
    parser.add_argument('--date', type=str, help='Date to backfill in YYYY-MM-DD format.')
    args = parser.parse_args()

    target_symbols = [args.symbol]
    run_backfill(target_symbols, full_run=args.full, date_override=args.date)
    print("\n[DB PATH]:", os.path.abspath("sos_master_data.db"))
