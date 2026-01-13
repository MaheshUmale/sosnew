package com.trading.hf.model;

import com.trading.hf.patterns.PatternStateMachine;
import java.util.List;

public class MarketEvent {
    private MessageType type;
    private long timestamp;
    private String symbol;
    private VolumeBar candle;
    private Sentiment sentiment;
    private List<OptionChainData> optionChain;
    private java.util.Map<String, Double> screenerData; // For rvol, change_from_open
    private PatternStateMachine triggeredMachine; // Field to carry the signal

    public enum MessageType {
        MARKET_UPDATE,
        OPTION_CHAIN_UPDATE,
        SENTIMENT_UPDATE,
        CANDLE_UPDATE,
        UNKNOWN
    }

    // Getters and setters
    public MessageType getType() {
        return type;
    }

    public void setType(MessageType type) {
        this.type = type;
    }

    public long getTimestamp() {
        return timestamp;
    }

    public void setTimestamp(long timestamp) {
        this.timestamp = timestamp;
    }

    public String getSymbol() {
        return symbol;
    }

    public void setSymbol(String symbol) {
        this.symbol = symbol;
    }

    public VolumeBar getCandle() {
        return candle;
    }

    public void setCandle(VolumeBar candle) {
        this.candle = candle;
    }

    public Sentiment getSentiment() {
        return sentiment;
    }

    public void setSentiment(Sentiment sentiment) {
        this.sentiment = sentiment;
    }

    public List<OptionChainData> getOptionChain() {
        return optionChain;
    }

    public void setOptionChain(List<OptionChainData> optionChain) {
        this.optionChain = optionChain;
    }

    public java.util.Map<String, Double> getScreenerData() {
        return screenerData;
    }

    public void setScreenerData(java.util.Map<String, Double> screenerData) {
        this.screenerData = screenerData;
    }

    public PatternStateMachine getTriggeredMachine() {
        return triggeredMachine;
    }

    public void setTriggeredMachine(PatternStateMachine triggeredMachine) {
        this.triggeredMachine = triggeredMachine;
    }

    public void clear() {
        this.type = null;
        this.timestamp = 0L;
        this.symbol = null;
        this.candle = null;
        this.sentiment = null;
        this.optionChain = null;
        this.triggeredMachine = null; // Clear the signal
    }
}
