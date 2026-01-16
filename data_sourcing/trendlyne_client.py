import requests

class TrendlyneClient:
    def __init__(self):
        self.base_url = "https://smartoptions.trendlyne.com/phoenix/api"

    def get_stock_id_for_symbol(self, symbol):
        # Strip common prefixes
        s = symbol.upper()
        if '|' in s:
            s = s.split('|')[-1]
        
        # Map indices to Trendlyne ticker codes
        if "NIFTY 50" in s or s == "NIFTY":
            s = "NIFTY"
        elif "NIFTY BANK" in s or s == "BANKNIFTY":
            s = "BANKNIFTY"
            
        search_url = f"{self.base_url}/search-contract-stock/"
        params = {'query': s.lower()}
        try:
            response = requests.get(search_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            if data and 'body' in data and 'data' in data['body'] and len(data['body']['data']) > 0:
                for item in data['body']['data']:
                    target_code = item.get('stock_code', '').upper()
                    if target_code == s:
                        return item['stock_id']
                return data['body']['data'][0]['stock_id']
            return None
        except Exception as e:
            print(f"[Trendlyne] Error fetching stock ID for {symbol}: {e}")
            return None

    def get_expiry_dates(self, stock_id):
        expiry_url = f"{self.base_url}/fno/get-expiry-dates/?mtype=options&stock_id={stock_id}"
        try:
            response = requests.get(expiry_url, timeout=5)
            response.raise_for_status()
            return response.json().get('body', {}).get('expiryDates', [])
        except Exception as e:
            print(f"[Trendlyne] Error fetching expiry dates: {e}")
            return []

    def get_live_oi_data(self, stock_id, expiry_date, min_time, max_time):
        url = f"{self.base_url}/live-oi-data/"
        params = {
            'stockId': stock_id,
            'expDateList': expiry_date,
            'minTime': min_time,
            'maxTime': max_time
        }
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"[Trendlyne] Error fetching live OI data: {e}")
            return None
