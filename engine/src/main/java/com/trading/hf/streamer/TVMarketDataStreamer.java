package com.trading.hf.streamer;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.trading.hf.core.DisruptorOrchestrator;
import com.trading.hf.model.MarketEvent;
import com.trading.hf.model.OptionChainData;
import com.trading.hf.model.Sentiment;
import com.trading.hf.model.VolumeBar;
import org.java_websocket.client.WebSocketClient;
import org.java_websocket.handshake.ServerHandshake;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.net.URI;
import java.util.List;

public class TVMarketDataStreamer extends WebSocketClient {
    private static final Logger log = LoggerFactory.getLogger(TVMarketDataStreamer.class);

    private final DisruptorOrchestrator disruptorOrchestrator;
    private final ObjectMapper objectMapper = new ObjectMapper()
            .configure(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES, false);

    public TVMarketDataStreamer(URI serverUri, DisruptorOrchestrator disruptorOrchestrator) {
        super(serverUri);
        this.disruptorOrchestrator = disruptorOrchestrator;
    }

    @Override
    public void onOpen(ServerHandshake handshakedata) {
        log.info("Connected to Python Bridge at {}", getURI());
    }

    @Override
    public void onMessage(String message) {
        log.debug("Received message: {}", message);
        try {
            JsonNode rootNode = objectMapper.readTree(message);
            String typeStr = rootNode.get("type").asText().toUpperCase();
            MarketEvent.MessageType messageType;
            try {
                messageType = MarketEvent.MessageType.valueOf(typeStr);
            } catch (IllegalArgumentException e) {
                messageType = MarketEvent.MessageType.UNKNOWN;
            }
            JsonNode dataNode = rootNode.get("data");
            long timestamp = rootNode.get("timestamp").asLong();

            disruptorOrchestrator.onBridgeMessage(messageType, dataNode, timestamp);

        } catch (Exception e) {
            log.error("Error processing message: {}", message, e);
        }
    }

    @Override
    public void onClose(int code, String reason, boolean remote) {
        log.info("Disconnected from Python Bridge. Reason: {}", reason);
    }

    @Override
    public void onError(Exception ex) {
        log.error("WebSocket error:", ex);
    }
}
