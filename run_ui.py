import streamlit as st
import pandas as pd
import sqlite3
import json
from datetime import datetime
import time

# Import shared modules
try:
    from python_engine.utils.symbol_master import MASTER as SymbolMaster
    from python_engine.core.trade_logger import TradeLog
    from data_sourcing.data_manager import DataManager
except ImportError:
    # Fallback for different directory structures
    import sys
    import os
    sys.path.append(os.getcwd())
    from python_engine.utils.symbol_master import MASTER as SymbolMaster
    from python_engine.core.trade_logger import TradeLog
    from data_sourcing.data_manager import DataManager

# Configuration
try:
    from python_engine.engine_config import Config
    Config.load('config.json')
    DB_PATH = Config.get('db_path', 'sos_master_data.db')
except:
    DB_PATH = 'sos_master_data.db'

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def load_trades(symbol=None, date=None):
    conn = get_db_connection()
    query = "SELECT * FROM trades"
    conditions = []
    if symbol:
        conditions.append(f"symbol = '{symbol}'")
    if date:
        conditions.append(f"DATE(entry_time) = '{date}'")

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY entry_time DESC"
    df = pd.read_sql(query, conn)
    conn.close()
    return df

def load_candles(symbol, date):
    conn = get_db_connection()
    query = f"SELECT * FROM historical_candles WHERE symbol = '{symbol}' AND DATE(timestamp) = '{date}' ORDER BY timestamp"
    df = pd.read_sql(query, conn)
    conn.close()
    return df

@st.cache_resource
def get_data_manager():
    return DataManager()

def render_chart(candles, trades, title, div_id, height=400):
    # Convert candles to JSON for the JS library
    candle_data = []
    for _, row in candles.iterrows():
        candle_data.append({
            'time': int(pd.to_datetime(row['timestamp']).timestamp()),
            'open': row['open'],
            'high': row['high'],
            'low': row['low'],
            'close': row['close'],
        })

    markers = []
    for _, trade in trades.iterrows():
        # Only add markers if the symbol matches
        if trade['symbol'] == candles['symbol'].iloc[0] or trade['instrument_key'] == candles['symbol'].iloc[0]:
            markers.append({
                'time': int(pd.to_datetime(trade['entry_time']).timestamp()),
                'position': 'belowBar',
                'color': '#2196F3',
                'shape': 'arrowUp',
                'text': 'Entry'
            })
            if trade['exit_time']:
                markers.append({
                    'time': int(pd.to_datetime(trade['exit_time']).timestamp()),
                    'position': 'aboveBar',
                    'color': '#e91e63',
                    'shape': 'arrowDown',
                    'text': f"Exit ({trade['exit_price']})"
                })

    html_template = f"""
    <div id="{div_id}" style="height: {height}px; width: 100%;"></div>
    <script src="https://unpkg.com/lightweight-charts/dist/lightweight-charts.standalone.production.js"></script>
    <script>
        (function() {{
            const chart = LightweightCharts.createChart(document.getElementById('{div_id}'), {{
                width: document.getElementById('{div_id}').clientWidth,
                height: {height},
                layout: {{
                    backgroundColor: '#131722',
                    textColor: '#d1d4dc',
                }},
                grid: {{
                    vertLines: {{ color: '#2B2B43' }},
                    horzLines: {{ color: '#2B2B43' }},
                }},
                timeScale: {{
                    timeVisible: true,
                    secondsVisible: false,
                }},
            }});

            const candleSeries = chart.addCandlestickSeries({{
                upColor: '#26a69a', downColor: '#ef5350', borderVisible: false,
                wickUpColor: '#26a69a', wickDownColor: '#ef5350',
            }});

            const data = {json.dumps(candle_data)};
            candleSeries.setData(data);

            const markers = {json.dumps(markers)};
            candleSeries.setMarkers(markers);

            window.addEventListener('resize', () => {{
                chart.resize(document.getElementById('{div_id}').clientWidth, {height});
            }});
        }})();
    </script>
    """
    return html_template

# Streamlit UI
st.set_page_config(layout="wide", page_title="SOS Scalping Dashboard")

st.title("🚀 SOS Scalping Engine - Live Dashboard")

