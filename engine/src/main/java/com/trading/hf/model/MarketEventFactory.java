package com.trading.hf.model;

import com.lmax.disruptor.EventFactory;

public class MarketEventFactory implements EventFactory<MarketEvent> {
    @Override
    public MarketEvent newInstance() {
        return new MarketEvent();
    }
}
