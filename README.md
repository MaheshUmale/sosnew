# SOS-System-DATA-Bridge

This repository contains the Python-based Data Bridge for the Scalping Orchestration System (SOS). It acts as a WebSocket server, collecting market data from various sources and broadcasting it to the Java Core Engine.

## Backtesting Workflow

The primary workflow for this repository is to prepare historical data and feed it to the Java engine for backtesting.

### Step 1: Prepare Backtest Data

First, you need to download all the necessary historical data for a specific date and store it in a local SQLite database.

1.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
2.  **Configure the Upstox API key:**
    Create a `config.py` file with your Upstox access token:
    ```python
    ACCESS_TOKEN = "YOUR_ACCESS_TOKEN"
    ```
3.  **Run the data preparation script:**
    Execute the `prepare_backtest_data.py` script with the target date as an argument.
    ```bash
    python prepare_backtest_data.py YYYY-MM-DD
    ```
    For example, to get data for January 13th, 2026:
    ```bash
    python prepare_backtest_data.py 2026-01-13
    ```
    This will create a `backtest_data.db` file containing all the candle, option chain, and sentiment data for that day.

### Step 2: Run the Backtest

Once the data is prepared, you can run the backtest.

1.  **Start the Python Data Bridge Server:**
    Run the `tv_data_bridge.py` script. This will start a WebSocket server that reads the data from `backtest_data.db` and replays it.
    ```bash
    python tv_data_bridge.py
    ```
2.  **Start the Java Core Engine:**
    In a separate terminal, start the Java engine. It will connect to the Python server, receive the historical data, and run the trading strategies.
    ```bash
    # Make sure you have built the Java engine first
    java -jar engine/target/sos-engine-1.0-SNAPSHOT.jar
    ```

## Live Trading

For live trading, the process is different. The `live_trading_bridge.py` script connects to the Upstox WebSocket for real-time data and forwards it to the Java engine.

1.  **Install dependencies and configure the API key** as described in the backtesting section.
2.  **Run the live trading bridge:**
    ```bash
    python live_trading_bridge.py
    ```
    This script will:
    *   Start the Java Core Engine automatically in the background.
    *   Connect to the Upstox live data feed.
    *   Transform the data to the format expected by the SOS Engine.
    *   Forward the live data to the Java engine.

**Note:** The `tv_data_bridge.py` script is for replaying backtest data, while the `live_trading_bridge.py` script is for live market data. Do not run both at the same time.

## Vendored Dependency

The `tvdatafeed` library has been vendored into the `data_sourcing/tvdatafeed` directory. This was done to bypass persistent installation issues that were encountered in the development environment. This is a form of technical debt, and it should be revisited in the future to see if a more standard installation method is available.
