with open('run_ui.py', 'r') as f:
    content = f.read()

# Fix display_chart to use a temporary df for chart.set but keep original for markers
old_block = """    # Drop non-serializable columns but keep 'symbol' for trade matching
    cols_to_keep = ['time', 'open', 'high', 'low', 'close', 'volume', 'oi', 'symbol']
    df = df[[c for c in cols_to_keep if c in df.columns]]

    # Configure Chart
    chart.set(df)"""

new_block = """    # Configure Chart (use only OHLC columns for setting data)
    chart_cols = ['time', 'open', 'high', 'low', 'close', 'volume', 'oi']
    chart_df = df[[c for c in chart_cols if c in df.columns]]
    chart.set(chart_df)"""

content = content.replace(old_block, new_block)

with open('run_ui.py', 'w') as f:
    f.write(content)
