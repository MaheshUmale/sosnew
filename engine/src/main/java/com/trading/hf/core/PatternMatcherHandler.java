package com.trading.hf.core;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.lmax.disruptor.EventHandler;
import com.trading.hf.model.MarketEvent;
import com.trading.hf.model.PatternDefinition;
import com.trading.hf.model.PatternState;
import com.trading.hf.model.VolumeBar;
import com.trading.hf.patterns.GenericPatternParser;
import com.trading.hf.patterns.PatternStateMachine;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

public class PatternMatcherHandler implements EventHandler<MarketEvent> {
    private static final Logger log = LoggerFactory.getLogger(PatternMatcherHandler.class);

    private volatile Map<String, PatternDefinition> patternDefinitions;
    private final Map<String, PatternStateMachine> activeStateMachines = new ConcurrentHashMap<>();
    private final ObjectMapper objectMapper = new ObjectMapper();
    private final GenericPatternParser parser = new GenericPatternParser();

    public PatternMatcherHandler() {
        // Load all pattern definitions on startup
        reloadPatterns();
    }

    public synchronized void reloadPatterns() {
        log.info("Reloading pattern definitions...");
        Map<String, PatternDefinition> classpathPatterns = parser.loadPatterns("strategies");
        
        String externalPath = com.trading.hf.Config.get("strategies.external.path");
        Map<String, PatternDefinition> externalPatterns = new java.util.HashMap<>();
        if (externalPath != null) {
            externalPatterns = parser.loadPatternsFromDir(externalPath);
        }

        // Merge patterns, external takes precedence if ID matches
        Map<String, PatternDefinition> merged = new java.util.HashMap<>(classpathPatterns);
        merged.putAll(externalPatterns);
        
        this.patternDefinitions = merged;
        log.info("Total patterns loaded: {}", merged.size());
    }

    @Override
    public void onEvent(MarketEvent event, long sequence, boolean endOfBatch) throws Exception {
        // Clear any trigger from a previous event in the same slot
        event.setTriggeredMachine(null);

        if (event.getType() == MarketEvent.MessageType.MARKET_UPDATE || event.getType() == MarketEvent.MessageType.CANDLE_UPDATE) {
            VolumeBar candle = event.getCandle();
            if (candle != null) {
                String symbol = event.getSymbol();
                if (symbol.equals("NIFTY") || symbol.equals("BANKNIFTY")) {
                    log.info("Processing Index Candle: {} @ {}", symbol, candle.getClose());
                }
                candle.setSymbol(symbol);
                PriceRegistry.updatePrice(symbol, candle.getClose());
                
                // Mock screener data if missing (TEMPORARY for testing)
                if (event.getScreenerData() == null) {
                    java.util.Map<String, Double> mockScreener = new java.util.HashMap<>();
                    mockScreener.put("rvol", 3.0);
                    mockScreener.put("change_from_open", 1.5);
                    event.setScreenerData(mockScreener);
                }

                // For each defined pattern, check or create a state machine
                for (PatternDefinition definition : patternDefinitions.values()) {
                    String machineKey = symbol + ":" + definition.getPatternId();
                    PatternStateMachine stateMachine = activeStateMachines.computeIfAbsent(machineKey,
                            k -> new PatternStateMachine(definition, symbol));

                    // Evaluate the current candle against the state machine
                    stateMachine.evaluate(candle, event.getSentiment(), event.getScreenerData());

                    // If the final phase is completed, pass the machine to the next handler
                    if (stateMachine.isTriggered()) {
                        event.setTriggeredMachine(stateMachine);
                        stateMachine.consumeTrigger(); // Reset trigger flag
                        // We break after the first trigger for a symbol to avoid multiple signals
                        break;
                    }
                }
            }
        }
    }

    public Map<String, PatternStateMachine> getActiveStateMachines() {
        return activeStateMachines;
    }

    public void restoreState(Map<String, PatternState> savedStates) {
        for (Map.Entry<String, PatternState> entry : savedStates.entrySet()) {
            String machineKey = entry.getKey();
            PatternState savedState = entry.getValue();
            PatternDefinition definition = patternDefinitions.get(savedState.getPatternId());
            if (definition != null) {
                // Create a new state machine with the loaded state
                PatternStateMachine stateMachine = new PatternStateMachine(definition, savedState.getSymbol(), savedState);
                activeStateMachines.put(machineKey, stateMachine);
            } else {
                log.warn("Could not find pattern definition for loaded state: {}", savedState.getPatternId());
            }
        }
    }
}