# Sidebar
st.sidebar.header("Settings")
selected_symbol = st.sidebar.selectbox("Symbol", ["NIFTY", "BANKNIFTY"])
selected_date = st.sidebar.date_input("Date", datetime.strptime("2026-01-16", "%Y-%m-%d").date())
live_mode = st.sidebar.toggle("Live Mode (Auto-refresh)", value=False)

# Re-init SymbolMaster and DataManager
SymbolMaster.initialize()
dm = get_data_manager()

if live_mode:
    st.sidebar.info("Refreshing every 5 seconds...")
    time.sleep(5)
    st.rerun()

# Data Loading
db_symbol = SymbolMaster.get_upstox_key(selected_symbol)
index_candles = load_candles(db_symbol, selected_date)
trades_df = load_trades(db_symbol, selected_date)

@st.cache_data(ttl=60)
def resolve_atm_options(symbol, date):
    # Get last price for that date
    conn = get_db_connection()
    canonical = SymbolMaster.get_upstox_key(symbol)
    query = f"SELECT close FROM historical_candles WHERE symbol = '{canonical}' AND DATE(timestamp) = '{date}' ORDER BY timestamp DESC LIMIT 1"
    df = pd.read_sql(query, conn)
    conn.close()

    if df.empty:
        return None, None

    spot = df.iloc[0]['close']

    # Use DataManager to find ATM
    try:
        dm.load_and_cache_fno_instruments()
        ce_key, ce_name = dm.get_atm_option_details(symbol, 'BUY', spot)
        pe_key, pe_name = dm.get_atm_option_details(symbol, 'SELL', spot)
        return (ce_key, ce_name), (pe_key, pe_name)
    except Exception as e:
        st.error(f"Error resolving ATM options: {e}")
        return None, None

# Resolve ATM Options
atm_ce, atm_pe = resolve_atm_options(selected_symbol, selected_date)

# --- Layout ---

# Row 1: Index Chart
st.write(f"### {selected_symbol} Index")
if not index_candles.empty:
    st.components.v1.html(render_chart(index_candles, trades_df, f"{selected_symbol} Index", "index_chart", height=400), height=420)
else:
    st.warning(f"No index candles found for {selected_symbol} on {selected_date}")

# Row 2: ATM Options side-by-side
col_ce, col_pe = st.columns(2)

with col_ce:
    st.write("### ATM CE Chart")
    if atm_ce:
        ce_key, ce_name = atm_ce
        ce_candles = load_candles(ce_key, selected_date)
        if not ce_candles.empty:
            st.components.v1.html(render_chart(ce_candles, trades_df, ce_name, "ce_chart", height=300), height=320)
        else:
            st.info(f"No candles found for CE: {ce_name}")
    else:
        st.info("ATM CE not resolved.")

with col_pe:
    st.write("### ATM PE Chart")
    if atm_pe:
        pe_key, pe_name = atm_pe
        pe_candles = load_candles(pe_key, selected_date)
        if not pe_candles.empty:
            st.components.v1.html(render_chart(pe_candles, trades_df, pe_name, "pe_chart", height=300), height=320)
        else:
            st.info(f"No candles found for PE: {pe_name}")
    else:
        st.info("ATM PE not resolved.")

# Row 3: Trades (if any)
st.divider()
if not trades_df.empty:
    st.subheader(f"Trades ({len(trades_df)})")

    # Selection for specific trade visualization
    selected_trade_idx = st.selectbox("Visualize Specific Trade", trades_df.index,
                                     format_func=lambda x: f"[{trades_df.loc[x, 'pattern_id']}] {trades_df.loc[x, 'entry_time']} | {trades_df.loc[x, 'instrument_key']} @ {trades_df.loc[x, 'entry_price']}")

    selected_trade = trades_df.loc[selected_trade_idx]

    t_col1, t_col2 = st.columns([1, 2])
    with t_col1:
        st.write("#### Details")
        st.json(selected_trade.to_dict())

    with t_col2:
        st.write(f"#### Trade Chart: {selected_trade['instrument_key']}")
        opt_candles = load_candles(selected_trade['instrument_key'], selected_date)
        if not opt_candles.empty:
            st.components.v1.html(render_chart(opt_candles, trades_df, selected_trade['instrument_key'], "trade_opt_chart", height=300), height=320)
        else:
            st.warning("No candles for this trade's option.")
else:
    st.info(f"No trades recorded for {selected_symbol} on {selected_date}")
