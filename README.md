# Scalping Orchestration System (SOS) - Python Engine

This repository contains a Python-based trading engine for backtesting and live trading financial strategies.

## High-Level Architecture

The engine is built with a modular, event-driven architecture. The core components are:
- **`run.py`**: The main entry point for running the engine in both backtest and live modes.
- **`python_engine`**: The main package containing the core trading logic.
  - **`main.py`**: Handles the backtesting loop.
  - **`live_main.py`**: Handles the live trading loop.
  - **`core`**: Contains the main processing handlers (`PatternMatcherHandler`, `ExecutionHandler`, etc.).
  - **`models`**: Contains the Python `dataclass` definitions for all data structures.
  - **`utils`**: Contains helper utilities like the `DotDict` and `atr_calculator`.
- **`data_sourcing`**: Contains the `DataManager` responsible for fetching all market data.
- **`strategies`**: Contains the JSON files that define the trading strategies.

## Installation

1.  **Clone the Repository:**
    ```bash
    git clone <repository-url>
    cd <repository-directory>
    ```

2.  **Install Dependencies:**
    It is highly recommended to use a virtual environment.
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
    pip install -r requirements.txt
    ```

## How to Run

### Backtesting

To run a backtest, the engine strictly reads from a local SQLite database (`sos_master_data.db`) to ensure data integrity and prevent look-ahead bias.

#### 🚀 Quick Start (One-Command Flow)
The engine now supports **automatic backfilling**. If you run a backtest for a date range that is missing from your database, SOS will automatically trigger the ingestion process.

```bash
# This command will check for data, ingest if missing, and then run the backtest
python run.py --mode backtest --symbol NIFTY --from-date 2026-01-12 --to-date 2026-01-16
```

#### 📊 Manual Data Ingestion
For fine-grained control or bulk loading, use the `ingestion.py` script. It consolidates index candles, option chains, and market statistics (PCR) into a single optimized process.

```bash
# Ingest 15 days of NIFTY data (skips existing data)
python -m data_sourcing.ingestion --symbol NIFTY --from_date 2026-01-01 --to_date 2026-01-16

# To force overwrite or re-enrich existing data, use the --force flag
python -m data_sourcing.ingestion --symbol NIFTY --from_date 2026-01-16 --to_date 2026-01-16 --force --full-options
```

**Advanced Ingestion Flags:**
- `--full-options`: Fetches 1-minute historical OI snapshots from Trendlyne (recommended for accurate PCR analysis).
- `--force`: Re-processes the date, ensuring all enrichment steps (OI summing, volume sync) are re-run.

If no dates are specified, it defaults to the last 5 days.

To run a strict backtest without automatic backfilling, use the `--no-backfill` flag:
```bash
python run.py --mode backtest --symbol NIFTY --no-backfill
```

This will run the ingested data through the engine and print any trade executions to the console.

### Live Trading

To run the engine in live mode, you first need a valid Upstox developer access token.

### Validating Strategies

Before running the engine, it is recommended to validate your strategy files to ensure they are correctly formatted. You can do this by running the `validate_strategies.py` script:

```bash
python validate_strategies.py
```

This script will check all the `.json` files in the `strategies` directory against a schema and also validate the syntax of the `asteval` expressions.

1.  **Configure Access Token:**
    Open the `config.json` file and add your Upstox access token:
    ```json
    {
        "strategies_dir": "strategies",
        "upstox_access_token": "YOUR_SECRET_ACCESS_TOKEN_HERE"
    }
    ```

2.  **Run in Live Mode:**
    Execute the `run.py` script with `live` mode:
    ```bash
    python run.py --mode live
    ```
    The engine will connect to the Upstox WebSocket feed and process live market data.

### Symbol Mapping and Instrument Resolution

The engine uses a centralized `SymbolMaster` to handle the conversion between human-readable tickers (e.g., `NSE|INDEX|NIFTY`) and Upstox-specific instrument keys.

- **Canonical Format:** The internal system uses `NSE|INDEX|NIFTY` and `NSE|INDEX|BANKNIFTY`.
- **Data Synchronization:** To ensure consistent joins between Index candles, Option chains, and PCR stats, all timestamps are **normalized to the minute** (seconds = 00) during ingestion. This prevents "missing data" errors caused by slight millisecond drifts in API responses.
- **Live Data Mapping:** In live mode, incoming numeric instrument keys from Upstox are automatically mapped back to these canonical tickers to ensure consistency with strategy evaluation and database storage.
- **Dynamic F&O Subscription:** For index trading, the system automatically resolves and subscribes to the relevant ATM/OTM/ITM Call and Put options based on the current spot price of the underlying index.

## Validating Strategies

To ensure that your strategy files are correctly formatted and will not cause errors, you can use the `validate_strategies.py` script. This script will check your strategy files against a schema and validate the syntax of the expressions.

To run the validator, simply execute the following command:

```bash
python validate_strategies.py
```

If all your strategy files are valid, you will see a message saying "All strategy files are valid." If there are any errors, they will be printed to the console.

## Recent Updates (Jan 2026)

### 💎 Money Matrix: Option Chain Analysis Engine
- **Smart Trend Logic**: Implemented high-frequency sentiment analysis based on the relationship between Price Change and Open Interest (OI) Change. Categorizes market into:
    - **Long Buildup**: Price ↑, OI ↑ (Strong Bullish)
    - **Short Covering**: Price ↑, OI ↓ (Moderate Bullish)
    - **Short Buildup**: Price ↓, OI ↑ (Strong Bearish)
    - **Long Unwinding**: Price ↓, OI ↓ (Moderate Bearish)
- **Math Engine**: Integrated a robust Math Engine for real-time calculation of:
    - **Implied Volatility (IV)**: Derived using Newton-Raphson solver on the Black-Scholes model.
    - **Greeks**: Delta and Theta calculated per minute for every strike in the chain.
- **Strategy Realignment**: All 18 "Gates" (trading strategies) have been updated to utilize these high-conviction signals via a new `SMART_FILTER` phase.

### 🛠️ Robust Infrastructure & Data Sync
- **Timestamp Normalization**: Implemented minute-level normalization across all database tables.
- **Proxy OI Enrichment**: Index candles are enriched with a "Proxy OI" calculated as the sum of all associated options' OI.
- **SQLite Compatibility**: Robust upsert pattern ensures compatibility with all SQLite versions.

### 📈 Backtest Enhancements
- **Automatic Backfilling**: `run.py` automatically triggers `IngestionManager` for missing data.
- **Realistic Option Pricing**: Option trades strictly use contract premium prices for all calculations (Entry, SL, TP).
- **Sentiment-Based Sizing**: Position sizing (`quantity_mod`) and profit targets (`tp_mult`) now dynamically scale based on sentiment strength (e.g., higher conviction in `COMPLETE_BULLISH` regimes).

### System Requirements
- **tvDatafeed**: Ensure you have `tvdatafeed` installed in your environment (`pip install tvdatafeed`).
- **Chrome**: `tvDatafeed` requires a Chrome browser installation for authentication.
