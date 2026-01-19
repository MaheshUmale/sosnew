# Scalping Orchestration System (SOS) - Python Engine

This repository contains a high-frequency Python trading engine optimized for scalping NIFTY and BANKNIFTY options.

## 🚀 Jan 2026 Architecture Redesign

The system has been completely redesigned to be more modular, simplified, and robust:

1.  **Unified Trading Engine**: A single `TradingEngine` core now handles both backtest and live modes, ensuring parity between historical testing and real-time execution.
2.  **Market Structure Handler**: Implements advanced swing detection (Pivot Highs/Lows) and identifies immediate hurdles (Support/Resistance) based on price action and OI walls.
3.  **Data Repository Pattern**: Clean separation between database retrieval and remote data sourcing.
4.  **Smart Filter Integration**: Every entry is filtered by Smart Trend (Buildup/Unwinding) and PCR velocity to align with institutional order flow.

## 📊 Performance Report (Jan 19, 2026)

| Date | Total Trades | Net PnL | Win Rate |
| :--- | :--- | :--- | :--- |
| 2026-01-16 | 20 | -30.25 | 0.00% |
| 2026-01-19 | 11 | +9.80 | 27.27% |
| **Total** | **31** | **-20.45** | **9.68%** |

*Note: Jan 19 showed a significant improvement in profitability due to better alignment with market structure.*

---

## 🚀 Quick Start

### 1. Installation
```bash
pip install -r requirements.txt
pip install git+https://github.com/upstox/upstox-python.git@0b6dd12a1b0d107a8d95284840ed4bfb1be37230
```

### 2. Run Backtest
```bash
python run.py --mode backtest --symbol NIFTY --from-date 2026-01-19 --to-date 2026-01-19
```

### 3. Generate Report
```bash
python final_backtest_report.py
```

### 4. Visualizer Dashboard
```bash
python ui/server.py
```

---

## 📂 Core Architecture

- **`python_engine/core/trading_engine.py`**: The orchestration hub.
- **`python_engine/core/market_structure_handler.py`**: Swing and Hurdle detection.
- **`python_engine/data/repository.py`**: Clean SQLite interface.
- **`data_sourcing/ingestion.py`**: High-fidelity data acquisition and enrichment.

---

## 💎 Key Features

- **Money Matrix (Smart Trend)**: Filters trades by Option Chain Buildup.
- **Dynamic Sizing**: Scales position sizes based on market regime (COMPLETE_BULLISH/BEARISH).
- **Trailing SL**: Automatic break-even logic after 50% target reach.
- **High-Fidelity Greeks**: Per-minute IV, Delta, and Theta calculation during ingestion.

---

## ⚡ Live Trading
```bash
python run.py --mode live
```
