package com.trading.hf.execution;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.time.LocalDate;
import java.time.format.DateTimeFormatter;
import java.util.Locale;

public class OptionContractResolver {
    private static final Logger log = LoggerFactory.getLogger(OptionContractResolver.class);
    private static final DateTimeFormatter SYMBOL_DATE_FORMAT = DateTimeFormatter.ofPattern("dd MMM yy", Locale.ENGLISH);

    /**
     * Resolves the trading symbol for the ATM option based on underlying price and side.
     * Underlying NIFTY LONG -> Buy ATM CALL
     * Underlying NIFTY SHORT -> Buy ATM PUT
     * 
     * @param underlyingSymbol The underlying index (NIFTY/BANKNIFTY)
     * @param spotPrice The current spot price of the underlying
     * @param side The direction of the underlying signal
     * @param offset Offset from ATM (0=ATM, 1=OTM_1, etc.)
     * @return Resolved trading symbol (e.g., "NIFTY 25650 CE 13 JAN 26")
     */
    public String resolveATM(String underlyingSymbol, double spotPrice, String side, int offset) {
        String cleanSymbol = underlyingSymbol.toUpperCase();
        if (cleanSymbol.contains("NIFTY")) {
            if (cleanSymbol.contains("BANK")) {
                return resolveForIndex("BANKNIFTY", spotPrice, side, 100, offset);
            } else {
                return resolveForIndex("NIFTY", spotPrice, side, 50, offset);
            }
        }
        return underlyingSymbol; // Fallback to equity if not an index
    }

    private String resolveForIndex(String baseName, double spotPrice, String side, int strikeStep, int offset) {
        int atmStrike = (int) (Math.round(spotPrice / strikeStep) * strikeStep);
        
        // Adjust for OTM offset if requested
        if (offset != 0) {
            if ("LONG".equals(side)) {
                atmStrike += (offset * strikeStep);
            } else {
                atmStrike -= (offset * strikeStep);
            }
        }

        String optionType = "LONG".equals(side) ? "CE" : "PE";
        
        // In a real system, we'd look up the exact expiry from a Master or Option Chain.
        // For backtest purposes on 2026-01-12, the nearest weekly expiry for NIFTY is 13 JAN 26.
        // For BANKNIFTY on 2026-01-12, the nearest weekly expiry is 27 JAN 26.
        String expiryStr;
        if ("NIFTY".equals(baseName)) {
            expiryStr = "13 JAN 26";
        } else {
             expiryStr = "27 JAN 26";
        }

        String resolved = String.format("%s %d %s %s", baseName, atmStrike, optionType, expiryStr);
        log.info("Resolved Option Contract: {} Spot={} -> ATM Symbol={}", baseName, spotPrice, resolved);
        return resolved;
    }
}
