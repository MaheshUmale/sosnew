package com.trading.hf.core;

import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

public class PriceRegistry {
    private static final Map<String, Double> latestPrices = new ConcurrentHashMap<>();

    public static void updatePrice(String symbol, double price) {
        latestPrices.put(symbol, price);
    }

    public static double getPrice(String symbol) {
        return latestPrices.getOrDefault(symbol, 0.0);
    }
}
