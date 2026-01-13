package com.trading.hf.ui;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.lmax.disruptor.EventHandler;
import com.trading.hf.model.MarketEvent;

public class UIBroadcastHandler implements EventHandler<MarketEvent> {

    private final UISWebSocketServer webSocketServer;
    private final ObjectMapper objectMapper = new ObjectMapper();

    public UIBroadcastHandler(UISWebSocketServer webSocketServer) {
        this.webSocketServer = webSocketServer;
    }

    @Override
    public void onEvent(MarketEvent event, long sequence, boolean endOfBatch) throws Exception {
        // Broadcast ALL events to the UI so it's not empty
        try {
            String jsonEvent = objectMapper.writeValueAsString(event);
            webSocketServer.broadcast(jsonEvent);
        } catch (Exception e) {
            // Log the error, but don't stop the disruptor
        }
    }
}
