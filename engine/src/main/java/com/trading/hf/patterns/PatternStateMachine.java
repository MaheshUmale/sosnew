package com.trading.hf.patterns;

import com.trading.hf.model.PatternDefinition;
import com.trading.hf.model.PatternState;
import com.trading.hf.model.VolumeBar;
import org.mvel2.MVEL;
import org.mvel2.ParserContext;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.Serializable;
import java.util.HashMap;
import java.util.Map;

public class PatternStateMachine {
    private static final Logger log = LoggerFactory.getLogger(PatternStateMachine.class);

    private static final Map<String, Object> IMPORTS = new HashMap<>();
    static {
        IMPORTS.put("Math", Math.class);
        try {
            IMPORTS.put("abs", Math.class.getMethod("abs", double.class));
            // Map 'round' to our custom 2-arg version. 
            IMPORTS.put("round", MVELFunctions.class.getMethod("round", double.class, int.class));
            
            // Technical Indicators accepting History + Period + Field
            IMPORTS.put("stdev", MVELFunctions.class.getMethod("stdev", java.util.List.class, int.class, String.class));
            IMPORTS.put("highest", MVELFunctions.class.getMethod("highest", java.util.List.class, int.class, String.class));
            IMPORTS.put("max", MVELFunctions.class.getMethod("max", java.util.List.class, int.class, String.class));
            IMPORTS.put("lowest", MVELFunctions.class.getMethod("lowest", java.util.List.class, int.class, String.class));
            IMPORTS.put("min", MVELFunctions.class.getMethod("min", java.util.List.class, int.class, String.class));
            IMPORTS.put("moving_avg", MVELFunctions.class.getMethod("moving_avg", java.util.List.class, int.class, String.class));
        } catch (NoSuchMethodException e) {
            log.error("Failed to import Math/MVEL methods", e);
        }
    }


    private final PatternDefinition definition;
    private final PatternState state;
    private boolean triggered = false;
    private VolumeBar prevCandle;
    // Rolling history window for technical indicators
    private final java.util.LinkedList<VolumeBar> history = new java.util.LinkedList<>();
    private static final int MAX_HISTORY = 200;

    // Compile MVEL expressions for performance
    private final Map<String, Serializable> compiledConditions = new HashMap<>();
    private final Map<String, Serializable> compiledCaptures = new HashMap<>();

    public PatternStateMachine(PatternDefinition definition, String symbol) {
        this.definition = definition;
        this.state = new PatternState(definition.getPatternId(), symbol, definition.getPhases().get(0).getId());
        compileExpressions();
    }

    public PatternStateMachine(PatternDefinition definition, String symbol, PatternState state) {
        this.definition = definition;
        this.state = state;
        compileExpressions();
    }

    private void compileExpressions() {
        for (PatternDefinition.Phase phase : definition.getPhases()) {
            if (phase.getConditions() != null) {
                for (String condition : phase.getConditions()) {
                    try {
                        // Use dynamic compilation with imports (no ParserContext strictness)
                        // Replace 'var.' with 'vars.' to avoid keyword conflict with 'var'
                        String safeCondition = condition.replace("var.", "vars.");
                        compiledConditions.put(condition, MVEL.compileExpression(safeCondition, IMPORTS));
                    } catch (Exception e) {
                        log.error("Failed to compile condition: {}", condition, e);
                    }
                }
            }
            if (phase.getCapture() != null) {
                for (Map.Entry<String, String> entry : phase.getCapture().entrySet()) {
                    try {
                        String safeExpression = entry.getValue().replace("var.", "vars.");
                        compiledCaptures.put(entry.getValue(), MVEL.compileExpression(safeExpression, IMPORTS));
                    } catch (Exception e) {
                        log.error("Failed to compile capture: {}", entry.getValue(), e);
                    }
                }
            }
        }
    }

