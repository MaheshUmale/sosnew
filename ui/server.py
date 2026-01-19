import os
import pandas as pd
from datetime import datetime
from fastapi import FastAPI, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from python_engine.utils.symbol_master import MASTER as SymbolMaster
from data_sourcing.data_manager import DataManager
from data_sourcing.database_manager import DatabaseManager

app = FastAPI()
templates = Jinja2Templates(directory="ui/templates")

# Initialize shared resources
SymbolMaster.initialize()
dm = DataManager()
DB_PATH = 'sos_master_data.db'

@app.get("/", response_class=HTMLResponse)
async def get_dashboard(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/candles")
async def get_candles(
    symbol: str,
    date: str,
    mode: str = 'backtest'
):
    try:
        # Resolve canonical key if needed
        canonical = SymbolMaster.get_upstox_key(symbol) or symbol

        df = dm.get_historical_candles(
            canonical,
            from_date=date,
            to_date=date,
            mode=mode,
            n_bars=1000
        )

        if df is None or df.empty:
            return JSONResponse(content={"data": []})

        # Convert to records for JS
        df = df.copy()
        df['time'] = pd.to_datetime(df['timestamp']).view('int64') // 10**9
        # Lightweight charts expects time as unix timestamp (int) or string

        records = []
        for _, row in df.iterrows():
            records.append({
                "time": int(row['time']),
                "open": float(row['open']),
                "high": float(row['high']),
                "low": float(row['low']),
                "close": float(row['close']),
                "volume": float(row.get('volume', 0))
            })

        return JSONResponse(content={"data": records, "symbol": canonical})
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.get("/api/atm_options")
async def get_atm_options(symbol: str, date: str):
    try:
        canonical = SymbolMaster.get_upstox_key(symbol)
        db_manager = DatabaseManager(DB_PATH)

        query = f"SELECT close FROM historical_candles WHERE symbol = '{canonical}' AND DATE(timestamp) = '{date}' ORDER BY timestamp DESC LIMIT 1"
        with db_manager as db:
            df = pd.read_sql(query, db.conn)

        if df.empty:
            # Try to fetch one candle if today
            if date == datetime.now().strftime('%Y-%m-%d'):
                temp_df = dm.get_historical_candles(canonical, from_date=date, to_date=date, mode='live', n_bars=1)
                if temp_df is not None and not temp_df.empty:
                    spot = temp_df.iloc[-1]['close']
                else:
                    return JSONResponse(content={"error": "No spot price found"}, status_code=404)
            else:
                return JSONResponse(content={"error": "No spot price found"}, status_code=404)
        else:
            spot = df.iloc[0]['close']

        dm.load_and_cache_fno_instruments(target_date=date)
        ce_key, ce_name = dm.get_atm_option_details(symbol, 'BUY', spot, target_date=date)
        pe_key, pe_name = dm.get_atm_option_details(symbol, 'SELL', spot, target_date=date)

        return JSONResponse(content={
            "ce": {"key": ce_key, "name": ce_name},
            "pe": {"key": pe_key, "name": pe_name},
            "spot": float(spot)
        })
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.get("/api/trades")
async def get_trades(symbol: str = None, date: str = None):
    db_manager = DatabaseManager(DB_PATH)
    query = "SELECT * FROM trades"
    conditions = []
    if symbol:
        canonical = SymbolMaster.get_upstox_key(symbol) or symbol
        conditions.append(f"(symbol = '{canonical}' OR instrument_key = '{canonical}')")
    if date:
        conditions.append(f"DATE(entry_time) = '{date}'")

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY entry_time DESC"

    with db_manager as db:
        df = pd.read_sql(query, db.conn)

    # Convert timestamps for JSON and handle NaN
    trades = []

    for _, row in df.iterrows():
        trade = {}
        for k, v in row.to_dict().items():
            if pd.isna(v):
                trade[k] = None
            elif isinstance(v, (pd.Timestamp, datetime)):
                trade[k] = str(v)
            else:
                trade[k] = v

        trade['entry_time_unix'] = int(pd.to_datetime(row['entry_time']).timestamp())
        if row['exit_time'] and not pd.isna(row['exit_time']):
            trade['exit_time_unix'] = int(pd.to_datetime(row['exit_time']).timestamp())
        else:
            trade['exit_time_unix'] = None
        trades.append(trade)

    return JSONResponse(content={"trades": trades})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
