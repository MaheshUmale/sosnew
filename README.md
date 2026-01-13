# SOS-System-DATA-Bridge

This repository contains the Python-based Data Bridge for the Scalping Orchestration System (SOS). It acts as a WebSocket server, collecting market data from various sources and broadcasting it to the Java Core Engine.

## Running Locally (as a Server)

1.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
2.  **Configure the Upstox API key:**
    Create a `config.py` file with your Upstox access token:
    ```python
    ACCESS_TOKEN = "YOUR_ACCESS_TOKEN"
    ```
3.  **Run the script:**
    ```bash
    python3 tv_data_bridge.py
    ```
    The Data Bridge will start a WebSocket server and listen for connections on `ws://localhost:8765`.
