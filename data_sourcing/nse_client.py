import requests
import time

class NSEClient:
    def __init__(self):
        self.base_url = "https://www.nseindia.com"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "www.nseindia.com",
            "Connection": "keep-alive"
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        self._init_session()

    def _init_session(self):
        if not self.session.cookies:
            try:
                # First hit homepage
                self.session.get(self.base_url, timeout=15)
                # Then hit a subpage to ensure cookies are fully set
                self.session.get(f"{self.base_url}/market-data/live-equity-market", timeout=15)
            except Exception as e:
                print(f"[NSE] Failed to initialize session: {e}")

    def _make_get_request(self, url, params=None):
        time.sleep(1.0) # Be more conservative with NSE
        try:
            response = self.session.get(url, params=params, timeout=15)
            if response.status_code == 401 or response.status_code == 403:
                print(f"[NSE] Session expired or blocked. Re-initializing...")
                self.session.cookies.clear()
                self._init_session()
                response = self.session.get(url, params=params, timeout=15)
            
            response.raise_for_status()
            try:
                return response.json()
            except (ValueError, requests.exceptions.JSONDecodeError):
                # Only print warning if it's not a common block page
                if "<title>Access Denied</title>" not in response.text:
                    print(f"[NSE] Failed to decode JSON from {url}. Response started with: {response.text[:100]}")
                return None
        except requests.exceptions.HTTPError as e:
            print(f"[NSE] HTTP error: {e.response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"[NSE] Request failed: {e}")
        return None

    def get_option_chain(self, symbol, indices=True):
        instrument_type = "Indices" if indices else "Equities"
        url = f"{self.base_url}/api/option-chain-v3"
        params = {"type": instrument_type, "symbol": symbol}
        headers = self.headers.copy()
        headers["Referer"] = f"{self.base_url}/get-quotes/derivatives?symbol={symbol}"
        self.session.headers.update(headers)
        return self._make_get_request(url, params=params)

    def get_market_breadth(self):
        url = f"{self.base_url}/api/live-analysis-advance"
        headers = self.headers.copy()
        headers["Referer"] = f"{self.base_url}/market-data/live-equity-market"
        self.session.headers.update(headers)
        return self._make_get_request(url)

    def get_holiday_list(self):
        """Returns a hardcoded list of 2026 NSE holidays as per the provided dataset."""
        return [
            "2026-01-26", # Republic Day
            "2026-03-03", # Holi
            "2026-03-26", # Shri Ram Navami
            "2026-03-31", # Shri Mahavir Jayanti
            "2026-04-03", # Good Friday
            "2026-04-14", # Dr. Baba Saheb Ambedkar Jayanti
            "2026-05-01", # Maharashtra Day
            "2026-05-28", # Bakri Id
            "2026-06-26", # Muharram
            "2026-09-14", # Ganesh Chaturthi
            "2026-10-02", # Mahatma Gandhi Jayanti
            "2026-10-20", # Dussehra
            "2026-11-10", # Diwali-Balipratipada
            "2026-11-24", # Prakash Gurpurb Sri Guru Nanak Dev
            "2026-12-25"  # Christmas
        ]

    def get_indices(self):
        """
        Fetches the current data for all NSE indices.
        URL: https://www.nseindia.com/api/allIndices
        """
        url = f"{self.base_url}/api/allIndices"
        headers = self.headers.copy()
        headers["Referer"] = f"{self.base_url}/market-data/live-equity-market"
        self.session.headers.update(headers)
        return self._make_get_request(url)
