from tvDatafeed import TvDatafeed, Interval
try:
    tv = TvDatafeed()
    df = tv.get_hist(symbol='NIFTY', exchange='NSE', interval=Interval.in_1_minute, n_bars=10)
    print("NIFTY Data from TVDatafeed:")
    print(df)
except Exception as e:
    print(f"TVDatafeed Error: {e}")
