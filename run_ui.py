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

def load_trades(symbol=None, date=None):
    from data_sourcing.database_manager import DatabaseManager
    db_manager = DatabaseManager(DB_PATH)
    query = "SELECT * FROM trades"
    conditions = []
    if symbol:
        conditions.append(f"symbol = '{symbol}'")
    if date:
        conditions.append(f"DATE(entry_time) = '{date}'")

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY entry_time DESC"
    with db_manager as db:
        df = pd.read_sql(query, db.conn)
    return df

def load_candles(symbol, date, mode='backtest'):
    """Loads candles from DB with optional API fallback if mode='live'."""
    # Convert date to string for DataManager
    date_str = date.strftime('%Y-%m-%d') if not isinstance(date, str) else date

    # We use DataManager for consistent canonicalization and API fallback
    try:
        from data_sourcing.data_manager import DataManager
        # Reuse cached DataManager if available in session state, else create new
        if 'dm' not in st.session_state:
            st.session_state.dm = DataManager()

        # DataManager.get_historical_candles handles DB query + remote fallback
        df = st.session_state.dm.get_historical_candles(
            symbol,
            from_date=date_str,
            to_date=date_str,
            mode=mode,
            n_bars=1000 # Fetch more bars for a full day view
        )
        return df if df is not None else pd.DataFrame()
    except Exception as e:
        st.error(f"Error loading candles for {symbol}: {e}")
        return pd.DataFrame()

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
    if not trades.empty:
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
    <div id="{div_id}_wrapper" style="height: {height}px; width: 100%; background-color: #131722; position: relative;">
        <div id="{div_id}" style="height: 100%; width: 100%;"></div>
        <div id="{div_id}_loading" style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); color: #555; font-family: sans-serif;">
            {title} - Initializing Chart...
        </div>
    </div>
    <script src="https://unpkg.com/lightweight-charts/dist/lightweight-charts.standalone.production.js"></script>
    <script>
        (function() {{
            function initChart() {{
                const container = document.getElementById('{div_id}');
                const loading = document.getElementById('{div_id}_loading');

                if (!window.LightweightCharts) {{
                    console.log("Waiting for LightweightCharts...");
                    setTimeout(initChart, 100);
                    return;
                }}

                if (container.clientWidth === 0) {{
                    console.log("Waiting for container dimensions...");
                    setTimeout(initChart, 100);
                    return;
                }}

                if (loading) loading.style.display = 'none';

                const chart = LightweightCharts.createChart(container, {{
                    width: container.clientWidth,
                    height: {height},
                    layout: {{
                        background: {{ type: 'solid', color: '#131722' }},
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
                if (data && data.length > 0) {{
                    candleSeries.setData(data);
                }}

                const markers = {json.dumps(markers)};
                if (markers && markers.length > 0) {{
                    candleSeries.setMarkers(markers);
                }}

                const resizeObserver = new ResizeObserver(entries => {{
                    if (entries.length === 0 || !entries[0].contentRect) return;
                    const {{ width, height }} = entries[0].contentRect;
                    chart.applyOptions({{ width, height }});
                }});
                resizeObserver.observe(container);
            }}

            if (document.readyState === 'complete') {{
                initChart();
            }} else {{
                window.addEventListener('load', initChart);
            }}
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
selected_date = st.sidebar.date_input("Date", datetime.strptime("2026-01-19", "%Y-%m-%d").date())
live_mode = st.sidebar.toggle("Live Mode (Auto-refresh)", value=True)

# Re-init SymbolMaster and DataManager
with st.spinner("Initializing system..."):
    SymbolMaster.initialize()
    dm = get_data_manager()

# Data Loading
# Use 'live' mode if selected_date is today or live_mode is toggled
fetch_mode = 'live' if live_mode or selected_date == datetime.now().date() else 'backtest'

db_symbol = SymbolMaster.get_upstox_key(selected_symbol)
if not db_symbol:
    st.error(f"Could not resolve key for {selected_symbol}. Check instrument master.")
    st.stop()

with st.spinner(f"Loading candles for {selected_symbol}..."):
    index_candles = load_candles(db_symbol, selected_date, mode=fetch_mode)

trades_df = load_trades(db_symbol, selected_date)

@st.cache_data(ttl=60)
def resolve_atm_options(symbol, date):
    # Get last price for that date
    from data_sourcing.database_manager import DatabaseManager
    db_manager = DatabaseManager(DB_PATH)

    canonical = SymbolMaster.get_upstox_key(symbol)
    query = f"SELECT close FROM historical_candles WHERE symbol = '{canonical}' AND DATE(timestamp) = '{date}' ORDER BY timestamp DESC LIMIT 1"
    with db_manager as db:
        df = pd.read_sql(query, db.conn)

    if df.empty:
        # Try alternate canonical
        alt_canonical = "NSE|INDEX|NIFTY" if symbol == "NIFTY" else "NSE|INDEX|BANKNIFTY"
        query = f"SELECT close FROM historical_candles WHERE symbol = '{alt_canonical}' AND DATE(timestamp) = '{date}' ORDER BY timestamp DESC LIMIT 1"
        with db_manager as db:
            df = pd.read_sql(query, db.conn)

    if df.empty:
        return None, None

    spot = df.iloc[0]['close']

    # Use DataManager to find ATM
    try:
        dm.load_and_cache_fno_instruments(target_date=date)
        ce_key, ce_name = dm.get_atm_option_details(symbol, 'BUY', spot, target_date=date)
        pe_key, pe_name = dm.get_atm_option_details(symbol, 'SELL', spot, target_date=date)
        return (ce_key, ce_name), (pe_key, pe_name)
    except Exception as e:
        st.error(f"Error resolving ATM options: {e}")
        return None, None

# Resolve ATM Options
with st.spinner(f"Resolving ATM options for {selected_symbol}..."):
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
        ce_candles = load_candles(ce_key, selected_date, mode=fetch_mode)
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
        pe_candles = load_candles(pe_key, selected_date, mode=fetch_mode)
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
        opt_candles = load_candles(selected_trade['instrument_key'], selected_date, mode=fetch_mode)
        if not opt_candles.empty:
            st.components.v1.html(render_chart(opt_candles, trades_df, selected_trade['instrument_key'], "trade_opt_chart", height=300), height=320)
        else:
            st.warning("No candles for this trade's option.")
else:
    st.info(f"No trades recorded for {selected_symbol} on {selected_date}")

# Auto-refresh logic (at the end to allow rendering first)
if live_mode:
    time.sleep(5)
    st.rerun()
