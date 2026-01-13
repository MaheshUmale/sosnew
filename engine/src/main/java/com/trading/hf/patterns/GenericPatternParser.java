package com.trading.hf.patterns;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.trading.hf.model.PatternDefinition;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.util.HashMap;
import java.util.Map;
import java.util.stream.Collectors;


public class GenericPatternParser {
    private static final Logger log = LoggerFactory.getLogger(GenericPatternParser.class);

    private final ObjectMapper objectMapper = new ObjectMapper();

    public Map<String, PatternDefinition> loadPatterns(String directoryPath) {
        Map<String, PatternDefinition> patterns = new HashMap<>();

        try (
                InputStream in = getClass().getClassLoader().getResourceAsStream(directoryPath);
                BufferedReader br = new BufferedReader(new InputStreamReader(in))) {
            String resource;
            while (br != null && (resource = br.readLine()) != null) {
                if (resource.endsWith(".json")) {
                    try (InputStream jsonStream = getClass().getClassLoader()
                            .getResourceAsStream(directoryPath + "/" + resource)) {
                        if (jsonStream == null) {
                            log.error("Cannot find resource: {}", resource);
                            continue;
                        }
                        PatternDefinition definition = objectMapper.readValue(jsonStream, PatternDefinition.class);
                        patterns.put(definition.getPatternId(), definition);
                        log.info("Loaded pattern from classpath: {}", definition.getPatternId());
                    } catch (IOException e) {
                        log.error("Error parsing pattern file from classpath: {}", resource, e);
                    }
                }
            }
        } catch (IOException | NullPointerException e) {
            log.warn("Could not read strategies from classpath directory: {}. This might be expected if running from IDE.", directoryPath);
        }

        return patterns;
    }

    public Map<String, PatternDefinition> loadPatternsFromDir(String dirPath) {
        Map<String, PatternDefinition> patterns = new HashMap<>();
        java.io.File folder = new java.io.File(dirPath);
        if (!folder.exists() || !folder.isDirectory()) {
            log.warn("External strategies directory does not exist or is not a directory: {}", dirPath);
            return patterns;
        }

        java.io.File[] listOfFiles = folder.listFiles((dir, name) -> name.endsWith(".json"));
        if (listOfFiles != null) {
            for (java.io.File file : listOfFiles) {
                try {
                    PatternDefinition definition = objectMapper.readValue(file, PatternDefinition.class);
                    patterns.put(definition.getPatternId(), definition);
                    log.info("Loaded pattern from filesystem: {}", definition.getPatternId());
                } catch (IOException e) {
                    log.error("Error parsing pattern file from filesystem: {}", file.getName(), e);
                }
            }
        }
        return patterns;
    }
}
