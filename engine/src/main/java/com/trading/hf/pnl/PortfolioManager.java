package com.trading.hf.pnl;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.trading.hf.model.VolumeBar;
import com.trading.hf.ui.UISWebSocketServer;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.CopyOnWriteArrayList;

public class PortfolioManager {
    private static final Logger log = LoggerFactory.getLogger(PortfolioManager.class);

    private final List<Trade> trades = new CopyOnWriteArrayList<>();
    private final UISWebSocketServer uiWebSocketServer;
    private final ObjectMapper objectMapper = new ObjectMapper();

    public PortfolioManager(UISWebSocketServer uiWebSocketServer) {
        this.uiWebSocketServer = uiWebSocketServer;
    }

    public void newTrade(String symbol, double entry, double sl, double tp, double quantity, Trade.TradeSide side, String gate) {
        trades.add(new Trade(symbol, entry, sl, tp, quantity, side, gate));
    }

    public void onCandle(VolumeBar candle) {
        List<Trade> closedTrades = new ArrayList<>();
        double totalPnl = 0.0;
        for (Trade trade : trades) {
            if (trade.isOpen()) {
                if (candle.getSymbol().equals(trade.getSymbol())) {
                    boolean close = false;
                    if (trade.getSide() == Trade.TradeSide.LONG) {
                        if (candle.getClose() <= trade.getStopLoss() || candle.getClose() >= trade.getTakeProfit()) {
                            close = true;
                        }
                    } else { // SHORT
                        if (candle.getClose() >= trade.getStopLoss() || candle.getClose() <= trade.getTakeProfit()) {
                            close = true;
                        }
                    }
                    if (close) {
                        trade.close(candle.getClose());
                        closedTrades.add(trade);
                        String reason = (trade.getSide() == Trade.TradeSide.LONG) ? 
                                (candle.getClose() >= trade.getTakeProfit() ? "TP_HIT" : "SL_HIT") :
                                (candle.getClose() <= trade.getTakeProfit() ? "TP_HIT" : "SL_HIT");
                        
                        log.info("[EXIT_DATA] Side={}, Symbol={}, Price={}, Reason={}, PnL={}, Gate={}", 
                                trade.getSide(), trade.getSymbol(), candle.getClose(), reason, trade.getPnl(), trade.getGate());
                    }
                }
            }
            if (!trade.isOpen()) {
                totalPnl += trade.getPnl();
            }
        }
        trades.removeAll(closedTrades);

        try {
            String pnlUpdate = objectMapper.writeValueAsString(new PnlUpdate(totalPnl, trades.size()));
            uiWebSocketServer.broadcast(pnlUpdate);
        } catch (Exception e) {
            // log error
        }
    }

    private static class PnlUpdate {
        public final String type = "PNL_UPDATE";
        public final double totalPnl;
        public final int openTrades;

        public PnlUpdate(double totalPnl, int openTrades) {
            this.totalPnl = totalPnl;
            this.openTrades = openTrades;
        }
    }
}
