package com.trading.hf.core;

import com.lmax.disruptor.EventHandler;
import com.trading.hf.model.MarketEvent;
import com.trading.hf.model.Sentiment;

public class SentimentHandler implements EventHandler<MarketEvent> {

    @Override
    public void onEvent(MarketEvent event, long sequence, boolean endOfBatch) throws Exception {
        if (event.getType() == MarketEvent.MessageType.MARKET_UPDATE || event.getType() == MarketEvent.MessageType.SENTIMENT_UPDATE) {
            Sentiment sentiment = event.getSentiment();
            if (sentiment != null) {
                String regime = sentiment.getRegime();
                if (regime == null) {
                    // Only determine regime if it wasn't provided
                    regime = determineRegime(sentiment);
                    sentiment.setRegime(regime);
                }
                GlobalRegimeController.setRegime(regime);
            }
        }
    }

    private static final double PCR_EXTREME_BULLISH = 0.7;
    private static final double PCR_EXTREME_BEARISH = 1.3;
    private static final double PCR_NEUTRAL = 1.0;

    private String determineRegime(Sentiment sentiment) {
        // Simple logic for demonstration purposes. A real implementation would be more complex.
        double pcr = sentiment.getPcr();
        if (pcr < PCR_EXTREME_BULLISH) {
            return "COMPLETE_BULLISH";
        } else if (pcr < PCR_NEUTRAL) {
            return "BULLISH";
        } else if (pcr > PCR_EXTREME_BEARISH) {
            return "COMPLETE_BEARISH";
        } else if (pcr > PCR_NEUTRAL) {
            return "BEARISH";
        } else {
            return "SIDEWAYS";
        }
    }
}
