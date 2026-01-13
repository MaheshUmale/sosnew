package com.trading.hf.patterns;

import com.trading.hf.model.VolumeBar;
import java.util.List;
import java.util.stream.Collectors;

public class MVELFunctions {
    
    // Calculate Standard Deviation over the last 'period' bars for a specific field
    public static double stdev(List<VolumeBar> history, int period, String field) {
        if (history == null || history.size() < 2) return 0.0;
        
        List<Double> values = extractLastN(history, period, field);
        if (values.isEmpty()) return 0.0;

        double mean = values.stream().mapToDouble(Double::doubleValue).average().orElse(0.0);
        double variance = values.stream().mapToDouble(v -> Math.pow(v - mean, 2)).average().orElse(0.0);
        
        return Math.sqrt(variance);
    }

    // Calculate Highest value over the last 'period' bars for a specific field
    public static double highest(List<VolumeBar> history, int period, String field) {
        if (history == null || history.isEmpty()) return 0.0;
        
        List<Double> values = extractLastN(history, period, field);
        return values.stream().mapToDouble(Double::doubleValue).max().orElse(0.0);
    }
    
    // Calculate Max (synonym for highest)
    public static double max(List<VolumeBar> history, int period, String field) {
        return highest(history, period, field);
    }

    // Calculate Lowest value over the last 'period' bars for a specific field
    public static double lowest(List<VolumeBar> history, int period, String field) {
        if (history == null || history.isEmpty()) return 0.0;
        
        List<Double> values = extractLastN(history, period, field);
        return values.stream().mapToDouble(Double::doubleValue).min().orElse(0.0);
    }
    
    // Calculate Min (synonym for lowest)
    public static double min(List<VolumeBar> history, int period, String field) {
        return lowest(history, period, field);
    }
    
    // Calculate Simple Moving Average (SMA)
    public static double sma(List<VolumeBar> history, int period, String field) {
         if (history == null || history.isEmpty()) return 0.0;
         
         List<Double> values = extractLastN(history, period, field);
         return values.stream().mapToDouble(Double::doubleValue).average().orElse(0.0);
    }
    
    // Deprecated alias for compatibility if needed, but 'moving_avg' usually implies SMA
    public static double moving_avg(List<VolumeBar> history, int period, String field) {
        return sma(history, period, field);
    }

    // Custom round with scale
    public static double round(double value, int scale) {
        if (scale >= 0) {
            double factor = Math.pow(10, scale);
            return Math.round(value * factor) / factor;
        } else {
            double factor = Math.pow(10, -scale);
            return Math.round(value / factor) * factor;
        }
    }
    
    // Helper to extract the last N values for a field
    private static List<Double> extractLastN(List<VolumeBar> history, int n, String field) {
        int size = history.size();
        int start = Math.max(0, size - n);
        List<VolumeBar> subList = history.subList(start, size);
        
        return subList.stream().map(bar -> {
            switch (field.toLowerCase()) {
                case "close": return bar.getClose();
                case "high": return bar.getHigh();
                case "low": return bar.getLow();
                case "open": return bar.getOpen();
                case "volume": return (double) bar.getVolume();
                case "atr": return bar.getATR();
                default: return 0.0;
            }
        }).collect(Collectors.toList());
    }
}
