package com.trading.hf.execution;

import com.trading.hf.core.GlobalRegimeController;
import com.trading.hf.core.PriceRegistry;
import com.trading.hf.model.PatternDefinition;
import com.trading.hf.model.PatternState;
import com.trading.hf.pnl.PortfolioManager;
import com.trading.hf.pnl.Trade;
import org.mvel2.MVEL;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.Serializable;
import java.util.HashMap;
import java.util.Map;

public class OrderOrchestrator {
    private static final Logger log = LoggerFactory.getLogger(OrderOrchestrator.class);
    private final PortfolioManager portfolioManager;
    private final OptionContractResolver optionResolver = new OptionContractResolver();

    public OrderOrchestrator(PortfolioManager portfolioManager) {
        this.portfolioManager = portfolioManager;
    }

    public void executeTrade(PatternState triggeredState, PatternDefinition definition) {
        // 1. Get the current market regime and config
        GlobalRegimeController.MarketRegime regime = GlobalRegimeController.getRegime();
        PatternDefinition.RegimeConfig regimeConfig = definition.getRegimeConfig().get(regime.name());

        // 2. Check if the pattern is allowed in the current regime
        if (regimeConfig != null && !regimeConfig.isAllowEntry()) {
            log.info("Execution VETOED: Pattern {} is not allowed in {} regime.", definition.getPatternId(), regime);
            return;
        }

        // 3. Create the execution context for MVEL
        Map<String, Object> context = new HashMap<>();
        context.put("var", triggeredState.getCapturedVariables());
        context.put("vars", triggeredState.getCapturedVariables());
        if (regimeConfig != null) {
            context.put("tp_mult", regimeConfig.getTpMult());
            context.put("quantity_mod", regimeConfig.getQuantityMod());
        } else {
            context.put("tp_mult", 1.0);
            context.put("quantity_mod", 1.0);
        }

        try {
            // 4. Evaluate entry and stop-loss first to calculate risk
            double underlyingEntry = MVEL.eval(definition.getExecution().getEntry(), context, Double.class);
            double underlyingSL = MVEL.eval(definition.getExecution().getSl(), context, Double.class);
            Trade.TradeSide underlyingSide = Trade.TradeSide.valueOf(definition.getExecution().getSide());

            double underlyingRisk = Math.abs(underlyingEntry - underlyingSL);
            context.put("entry", underlyingEntry);
            context.put("risk", underlyingRisk);

            // 5. Evaluate underlying take-profit
            double underlyingTP = MVEL.eval(definition.getExecution().getTp(), context, Double.class);

            // 6. Calculate base underlying quantity
            double baseQuantity = 100;
            double finalQuantity = baseQuantity * (double) context.get("quantity_mod");

            String symbolToTrade = triggeredState.getSymbol();
            double tradeEntry = underlyingEntry;
            double tradeSL = underlyingSL;
            double tradeTP = underlyingTP;
            Trade.TradeSide tradeSide = underlyingSide;

            // 7. Resolve to Option if it's NIFTY or BANKNIFTY (Exact match only to avoid triggering on options themselves)
            if (symbolToTrade.equals("NIFTY") || symbolToTrade.equals("BANKNIFTY")) {
                String optionSymbol = optionResolver.resolveATM(symbolToTrade, underlyingEntry, underlyingSide.name(), 0);
                double optionPrice = PriceRegistry.getPrice(optionSymbol);
                
                if (optionPrice > 0) {
                    log.info("Switching to OPTION Trade: {} -> {} @ {}", symbolToTrade, optionSymbol, optionPrice);
                    symbolToTrade = optionSymbol;
                    tradeEntry = optionPrice;
                    tradeSide = Trade.TradeSide.LONG; // We are always BUYING the option (CE or PE)
                    
                    // Simple option exit logic: exit when underlying hits SL/TP levels 
                    // To do this simply in current PortfolioManager, we set an wide SL/TP or estimate 
                    // delta-based SL/TP on the option price itself.
                    // For now, let's use a 50% relative risk logic for the option itself.
                    double priceMovementFactor = Math.abs(underlyingTP - underlyingEntry) / underlyingEntry;
                    double riskMovementFactor = Math.abs(underlyingSL - underlyingEntry) / underlyingEntry;
                    
                    tradeSL = tradeEntry * (1 - (riskMovementFactor * 5)); // Aggressive 5x levered SL
                    tradeTP = tradeEntry * (1 + (priceMovementFactor * 5)); // Aggressive 5x levered TP
                } else {
                    log.warn("Option price for {} not found in PriceRegistry. Falling back to Underlying.", optionSymbol);
                }
            }

            log.info("[EXEC_DATA] Side={}, Symbol={}, Qty={}, Price={}, SL={}, TP={}, Gate={}", 
                    tradeSide, symbolToTrade, finalQuantity, tradeEntry, tradeSL, tradeTP, definition.getPatternId());
            log.info("--------------------------");

            portfolioManager.newTrade(symbolToTrade, tradeEntry, tradeSL, tradeTP, finalQuantity, tradeSide, definition.getPatternId());

        } catch (Exception e) {
            log.error("Error evaluating execution logic for pattern {}", definition.getPatternId(), e);
        }
    }
}
