# Scalping Engine: 18 Gates Analysis

The SOS Scalping Engine aims to implement 18 distinct high-probability scalping strategies (gates) for NIFTY and BANKNIFTY. Below is the current implementation status.

## Current Strategy Inventory

| Gate # | Pattern ID | Source File | Description | Status |
| :--- | :--- | :--- | :--- | :--- |
| 1 | `MV_CROSS_SIMPLE` | `strategies/example_strategy.json` | 5/20 EMA Cross setup | [OK] |
| 2 | `INDEX_BREAKOUT_LONG` | `strategies/INDEX_BREAKOUT_LONG.json` | Trend following on index breakout | [OK] |
| 3 | `BRF_SHORT` | `strategies/BRF_SHORT.json` | Breakout Reversal Failure (Short) | [OK] |
| 4 | `INSTITUTIONAL_DEMAND` | `strategies/INSTITUTIONAL_DEMAND_LONG.json` | Demand zone entry | [OK] |
| 5 | `ROUND_LEVEL_REJ_SHORT` | `strategies/ROUND_LEVEL_REJECTION_SHORT.json` | Psychological level (000/500) rejection | [OK] |
| 6 | `SAMPLE_TREND_REVERSAL` | `strategies/SAMPLE_TREND_REVERSAL.json` | HL/LH based reversal | [OK] |
| 7 | `SCREENER_MOMENTUM` | `strategies/SCREENER_MOMENTUM_LONG.json` | High momentum stock scalping | [OK] |
| 8 | `SNAP_REVERSAL_LONG` | `strategies/SNAP_REVERSAL_LONG.json` | Hammer/Wick based snapback | [NEW] |
| 9 | `VWAP_EMA_GATE_LONG` | `strategies/VWAP_EMA_GATE_LONG.json` | Trend persistence above VWAP & 9EMA | [NEW] |
| 10 | `BIGDOG_BREAKOUT_LONG`| `strategies/BIGDOG_BREAKOUT_LONG.json` | Consolidation range breakout | [NEW] |
| 11 | `SNAP_REVERSAL_SHORT` | *Pending* | Shooting star style reversal | [TODO] |
| 12 | `VWAP_EMA_GATE_SHORT`| *Pending* | Trend persistence below VWAP & 9EMA | [TODO] |
| 13 | `BIGDOG_BREAKOUT_SHORT`| *Pending* | Consolidation range breakdown | [TODO] |
| 14 | `BB_MEAN_REVERSION_L` | *Pending* | Bollinger Band lower band touch/bounce | [TODO] |
| 15 | `BB_MEAN_REVERSION_S` | *Pending* | Bollinger Band upper band touch/reject | [TODO] |
| 16 | `VOL_BURST_SCALPER` | *Pending* | Momentum spike on unusual volume | [TODO] |
| 17 | `GAP_FILL_LONG` | *Pending* | Morning gap fill setup | [TODO] |
| 18 | `SCALPING_GATE_PRO` | `strategies/INDEX_OPTION_DEMO.json` | Multi-factor confirmation gate | [DRAFT] |

## Technical Implementation Notes

- **Indicators**: Added `ema`, `vwap`, `rsi`, `highest`, `lowest`, `sma` to Python execution context.
- **Wick Detection**: Added `high_wick`, `low_wick`, and `body_size` helper functions for candle pattern detection (SNAP gates).
- **Index Volume**: Data sourcing for volume from `tvDatafeed` is now integrated into `DataManager` specifically for indices.
- **Sentiment**: PCR and Market Breadth are used to filter entries based on `regime_config` in each JSON.

## Required Actions

1.  **Refine TVDatafeed**: Address the Chrome cookie encryption issue to ensure index volumes are captured during backtests.
2.  **Complete TODOs**: Implement the remaining 7 gates in JSON format.
3.  **Validate Execution**: verify `delta` based option SL/TP logic in `order_orchestrator.py`.
