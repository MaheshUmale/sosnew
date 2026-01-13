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
| `regime` | String | A string representing the current market state. |

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

### 3.3 `OPTION_CHAIN_UPDATE`

This message provides a snapshot of the option chain for a specific symbol, focusing on Open Interest (OI) data.

- **`type`**: `"OPTION_CHAIN_UPDATE"`

#### `data` Object Structure

| Field    | Type  | Description                                                     |
|----------|-------|-----------------------------------------------------------------|
| `symbol` | String| The identifier for the financial instrument (e.g., "NIFTY_BANK"). |
| `chain`  | Array | An array of objects, where each object represents a strike price. |

#### `chain` Array Object Structure

| Field        | Type   | Description                                 |
|--------------|--------|---------------------------------------------|
| `strike`     | Double | The strike price.                           |
| `call_oi_chg`| Long   | The change in open interest for call options. |
| `put_oi_chg` | Long   | The change in open interest for put options.  |

### 3.4 `MARKET_UPDATE`

This is a composite message that combines candle data and sentiment data into a single update. This is the primary message type used during active market hours.

- **`type`**: `"MARKET_UPDATE"`

#### `data` Object Structure

| Field       | Type   | Description                                      |
|-------------|--------|--------------------------------------------------|
| `symbol`    | String | The identifier for the financial instrument.     |
| `candle`    | Object | A nested JSON object containing the OHLCV data.  |
| `sentiment` | Object | A nested JSON object containing sentiment metrics. |

#### `sentiment` Object Structure

| Field    | Type   | Description                                     |
|----------|--------|-------------------------------------------------|
| `pcr`    | Double | The Put-Call Ratio.                             |
| `regime` | String | The calculated market regime (see `SENTIMENT_UPDATE`). |


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

### 4.2 `OPTION_CHAIN_UPDATE` Example

```json
{
  "type": "OPTION_CHAIN_UPDATE",
  "timestamp": 1704711720000,
  "data": {
    "symbol": "NIFTY_BANK",
    "chain": [
      { "strike": 48000, "call_oi_chg": -15000, "put_oi_chg": 25000 },
      { "strike": 48100, "call_oi_chg": -10000, "put_oi_chg": 18000 },
      { "strike": 48200, "call_oi_chg": 22000, "put_oi_chg": 5000 }
    ]
  }
}
```

### 4.3 `MARKET_UPDATE` Example

```json
{
  "type": "MARKET_UPDATE",
  "timestamp": 1704711780000,
  "data": {
    "symbol": "NIFTY_BANK",
    "candle": {
      "open": 48150.75,
      "high": 48200.00,
      "low": 48120.50,
      "close": 48180.25,
      "volume": 95000
    },
    "sentiment": {
      "pcr": 1.05,
      "regime": "SIDEWAYS_BULLISH"
    }
  }
}
```

### 4.4 `SENTIMENT_UPDATE` Example

```json
{
  "type": "SENTIMENT_UPDATE",
  "timestamp": 1704711660000,
  "data": {
    "regime": "BEARISH"
  }
}
```
