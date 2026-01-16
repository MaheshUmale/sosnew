import requests
import json
import backfill_trendlyne

symbol = "NIFTY"
stock_id = backfill_trendlyne.get_stock_id_for_symbol(symbol)
expiry_url = f"https://smartoptions.trendlyne.com/phoenix/api/fno/get-expiry-dates/?mtype=options&stock_id={stock_id}"
resp = requests.get(expiry_url, timeout=10)
expiry_list = resp.json().get('body', {}).get('expiryDates', [])
nearest_expiry = expiry_list[0]

url = f"https://smartoptions.trendlyne.com/phoenix/api/live-oi-data/"
params = {
    'stockId': stock_id,
    'expDateList': nearest_expiry,
    'minTime': "09:15",
    'maxTime': "10:00" # Sample
}

response = requests.get(url, params=params, timeout=10)
data = response.json()
oi_data = data['body']['oiData']

# Print keys of the first strike
first_strike = list(oi_data.keys())[0]
print("Keys:", sorted(list(oi_data[first_strike].keys())))

