package com.trading.hf.state;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.trading.hf.model.PatternState;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.File;
import java.io.IOException;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

public class RecoveryManager {
    private static final Logger log = LoggerFactory.getLogger(RecoveryManager.class);

    private static final String STATE_FILE = "sos_engine_state.json";
    private final ObjectMapper objectMapper = new ObjectMapper();

    public void saveState(Map<String, PatternState> activeStates) {
        try {
            objectMapper.writeValue(new File(STATE_FILE), activeStates);
            log.info("Engine state saved.");
        } catch (IOException e) {
            log.error("Error saving engine state:", e);
        }
    }

    public Map<String, PatternState> loadState() {
        File file = new File(STATE_FILE);
        if (file.exists()) {
            try {
                Map<String, PatternState> loadedStates = objectMapper.readValue(file, new TypeReference<Map<String, PatternState>>() {});
                log.info("Engine state loaded.");
                return new ConcurrentHashMap<>(loadedStates);
            } catch (IOException e) {
                log.error("Error loading engine state:", e);
            }
        }
        log.info("No saved state found, starting fresh.");
        return new ConcurrentHashMap<>();
    }
}
