package com.trading.hf.core;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.concurrent.atomic.AtomicReference;

public class GlobalRegimeController {
    private static final Logger log = LoggerFactory.getLogger(GlobalRegimeController.class);

    public enum MarketRegime {
        COMPLETE_BULLISH,
        BULLISH,
        SIDEWAYS_BULLISH,
        SIDEWAYS,
        SIDEWAYS_BEARISH,
        BEARISH,
        COMPLETE_BEARISH,
        UNKNOWN // Default initial state
    }

    private static final AtomicReference<MarketRegime> currentRegime = new AtomicReference<>(MarketRegime.UNKNOWN);

    public static void setRegime(String regimeString) {
        try {
            MarketRegime newRegime = MarketRegime.valueOf(regimeString.toUpperCase());
            currentRegime.set(newRegime);
            log.info("Market regime updated to: {}", newRegime);
        } catch (IllegalArgumentException e) {
            log.warn("Invalid market regime received: {}", regimeString);
            currentRegime.set(MarketRegime.UNKNOWN);
        }
    }

    public static MarketRegime getRegime() {
        return currentRegime.get();
    }
}
