package com.trading.hf.pnl;

import com.lmax.disruptor.EventHandler;
import com.trading.hf.model.MarketEvent;
import com.trading.hf.model.VolumeBar;

public class PnlHandler implements EventHandler<MarketEvent> {

    private final PortfolioManager portfolioManager;

    public PnlHandler(PortfolioManager portfolioManager) {
        this.portfolioManager = portfolioManager;
    }

    @Override
    public void onEvent(MarketEvent event, long sequence, boolean endOfBatch) throws Exception {
        if (event.getType() == MarketEvent.MessageType.MARKET_UPDATE || event.getType() == MarketEvent.MessageType.CANDLE_UPDATE) {
            VolumeBar candle = event.getCandle();
            if (candle != null) {
                candle.setSymbol(event.getSymbol());
                portfolioManager.onCandle(candle);
            }
        }
    }
}
