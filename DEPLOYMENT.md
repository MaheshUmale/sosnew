# SOS Deployment & Initialization Guide

This guide provides step-by-step instructions on how to initialize the SOS trading engine and run your first backtest or live session.

## 1. Prerequisites

- Python 3.10+
- SQLite (included with Python)
- Upstox API Credentials (Client ID, Secret, Redirect URL)
- Optional: MongoDB (for raw tick data ingestion)

## 2. Environment Setup

### Install Dependencies
```bash
pip install -r requirements.txt
pip install git+https://github.com/upstox/upstox-python.git@0b6dd12a1b0d107a8d95284840ed4bfb1be37230
```

### Configuration
Update `config.json` in the root directory:
```json
{
  "upstox_access_token": "YOUR_ACCESS_TOKEN",
  "strategies_dir": "strategies",
  "db_path": "sos_master_data.db"
}
```

## 3. Data Ingestion

The engine is self-healing, but for the best performance, pre-load historical data:

### Standard Ingestion (Upstox + Trendlyne)
```bash
python -m data_sourcing.ingestion --symbol NIFTY --from_date 2026-01-12 --to_date 2026-01-19 --full-options
```

### MongoDB Ingestion (High-Fidelity Ticks)
```bash
python -m data_sourcing.ingestion --mongo --mongo-uri "mongodb://localhost:27017/"
```

## 4. Running the Engine

### Backtest Mode
Execute a backtest for a specific symbol and date range. The engine will automatically use vectorized pivots and cached repository lookups.
```bash
python run.py --mode backtest --symbol NIFTY --from-date 2026-01-19 --to-date 2026-01-19
```

### Live Mode
Ensure your `upstox_access_token` is valid before starting.
```bash
python run.py --mode live
```

## 5. Performance Validation

Generate a consolidated PnL and strategy performance report:
```bash
python final_backtest_report.py
```

To view trades visually, start the FastAPI dashboard:
```bash
python ui/server.py
```
Then navigate to `http://localhost:8000`.

---
**Note:** For latency-sensitive environments, ensure the `sos_master_data.db` is stored on a high-speed NVMe drive to minimize SQLite I/O wait times.
