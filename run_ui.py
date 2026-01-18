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
except ImportError:
    # Fallback for different directory structures
    import sys
    import os
    sys.path.append(os.getcwd())
    from python_engine.utils.symbol_master import MASTER as SymbolMaster
    from python_engine.core.trade_logger import TradeLog

# Configuration
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

def render_chart(candles, trades, title, div_id):
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
    <div id="{div_id}" style="height: 400px; width: 100%;"></div>
    <script src="https://unpkg.com/lightweight-charts/dist/lightweight-charts.standalone.production.js"></script>
    <script>
        (function() {{
            const chart = LightweightCharts.createChart(document.getElementById('{div_id}'), {{
                width: document.getElementById('{div_id}').clientWidth,
                height: 400,
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
                chart.resize(document.getElementById('{div_id}').clientWidth, 400);
            }});
        }})();
    </script>
    """
    return html_template

# Streamlit UI
st.set_page_config(layout="wide", page_title="SOS Scalping Dashboard")

st.title("🚀 SOS Scalping Engine - Trade Analysis")

# Sidebar
st.sidebar.header("Settings")
selected_symbol = st.sidebar.selectbox("Symbol", ["NIFTY", "BANKNIFTY"])
selected_date = st.sidebar.date_input("Date", datetime.strptime("2026-01-16", "%Y-%m-%d").date())
live_mode = st.sidebar.toggle("Live Mode (Auto-refresh)", value=False)

# Re-init SymbolMaster to ensure we use the singleton
SymbolMaster.initialize()

if live_mode:
    st.sidebar.info("Refreshing every 5 seconds...")
    time.sleep(5)
    st.rerun()

# Data Loading
symbol_master = SymbolMaster()
db_symbol = symbol_master.get_upstox_key(selected_symbol)

trades_df = load_trades(db_symbol, selected_date)

if not trades_df.empty:
    st.subheader(f"Trades for {selected_symbol} on {selected_date}")

    # Selection
    selected_trade_idx = st.selectbox("Select Trade to Visualize", trades_df.index,
                                     format_func=lambda x: f"[{trades_df.loc[x, 'pattern_id']}] Entry: {trades_df.loc[x, 'entry_time']} @ {trades_df.loc[x, 'entry_price']}")

    selected_trade = trades_df.loc[selected_trade_idx]

    # Main content: Side-by-side charts
    col1, col2 = st.columns(2)

    with col1:
        st.write("### Index Chart")
        index_candles = load_candles(db_symbol, selected_date)
        if not index_candles.empty:
            st.components.v1.html(render_chart(index_candles, trades_df, f"{selected_symbol} Index", "index_chart"), height=450)
        else:
            st.warning("No index candles found for this date.")

    with col2:
        st.write("### Option Chart")
        opt_key = selected_trade['instrument_key']
        option_candles = load_candles(opt_key, selected_date)
        if not option_candles.empty:
            st.components.v1.html(render_chart(option_candles, trades_df, f"Option {opt_key}", "option_chart"), height=450)
        else:
            st.warning(f"No option candles found for {opt_key}.")

    # Trade Details
    st.divider()
    st.write("### Trade Details")
    st.json(selected_trade.to_dict())

else:
    st.warning(f"No trades found for {selected_symbol} on {selected_date}")
    # Still show the index chart if available
    st.write("### Index Chart")
    index_candles = load_candles(db_symbol, selected_date)
    if not index_candles.empty:
        st.components.v1.html(render_chart(index_candles, pd.DataFrame(), f"{selected_symbol} Index", "index_chart_no_trades"), height=450)
    else:
        st.info("No index candles found for this date either. Try another date or run backtest.")
