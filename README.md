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
    cd Scalping-Orchestration-System-SOS-
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

To run a backtest, use the `run.py` script with `backtest` mode and specify a symbol.

```bash
python run.py --mode backtest --symbol NIFTY
```

This will fetch the latest historical data for the symbol, run it through the engine, and print any trade executions to the console.

### Live Trading

To run the engine in live mode, you first need a valid Upstox developer access token.

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
