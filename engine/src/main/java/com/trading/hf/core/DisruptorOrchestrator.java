package com.trading.hf.core;

import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.lmax.disruptor.RingBuffer;
import com.lmax.disruptor.dsl.Disruptor;
import com.lmax.disruptor.util.DaemonThreadFactory;
import com.trading.hf.model.MarketEvent;
import com.trading.hf.model.MarketEventFactory;
import com.trading.hf.pnl.PnlHandler;
import com.trading.hf.ui.UIBroadcastHandler;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class DisruptorOrchestrator {
    private static final Logger log = LoggerFactory.getLogger(DisruptorOrchestrator.class);

    private final Disruptor<MarketEvent> disruptor;
    private final RingBuffer<MarketEvent> ringBuffer;
    private final ExecutorService executor;
    private final ObjectMapper objectMapper = new ObjectMapper()
            .configure(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES, false);

    @SuppressWarnings("unchecked")
    public DisruptorOrchestrator(int bufferSize, OptionChainHandler optionChainHandler, SentimentHandler sentimentHandler, PatternMatcherHandler patternMatcherHandler, ExecutionHandler executionHandler, UIBroadcastHandler uiBroadcastHandler, PnlHandler pnlHandler) {
        // 1. Create a thread pool for the consumers
        executor = Executors.newCachedThreadPool(DaemonThreadFactory.INSTANCE);

        // 2. The factory for the event
        MarketEventFactory factory = new MarketEventFactory();

        // 3. Construct the Disruptor
        disruptor = new Disruptor<>(factory, bufferSize, DaemonThreadFactory.INSTANCE);

        // 4. Connect the handlers in a chain
        disruptor.handleEventsWith(optionChainHandler)
                 .then(sentimentHandler)
                 .then(patternMatcherHandler)
                 .then(executionHandler)
                 .then(uiBroadcastHandler, pnlHandler);

        // 5. Get the ring buffer from the Disruptor to be used for publishing
        ringBuffer = disruptor.getRingBuffer();
    }

    public void start() {
        disruptor.start();
    }

    public void shutdown() {
        disruptor.shutdown();
        executor.shutdown();
    }

    public void onBridgeMessage(MarketEvent.MessageType messageType, JsonNode dataNode, long timestamp) {
        ringBuffer.publishEvent((event, sequence) -> {
            try {
                event.setType(messageType);
                event.setTimestamp(timestamp);

                switch (messageType) {
                    case MARKET_UPDATE:
                        event.setSymbol(dataNode.get("symbol").asText());
                        event.setCandle(objectMapper.treeToValue(dataNode.get("candle"), com.trading.hf.model.VolumeBar.class));
                        event.setSentiment(objectMapper.treeToValue(dataNode.get("sentiment"), com.trading.hf.model.Sentiment.class));
                        break;
                    case CANDLE_UPDATE:
                        event.setSymbol(dataNode.get("symbol").asText());
                        event.setCandle(objectMapper.treeToValue(dataNode.get("candle"), com.trading.hf.model.VolumeBar.class));
                        break;
                    case SENTIMENT_UPDATE:
                        event.setSentiment(objectMapper.treeToValue(dataNode, com.trading.hf.model.Sentiment.class));
                        break;
                    case OPTION_CHAIN_UPDATE:
                        event.setSymbol(dataNode.get("symbol").asText());
                        event.setOptionChain(objectMapper.readerFor(new com.fasterxml.jackson.core.type.TypeReference<java.util.List<com.trading.hf.model.OptionChainData>>() {}).readValue(dataNode.get("chain")));
                        break;
                    default:
                        log.warn("Unknown message type: {}", messageType);
                        break;
                }
            } catch (Exception e) {
                log.error("Error processing message in Disruptor event handler: {}", dataNode, e);
            }
        });
    }
}
