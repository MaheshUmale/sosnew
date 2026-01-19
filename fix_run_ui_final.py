import sys

def rewrite():
    with open('run_ui.py', 'r') as f:
        lines = f.readlines()

    new_lines = []
    skip = False
    for line in lines:
        if 'def display_chart(df, trades, title, height=400):' in line:
            new_lines.append(line)
            new_lines.append("    if df.empty:\n")
            new_lines.append("        st.warning(f'No data to display for {title}')\n")
            new_lines.append("        return\n\n")
            new_lines.append("    # Create the chart\n")
            new_lines.append("    chart = StreamlitChart(width=None, height=height)\n\n")
            new_lines.append("    # Configure Chart (OHLC columns)\n")
            new_lines.append("    chart_cols = ['time', 'open', 'high', 'low', 'close', 'volume', 'oi']\n")
            new_lines.append("    chart_df = df[[c for c in chart_cols if c in df.columns]]\n")
            new_lines.append("    chart.set(chart_df)\n\n")
            new_lines.append("    # Add Markers for trades\n")
            new_lines.append("    if not trades.empty:\n")
            new_lines.append("        for _, trade in trades.iterrows():\n")
            new_lines.append("            # Match trade to symbol\n")
            new_lines.append("            if trade['symbol'] == df['symbol'].iloc[0] or trade['instrument_key'] == df['symbol'].iloc[0]:\n")
            new_lines.append("                entry_time = pd.to_datetime(trade['entry_time']).strftime('%Y-%m-%d %H:%M:%S')\n")
            new_lines.append("                chart.marker(time=entry_time, position='belowBar', color='#2196F3', shape='arrowUp', text=f\"Entry @ {trade['entry_price']}\")\n")
            new_lines.append("                if trade['exit_time']:\n")
            new_lines.append("                    exit_time = pd.to_datetime(trade['exit_time']).strftime('%Y-%m-%d %H:%M:%S')\n")
            new_lines.append("                    chart.marker(time=exit_time, position='aboveBar', color='#e91e63', shape='arrowDown', text=f\"Exit @ {trade['exit_price']}\")\n\n")
            new_lines.append("    chart.load()\n")
            skip = True
        elif skip and 'chart.load()' in line:
            skip = False
            continue
        elif skip:
            continue
        else:
            new_lines.append(line)

    with open('run_ui.py', 'w') as f:
        f.writelines(new_lines)

rewrite()
