package com.trading.hf.core;

import com.lmax.disruptor.EventHandler;
import com.trading.hf.model.MarketEvent;
import com.trading.hf.model.OptionChainData;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

public class OptionChainHandler implements EventHandler<MarketEvent> {

    private static final Logger log = LoggerFactory.getLogger(OptionChainHandler.class);
    private static final Map<Integer, OptionChainData> latestOptionChain = new ConcurrentHashMap<>();

    @Override
    public void onEvent(MarketEvent event, long sequence, boolean endOfBatch) throws Exception {
        if (event.getType() == MarketEvent.MessageType.OPTION_CHAIN_UPDATE) {
            try {
                List<OptionChainData> chainData = event.getOptionChain();
                if (chainData != null) {
                    for (OptionChainData data : chainData) {
                        latestOptionChain.put(data.getStrike(), data);
                    }
                    log.info("Successfully processed and updated option chain data for {} strikes.", chainData.size());
                }
            } catch (Exception e) {
                log.error("Failed to process OPTION_CHAIN_UPDATE event", e);
            }
        }
    }

    public static Map<Integer, OptionChainData> getLatestOptionChain() {
        return latestOptionChain;
    }
}
