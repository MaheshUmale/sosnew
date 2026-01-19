import os
import sys
sys.path.append(os.getcwd())

import streamlit as st

# MUST BE AT TOP
st.set_page_config(layout="wide", page_title="SOS Scalping Dashboard")

import pandas as pd
import json
from datetime import datetime
import time
from lightweight_charts.widgets import StreamlitChart

# Import shared modules
try:
    from python_engine.utils.symbol_master import MASTER as SymbolMaster
    from data_sourcing.data_manager import DataManager
    from data_sourcing.database_manager import DatabaseManager
except ImportError:
    from python_engine.utils.symbol_master import MASTER as SymbolMaster
    from data_sourcing.data_manager import DataManager
    from data_sourcing.database_manager import DatabaseManager

# Configuration
try:
    from python_engine.engine_config import Config
    Config.load('config.json')
    DB_PATH = Config.get('db_path', 'sos_master_data.db')
except:
    DB_PATH = 'sos_master_data.db'

# Initialization with caching to prevent redundant work and thread issues
@st.cache_resource
def get_data_manager():
    return DataManager()

@st.cache_resource
def init_symbol_master():
    try:
        SymbolMaster.initialize()
        return True
    except Exception as e:
        return str(e)

# Initialize system
init_res = init_symbol_master()
if init_res is not True:
    st.error(f"Failed to initialize system: {init_res}")
    st.stop()

dm = get_data_manager()
st.session_state.dm = dm

def load_trades(symbol=None, date=None):
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
    date_str = date.strftime('%Y-%m-%d') if not isinstance(date, str) else date
    try:
        df = st.session_state.dm.get_historical_candles(
            symbol,
            from_date=date_str,
            to_date=date_str,
            mode=mode,
            n_bars=1000
        )
        if df is not None and not df.empty:
            # lightweight-charts requires 'time' column or index
            df = df.copy()
            df['time'] = pd.to_datetime(df['timestamp']).dt.strftime('%Y-%m-%d %H:%M:%S')
            df = df.sort_values('time')
            return df
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Error loading candles for {symbol}: {e}")
        return pd.DataFrame()

def display_chart(df, trades, title, height=400):
    if df.empty:
        st.warning(f'No data to display for {title}')
        return

    # Create the chart
    chart = StreamlitChart(width=None, height=height)

    # Configure Chart (OHLC columns)
    chart_cols = ['time', 'open', 'high', 'low', 'close', 'volume', 'oi']
    chart_df = df[[c for c in chart_cols if c in df.columns]]
    chart.set(chart_df)

    # Add Markers for trades
    if not trades.empty:
        for _, trade in trades.iterrows():
            # Match trade to symbol
            if trade['symbol'] == df['symbol'].iloc[0] or trade['instrument_key'] == df['symbol'].iloc[0]:
                entry_time = pd.to_datetime(trade['entry_time']).strftime('%Y-%m-%d %H:%M:%S')
                chart.marker(time=entry_time, position='belowBar', color='#2196F3', shape='arrowUp', text=f"Entry @ {trade['entry_price']}")
                if trade['exit_time']:
                    exit_time = pd.to_datetime(trade['exit_time']).strftime('%Y-%m-%d %H:%M:%S')
                    chart.marker(time=exit_time, position='aboveBar', color='#e91e63', shape='arrowDown', text=f"Exit @ {trade['exit_price']}")

    chart.load()

# Streamlit UI
st.title("🚀 SOS Scalping Engine - Live Dashboard")

# Sidebar
st.sidebar.header("Settings")
selected_symbol = st.sidebar.selectbox("Symbol", ["NIFTY", "BANKNIFTY"])

# Default to 2026-01-16 for testing
default_date = datetime.strptime("2026-01-16", "%Y-%m-%d").date()
selected_date = st.sidebar.date_input("Date", default_date)
live_mode = st.sidebar.toggle("Live Mode (Auto-refresh)", value=False)

if st.sidebar.button("Force Refresh"):
    st.rerun()

if st.sidebar.button("Clear Cache"):
    st.cache_resource.clear()
    st.rerun()

# Data Loading
fetch_mode = 'live' if live_mode or selected_date == datetime.now().date() else 'backtest'

db_symbol = SymbolMaster.get_upstox_key(selected_symbol)
if not db_symbol:
    st.error(f"Could not resolve key for {selected_symbol}. Check instrument master.")
    st.stop()

with st.spinner(f"Loading candles for {selected_symbol}..."):
    index_candles = load_candles(db_symbol, selected_date, mode=fetch_mode)

trades_df = load_trades(db_symbol, selected_date)

def resolve_atm_options(symbol, date):
    # Use DataManager to find ATM
    try:
        # Get last price for that date
        db_manager = DatabaseManager(DB_PATH)
        canonical = SymbolMaster.get_upstox_key(symbol)
        date_str = date.strftime('%Y-%m-%d')
        query = f"SELECT close FROM historical_candles WHERE symbol = '{canonical}' AND DATE(timestamp) = '{date_str}' ORDER BY timestamp DESC LIMIT 1"
        with db_manager as db:
            df = pd.read_sql(query, db.conn)

        if df.empty:
            # Fallback to current price if no historical data found for today
            if date == datetime.now().date():
                 temp_df = st.session_state.dm.get_historical_candles(canonical, from_date=date_str, to_date=date_str, mode='live', n_bars=1)
                 if temp_df is not None and not temp_df.empty:
                     spot = temp_df.iloc[-1]['close']
                 else:
                     return None, None
            else:
                return None, None
        else:
            spot = df.iloc[0]['close']

        st.session_state.dm.load_and_cache_fno_instruments(target_date=date_str)
        ce_key, ce_name = st.session_state.dm.get_atm_option_details(symbol, 'BUY', spot, target_date=date_str)
        pe_key, pe_name = st.session_state.dm.get_atm_option_details(symbol, 'SELL', spot, target_date=date_str)
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
    display_chart(index_candles, trades_df, f"{selected_symbol} Index", height=400)
else:
    st.warning(f"No index candles found for {selected_symbol} on {selected_date}")

# Row 2: ATM Options side-by-side
st.divider()
col_ce, col_pe = st.columns(2)

with col_ce:
    st.write("### ATM CE Chart")
    if atm_ce:
        ce_key, ce_name = atm_ce
        ce_candles = load_candles(ce_key, selected_date, mode=fetch_mode)
        if not ce_candles.empty:
            display_chart(ce_candles, trades_df, ce_name, height=300)
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
            display_chart(pe_candles, trades_df, pe_name, height=300)
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
            display_chart(opt_candles, trades_df, selected_trade['instrument_key'], height=300)
        else:
            st.warning("No candles for this trade's option.")
else:
    st.info(f"No trades recorded for {selected_symbol} on {selected_date}")

# Auto-refresh logic
if live_mode:
    time.sleep(5)
    st.rerun()
