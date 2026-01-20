# Scalping Orchestration System (SOS) - Python Engine

High-performance, modular option trading engine optimized for scalping NIFTY and BANKNIFTY with a focus on institutional order flow and market structure.

---

## 🚀 2026 Modular Handler-Based Architecture

The SOS engine has been refactored into a senior-grade, handler-based pipeline. This architecture ensures strict parity between backtesting and live trading while maintaining low latency.

### Core Components
1.  **Unified TradingEngine**: The central orchestrator managing a sequential pipeline of analysis modules (Structure -> Sentiment -> Option Chain -> Pattern -> Execution).
2.  **MarketStructureHandler**: Uses **Vectorized Pivot Detection** (Numpy-based rolling windows) to identify local Highs/Lows and tracks institutional hurdles (Support/Resistance) based on price action stalling and OI walls.
3.  **DataRepository (Singleton)**: An optimized abstraction layer for SQLite I/O, featuring **Metadata Caching** and **LRU Caches** for high-frequency stats lookups during backtests.
4.  **IngestionManager**: A high-fidelity data acquisition hub that resolves option contract keys and performs vectorized Greeks enrichment (Delta, Gamma, Theta, Vega) and PCR velocity calculations.

---

## 📈 Performance Report (Jan 2026)

| Date | Total Trades | Net PnL | Win Rate | Status |
| :--- | :--- | :--- | :--- | :--- |
| 2026-01-16 | 20 | -30.25 | 0.00% | Initial Test |
| 2026-01-19 | 11 | **+9.80** | **27.27%** | Optimized |
| **Consolidated** | **31** | **-20.45** | **9.68%** | |

*Note: The performance shift on Jan 19 highlights the impact of the newly implemented Market Structure and Smart Trend filters.*

---

## 🛠️ Optimization & Production Readiness

-   **Vectorization**: All Pivot and Hurdle detection logic is implemented using Numpy array operations to minimize CPU cycles per tick.
-   **Structured Logging**: System-wide logging follows the standardized format: `[%(asctime)s] [%(levelname)s] - %(message)s` for enhanced observability.
-   **Strict Documentation**: Codebase adheres to Google-style docstrings and comprehensive Python type hints for maintainability.
-   **Resilience**: Implemented robust fallback mechanisms for PCR calculation and session re-initialization for live data feeders.

---

## 🚀 Quick Start

### 1. Installation & Environment
```bash
pip install -r requirements.txt
pip install git+https://github.com/upstox/upstox-python.git@0b6dd12a1b0d107a8d95284840ed4bfb1be37230
```

### 2. Configuration
Update `config.json` with your Upstox access token and strategy directory. See `DEPLOYMENT.md` for full environment setup.

### 3. Execution
**Backtest Mode**:
```bash
python run.py --mode backtest --symbol NIFTY --from-date 2026-01-19 --to-date 2026-01-19
```

**Live Mode**:
```bash
python run.py --mode live
```

---

## 📂 Project Structure

- **`python_engine/core/`**: Trading logic, handlers, and state management.
- **`python_engine/data/`**: Repository pattern and database abstraction.
- **`data_sourcing/`**: Unified API clients (Upstox, Trendlyne, NSE) and ingestion pipeline.
- **`strategies/`**: 18 Scalping strategies defined in JSON format.
- **`ui/`**: FastAPI-based dashboard for real-time and historical trade visualization.

---

## 💎 Advanced Features

- **Money Matrix (Smart Trend)**: Dynamic regime mapping (Buildup, Unwinding, Covering) based on per-minute OI changes.
- **Dynamic Sizing**: Position sizing scales (up to 2.5x) based on regime strength.
- **High-Fidelity Greeks**: Integrated Black-Scholes pricing and Greeks calculation at 1-minute resolution.
- **Self-Healing Data**: Automated backfilling of missing candles or option chains during backtest execution.
