# SOS Engine Data Bridge Contract

This document outlines the data contract for third-party applications to act as a data bridge for the Scalping Orchestration System (SOS) Engine.

## 1. Overview & Connection Details

- **Protocol:** WebSocket
- **Data Format:** JSON
- **Default URI:** `ws://localhost:8765`

All communication between the data bridge and the SOS Engine is handled via a WebSocket connection. The **Data Bridge acts as the WebSocket Server**, listening for connections on port 8765. The **SOS Engine acts as the WebSocket Client**, initiating the connection to the bridge. The bridge sends JSON-formatted text messages to the engine upon connection and updates.

## 2. General Message Structure

All messages sent to the SOS Engine must be a JSON object containing the following top-level fields:

| Field       | Type   | Description                                                                 |
|-------------|--------|-----------------------------------------------------------------------------|
| `type`      | String | The type of the message. This determines the structure of the `data` object. |
| `timestamp` | Long   | The Unix timestamp (in milliseconds) when the event occurred.               |
| `data`      | Object | A JSON object containing the message-specific payload.                      |

## 3. Message Types

### 3.1 `CANDLE_UPDATE`

This message provides a snapshot of a single candle's data for a specific financial instrument.

- **`type`**: `"CANDLE_UPDATE"`

#### `data` Object Structure

| Field    | Type   | Description                                     |
|----------|--------|-------------------------------------------------|
| `symbol` | String | The identifier for the financial instrument (e.g., "NIFTY_BANK"). |
| `candle` | Object | A nested JSON object containing the OHLCV data. |

#### `candle` Object Structure

| Field    | Type   | Description                                     |
|----------|--------|-------------------------------------------------|
| `open`   | Double | The opening price of the candle.                |
| `high`   | Double | The highest price of the candle.                |
| `low`    | Double | The lowest price of the candle.                 |
| `close`  | Double | The closing price of the candle.                |
| `volume` | Long   | The trading volume during the candle's period.  |

### 3.2 `SENTIMENT_UPDATE`

This message provides a high-level overview of the current market sentiment, encapsulated in a single "regime" state.

- **`type`**: `"SENTIMENT_UPDATE"`

#### `data` Object Structure

| Field    | Type   | Description                                     |
|----------|--------|-------------------------------------------------|
| Field       | Type   | Description                                     |
|-------------|--------|-------------------------------------------------|
| `regime`    | String | A string representing the current market state. |
| `pcr`       | Double | Put-Call Ratio of the primary index.            |
| `advances`  | Integer| Number of advancing stocks in the market.       |
| `declines`  | Integer| Number of declining stocks in the market.       |

#### `regime` Enum Values

The `regime` field must be one of the following case-insensitive strings:

- `COMPLETE_BULLISH`
- `BULLISH`
- `SIDEWAYS_BULLISH`
- `SIDEWAYS`
- `SIDEWAYS_BEARISH`
- `BEARISH`
- `COMPLETE_BEARISH`
- `UNKNOWN`

## 4. Examples

### 4.1 `CANDLE_UPDATE` Example

```json
{
  "type": "CANDLE_UPDATE",
  "timestamp": 1704711600000,
  "data": {
    "symbol": "NIFTY_BANK",
    "candle": {
      "open": 48100.50,
      "high": 48250.00,
      "low": 48050.25,
      "close": 48150.75,
      "volume": 150000
    }
  }
}
```

### 4.2 `SENTIMENT_UPDATE` Example

```json
{
  "type": "SENTIMENT_UPDATE",
  "timestamp": 1704711660000,
  "data": {
    "regime": "BEARISH"
  }
}
```