    public void evaluate(VolumeBar candle, com.trading.hf.model.Sentiment sentiment, Map<String, Double> screenerData) {
        // Update history
        history.add(candle);
        if (history.size() > MAX_HISTORY) {
            history.removeFirst();
        }

        PatternDefinition.Phase currentPhase = getCurrentPhase();
        if (currentPhase == null) return;

        if (checkConditions(currentPhase.getConditions(), candle, sentiment, screenerData)) {
            captureVariables(currentPhase.getCapture(), candle, sentiment);
            moveToNextPhase();
        } else {
            state.incrementTimeout();
            if (state.isTimedOut(currentPhase.getTimeout())) {
                state.reset();
            }
        }
        // Update prevCandle reference
        this.prevCandle = candle;
    }

    private boolean checkConditions(java.util.List<String> conditions, VolumeBar candle, com.trading.hf.model.Sentiment sentiment, Map<String, Double> screenerData) {
        if (conditions == null || conditions.isEmpty()) return true;

        Map<String, Object> context = new HashMap<>();
        context.put("candle", candle);
        context.put("sentiment", sentiment);
        context.put("var", state.getCapturedVariables()); 
    context.put("vars", state.getCapturedVariables()); 
        context.put("screener", screenerData != null ? screenerData : new HashMap<>());
        context.put("prev_candle", this.prevCandle != null ? this.prevCandle : candle);
        context.put("history", history); // Expose history to MVEL

        // Add shorthand variables to context for identifiers like 'volume', 'close'
        context.put("volume", (double) candle.getVolume());
        context.put("close", candle.getClose());
        context.put("high", candle.getHigh());
        context.put("low", candle.getLow());
        context.put("open", candle.getOpen());

        for (String condition : conditions) {
            try {
                // Look up by ORIGINAL condition string, but it maps to 'safe' compiled expression
                Serializable compiled = compiledConditions.get(condition);
                if (compiled == null) continue;
                Boolean result = MVEL.executeExpression(compiled, context, Boolean.class);
                if (result == null || !result) {
                    return false;
                }
            } catch (Exception e) {
                log.error("Error evaluating MVEL condition: {}", condition, e);
                return false;
            }
        }
        return true;
    }

    private void captureVariables(Map<String, String> captures, VolumeBar candle, com.trading.hf.model.Sentiment sentiment) {
        if (captures == null) return;

        Map<String, Object> context = new HashMap<>();
        context.put("candle", candle);
        context.put("sentiment", sentiment);
        context.put("vars", state.getCapturedVariables()); // Changed from var to vars

        for (Map.Entry<String, String> entry : captures.entrySet()) {
            try {
                Serializable compiled = compiledCaptures.get(entry.getValue());
                if (compiled == null) continue;
                Object value = MVEL.executeExpression(compiled, context);
                if (value instanceof Number) {
                    state.capture(entry.getKey(), ((Number) value).doubleValue());
                }
            } catch (Exception e) {
                log.error("Error capturing MVEL variable: {}", entry.getKey(), e);
            }
        }
    }

    private void moveToNextPhase() {
        int currentPhaseIndex = findPhaseIndex(state.getCurrentPhaseId());
        if (currentPhaseIndex < definition.getPhases().size() - 1) {
            String nextPhaseId = definition.getPhases().get(currentPhaseIndex + 1).getId();
            state.moveTo(nextPhaseId);
        } else {
            this.triggered = true;
            log.info("TRIGGER for {} on {}", definition.getPatternId(), state.getSymbol());
        }
    }

    private PatternDefinition.Phase getCurrentPhase() {
        return definition.getPhases().stream()
                .filter(p -> p.getId().equals(state.getCurrentPhaseId()))
                .findFirst()
                .orElse(null);
    }

    private int findPhaseIndex(String phaseId) {
        for (int i = 0; i < definition.getPhases().size(); i++) {
            if (definition.getPhases().get(i).getId().equals(phaseId)) {
                return i;
            }
        }
        return -1;
    }

    public PatternState getState() {
        return state;
    }

    public PatternDefinition getDefinition() {
        return definition;
    }

    public boolean isTriggered() {
        return triggered;
    }

    public void consumeTrigger() {
        this.triggered = false;
    }
}
