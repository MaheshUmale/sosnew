# SOS Trading Engine - TODO List

## 🚨 Critical Issues (In Progress)

### ATR/SL/TP Calculation
- [ ] Verify ATR is correctly primed from historical data before live trading starts
- [ ] Confirm TP calculation produces non-zero difference (`entry + ATR*3`)
- [ ] Test with backtest mode on today's data to validate fix
- [ ] Remove debug print statements from `OrderOrchestrator` after validation

### WebSocket Stability
- [ ] Investigate frequent WebSocket disconnections (Exit code: 1)
- [ ] Add `on_auto_reconnect_stopped(self, reason)` parameter fix in `live_main.py`
- [ ] Improve error handling for streamer reconnection logic

---

## 📊 Data & Symbol Resolution

### Symbol Mapping (Fixed ✅)
- [x] Fix `DataManager.get_atm_option_details_for_timestamp` symbol format (`NIFTY 25750 CE 22 JAN 26`)
- [x] Fix `InstrumentLoader` to map "NIFTY" → "Nifty 50" for options lookup
- [x] Normalize ATR cache key to match primed symbol format

### Data Sources
- [ ] Verify `tvDatafeed` is providing accurate volume data for NIFTY/BANKNIFTY
- [ ] Investigate "TOKEN : None" message at startup (cosmetic but confusing)
- [ ] Fix NSE holiday API JSON decode failure (non-critical)

---

## 🔧 Engine Improvements

### Trade Logging
- [x] Add `trades` table to `sos_master_data.db`
- [x] Integrate `TradeLog` with DatabaseManager for real-time persistence
- [ ] Add trade entry/exit logging with timestamps and reason

### Strategy Execution
- [ ] Verify all 18 gates (strategies) are correctly loaded and evaluated
- [ ] Add regime filtering (PCR/Market Breadth) to all strategies
- [ ] Implement break-even logic for open positions
- [ ] Add trailing stop-loss functionality

### Order Orchestrator
- [ ] Fix delta calculation for option SL/TP (currently hardcoded to 0.5)
- [ ] Add support for fetching live option delta from API
- [ ] Handle multiple position management per underlying

---

## 🧪 Testing & Validation

### Backtest
- [ ] Run backtest for 2026-01-16 with all fixes applied
- [ ] Verify trades show non-zero PnL
- [ ] Compare live trades vs backtest results for same period

### Live Testing
- [ ] Monitor live engine for 10+ minutes without crashes
- [ ] Capture at least 5 new trades with correct SL/TP
- [ ] Validate exit logic (SL/TP hit, time-based exit)

---

## 📋 Code Cleanup

- [ ] Remove debug print statements from `DataManager.py`
- [ ] Remove debug print statements from `OrderOrchestrator.py`
- [ ] Remove debug print statements from `InstrumentLoader.py`
- [ ] Clean up `LiveTradingEngine.process_message` for readability
- [ ] Add proper logging (replace `print()` with `logging` module)

---

## 📚 Documentation

- [ ] Document symbol format conventions used by each provider
- [ ] Document ATR calculation logic
- [ ] Document option SL/TP delta calculation
- [ ] Create architecture diagram for data flow

---

**Last Updated:** 2026-01-16 14:11 IST
