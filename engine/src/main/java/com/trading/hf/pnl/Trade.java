package com.trading.hf.pnl;

public class Trade {
    public enum TradeSide {
        LONG, SHORT
    }
    private final String symbol;
    private final double entryPrice;
    private final double stopLoss;
    private final double takeProfit;
    private final double quantity;
    private final TradeSide side;
    private double pnl = 0.0;
    private boolean open = true;
    private final String gate;
    private final long timestamp;

    public Trade(String symbol, double entryPrice, double stopLoss, double takeProfit, double quantity, TradeSide side, String gate) {
        this.symbol = symbol;
        this.entryPrice = entryPrice;
        this.stopLoss = stopLoss;
        this.takeProfit = takeProfit;
        this.quantity = quantity;
        this.side = side;
        this.gate = gate;
        this.timestamp = System.currentTimeMillis();
    }

    public String getSymbol() {
        return symbol;
    }

    public boolean isOpen() {
        return open;
    }

    public void close(double exitPrice) {
        if (side == TradeSide.LONG) {
            this.pnl = (exitPrice - entryPrice) * quantity;
        } else {
            this.pnl = (entryPrice - exitPrice) * quantity;
        }
        this.open = false;
    }

    public double getStopLoss() {
        return stopLoss;
    }

    public double getTakeProfit() {
        return takeProfit;
    }

    public double getPnl() {
        return pnl;
    }

    public TradeSide getSide() {
        return side;
    }
    public String getGate() {
        return gate;
    }
}
