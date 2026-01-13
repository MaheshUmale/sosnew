package com.trading.hf.model;

import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

public class PatternState {

    private final String patternId;
    private final String symbol;
    private String currentPhaseId;
    private final Map<String, Double> capturedVariables;
    private int timeoutCounter;

    public PatternState(String patternId, String symbol, String initialPhaseId) {
        this.patternId = patternId;
        this.symbol = symbol;
        this.currentPhaseId = initialPhaseId;
        this.capturedVariables = new ConcurrentHashMap<>();
        this.timeoutCounter = 0;
    }

    @JsonCreator
    public PatternState(
            @JsonProperty("patternId") String patternId,
            @JsonProperty("symbol") String symbol,
            @JsonProperty("currentPhaseId") String currentPhaseId,
            @JsonProperty("capturedVariables") Map<String, Double> capturedVariables,
            @JsonProperty("timeoutCounter") int timeoutCounter) {
        this.patternId = patternId;
        this.symbol = symbol;
        this.currentPhaseId = currentPhaseId;
        this.capturedVariables = new ConcurrentHashMap<>(capturedVariables);
        this.timeoutCounter = timeoutCounter;
    }

    public String getPatternId() {
        return patternId;
    }

    public String getSymbol() {
        return symbol;
    }

    public String getCurrentPhaseId() {
        return currentPhaseId;
    }

    public void moveTo(String nextPhaseId) {
        this.currentPhaseId = nextPhaseId;
        this.timeoutCounter = 0; // Reset timeout when moving to a new phase
    }

    public void capture(String variableName, double value) {
        capturedVariables.put(variableName, value);
    }

    public Double getVariable(String variableName) {
        // The key in the map might be "var.mother_h", so we strip "var."
        String key = variableName.startsWith("var.") ? variableName.substring(4) : variableName;
        return capturedVariables.get(key);
    }

    public Map<String, Double> getCapturedVariables() {
        return capturedVariables;
    }

    public int getTimeoutCounter() {
        return timeoutCounter;
    }

    public void reset() {
        // Reset to the initial state, clearing variables and phase
        this.currentPhaseId = "SETUP"; // Or get the initial phase from the definition
        this.capturedVariables.clear();
        this.timeoutCounter = 0;
    }

    public void incrementTimeout() {
        this.timeoutCounter++;
    }

    public boolean isTimedOut(int timeout) {
        return timeout > 0 && this.timeoutCounter >= timeout;
    }
}
