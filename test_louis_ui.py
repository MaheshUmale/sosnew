import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from lightweight_charts.widgets import StreamlitChart

def test_lc_ui():
    st.title("Louisnw01 Lightweight Charts Test")

    # Generate dummy data
    now = datetime.now()
    data = []
    for i in range(100):
        data.append({
            'time': now + timedelta(minutes=i),
            'open': 100 + np.random.randn(),
            'high': 102 + np.random.randn(),
            'low': 98 + np.random.randn(),
            'close': 100 + np.random.randn(),
            'volume': 1000 * np.random.rand()
        })
    df = pd.DataFrame(data)

    # Louisnw01 library uses StreamlitChart widget
    chart = StreamlitChart(width=700, height=400)
    chart.set(df)
    chart.load()

if __name__ == "__main__":
    test_lc_ui()
