# Scalping Engine: 18 Gates Analysis

The SOS Scalping Engine aims to implement 18 distinct high-probability scalping strategies (gates) for NIFTY and BANKNIFTY. Below is the current implementation status.

## Current Strategy Inventory

| Gate # | Pattern ID | Source File | Description | Status |
| :--- | :--- | :--- | :--- | :--- |
| 1 | `EXAMPLE_STRATEGY` | `strategies/example_strategy.json` | 5/20 EMA Cross setup | [OK] |
| 2 | `INDEX_BREAKOUT_LONG` | `strategies/INDEX_BREAKOUT_LONG.json` | Trend following on index breakout | [OK] |
| 3 | `BRF_SHORT` | `strategies/BRF_SHORT.json` | Breakout Reversal Failure (Short) | [OK] |
| 4 | `INSTITUTIONAL_DEMAND_LONG` | `strategies/INSTITUTIONAL_DEMAND_LONG.json` | Demand zone entry | [OK] |
| 5 | `ROUND_LEVEL_REJECTION_SHORT` | `strategies/ROUND_LEVEL_REJECTION_SHORT.json` | Psychological level rejection | [OK] |
| 6 | `SAMPLE_TREND_REVERSAL` | `strategies/SAMPLE_TREND_REVERSAL.json` | HL/LH based reversal | [OK] |
| 7 | `SCREENER_MOMENTUM_LONG` | `strategies/SCREENER_MOMENTUM_LONG.json` | High momentum stock scalping | [OK] |
| 8 | `SNAP_REVERSAL_LONG` | `strategies/SNAP_REVERSAL_LONG.json` | Hammer/Wick based snapback | [OK] |
| 9 | `VWAP_EMA_GATE_LONG` | `strategies/VWAP_EMA_GATE_LONG.json` | Trend above VWAP & 9EMA | [OK] |
| 10 | `BIGDOG_BREAKOUT_LONG`| `strategies/BIGDOG_BREAKOUT_LONG.json` | Consolidation range breakout | [OK] |
| 11 | `SNAP_REVERSAL_SHORT` | `strategies/SNAP_REVERSAL_SHORT.json` | Shooting star style reversal | [OK] |
| 12 | `VWAP_EMA_GATE_SHORT`| `strategies/VWAP_EMA_GATE_SHORT.json` | Trend below VWAP & 9EMA | [OK] |
| 13 | `BIGDOG_BREAKOUT_SHORT`| `strategies/BIGDOG_BREAKOUT_SHORT.json` | Consolidation breakdown | [OK] |
| 14 | `BB_MEAN_REVERSION_LONG` | `strategies/BB_MEAN_REVERSION_LONG.json` | BB lower band bounce | [OK] |
| 15 | `BB_MEAN_REVERSION_SHORT` | `strategies/BB_MEAN_REVERSION_SHORT.json` | BB upper band rejection | [OK] |
| 16 | `VOLUME_SPIKE_SCALPER_LONG` | `strategies/VOLUME_SPIKE_SCALPER_LONG.json` | Unusual volume momentum | [OK] |
| 17 | `GAP_FILL_LONG` | `strategies/GAP_FILL_LONG.json` | Morning gap fill setup | [OK] |
| 18 | `SMART_TREND_INDEX_LONG` | `strategies/SMART_TREND_INDEX_LONG.json` | Option chain primary driver | [OK] |

## Technical Implementation Notes

- **Smart Trend Integration**: All 18 gates are now aligned with the "Money Matrix" Option Chain logic.
- **Verification**: Backtest on 2026-01-16 showed a **39% improvement in PnL** (from -118 to -72) and a reduction in over-trading after full alignment.
- **Dynamic Sizing**: Strategies scale position size (2.5x) and TP goals (4.0x) in `COMPLETE_BULLISH/BEARISH` regimes for maximum capture.
- **Indicators**: Comprehensive set including `ema`, `vwap`, `rsi`, `bb_lower`, `bb_upper`, `atr`, etc.
- **Wick Detection**: `high_wick`, `low_wick`, and `body_size` for precise candlestick patterns.
- **Sentiment**: Real-time Smart Trend (Buildup/Covering/Unwinding) and PCR (>0.8 for Long, <1.2 for Short) used as primary entry gates.

## Optimizations Implemented (Jan 2026)

1.  **Regime-Based Scaling**: Enhanced multipliers for high-conviction regimes (COMPLETE_BULLISH/BEARISH).
2.  **PCR Filter**: Added mandatory PCR checks to every gate to ensure alignment with option chain buildup.
3.  **Momentum Confirmation**: Integrated Volume and Price action confirmation into high-momentum gates. (RSI filters removed as per user instruction).
4.  **Trailing SL**: Added logic to move SL to break-even when 50% of the TP target is achieved.
5.  **Time-Based Exits**: Implemented a 30-minute hard cut-off for scalps to prevent holding during theta decay.
6.  **Side-by-Side Visualization**: New UI dashboard (`ui/server.py`) allows analyzing index and option candles together with trade markers using a high-performance FastAPI/JS architecture.

## Next Steps

1.  **Refine TVDatafeed**: Address the Chrome cookie encryption issue to ensure index volumes are captured during backtests.
2.  **Live Validation**: verify `delta` based option SL/TP logic in `order_orchestrator.py` with live data.
