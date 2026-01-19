# Scalping Orchestration System (SOS) - Python Engine

This repository contains a high-frequency Python trading engine optimized for scalping NIFTY and BANKNIFTY options.

## 🚀 Quick Start (Automated Flow)

To run a complete backtest session (Ingestion + Backtest + Report):

```bash
# 1. Run backtest (Automatically ingests data if missing)
python run.py --mode backtest --symbol NIFTY --from-date 2026-01-12 --to-date 2026-01-16

# 2. View performance UI (Side-by-Side Charts)
streamlit run run_ui.py
```

---

## 📂 Core Architecture

- **`run.py`**: Main entry point for Backtest and Live modes.
- **`python_engine/`**:
  - `main.py`: Core backtest engine with **Trailing SL** and **Time Exit** logic.
  - `live_main.py`: Live trading implementation with WebSockets.
  - `utils/symbol_master.py`: Standardized symbol management (OpenAlgo inspired).
  - `utils/math_engine.py`: Black-Scholes Greeks and Smart Trend logic.
- **`data_sourcing/`**: Unified data management (Upstox, Trendlyne, TVDatafeed).
- **`strategies/`**: 18 Optimized trading gates in JSON format.

---

## 🛠️ Detailed Instructions

### 1. Installation & Config

```bash
pip install -r requirements.txt
# Requires Chrome for TVDatafeed volume sync
```

Update `config.json` with your Upstox credentials for Live mode or remote data fetching.

### 2. Data Ingestion (Manual Control)

If you prefer to bulk-load data before testing:

```bash
# Ingest Index Candles + Daily Option Chain snapshots
python -m data_sourcing.ingestion --symbol NIFTY --from_date 2026-01-12 --to_date 2026-01-16

# Sync minute-by-minute historical OI for Smart Trend analysis
python backfill_trendlyne.py --full --date 2026-01-12 --symbol NIFTY
```

### 3. Backtesting

The engine strictly uses canonical symbols: `NIFTY` or `BANKNIFTY`.

```bash
# Run multi-day backtest
python run.py --mode backtest --symbol BANKNIFTY --from-date 2026-01-12 --to-date 2026-01-16
```

### 4. 📊 Analysis & Reporting

#### **Performance Report (CLI)**
Generate detailed Win/Loss and PnL metrics per Strategy (Gate) and Symbol:
```bash
# Custom script to run all 18 gates and consolidate results
python final_backtest_report.py
```

#### **Visualizer Dashboard (UI)**
A professional dashboard to analyze trades side-by-side on Index and Option premium charts.
```bash
streamlit run run_ui.py
```
- **Trade Markers**: Entry/Exit arrows plotted exactly on candles.
- **Side-by-Side View**: Compare Index movement vs Option premium decay.
- **Live Mode**: Toggle for real-time chart updates.

---

## 💎 Key Optimizations (Jan 2026)

### **1. Standardized Symbology**
Adopted OpenAlgo-style mapping. Internal logic is decoupled from broker keys, supporting seamless fallback between multiple data providers.

### **2. Money Matrix (Smart Trend)**
Every gate is now filtered by **Option Chain Buildup**:
- **Long Buildup / Short Covering**: Permitted for LONG entries.
- **Short Buildup / Long Unwinding**: Permitted for SHORT entries.
- **PCR Filter**: Mandatory alignment with Put-Call Ratio boundaries (>0.8 for Bullish).

### **3. Execution Hardening**
- **Trailing Stop Loss**: Automatically moves SL to Break-even once 50% of the TP target is achieved.
- **Time-Based Exit**: Hard 30-minute cut-off for scalps to prevent holding through theta decay.
- **Dynamic Sizing**: Position sizes scale up to 2.5x in high-conviction "COMPLETE" regimes.

### **4. Realistic Option PnL**
Unlike basic backtesters, SOS fetches **historical option premiums**. SL/TP and PnL are calculated using actual contract prices, not just index spot proxies.

---

## 🧪 Testing & Validation

To ensure your strategy logic is correct before trading:
```bash
python validate_strategies.py
```

---

## ⚡ Live Trading

To start live mode with Upstox:

1.  **Obtain API Credentials**: Get your `Client ID`, `Secret`, and `Redirect URL` from the Upstox Developer Portal.
2.  **Generate Access Token**: Use the `data_sourcing/upstox_gateway.py` or the official Upstox login flow to get an `access_token`.
3.  **Configure Engine**: Update `config.json` with your token:
    ```json
    {
      "upstox_access_token": "your_token_here",
      "strategies_dir": "strategies"
    }
    ```
4.  **Start the Engine**:
    ```bash
    python run.py --mode live
    ```
5.  **Monitor Live Trades**:
    In a separate terminal, run the UI to see live candles and executions:
    ```bash
    streamlit run run_ui.py
    ```
