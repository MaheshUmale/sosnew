package com.trading.hf.core;

import com.trading.hf.Config;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.IOException;
import java.nio.file.*;

import static java.nio.file.StandardWatchEventKinds.*;

public class StrategyWatcher implements Runnable {
    private static final Logger log = LoggerFactory.getLogger(StrategyWatcher.class);

    private final String dirPath;
    private final PatternMatcherHandler handler;

    public StrategyWatcher(PatternMatcherHandler handler) {
        this.dirPath = Config.get("strategies.external.path");
        this.handler = handler;
    }

    @Override
    public void run() {
        if (dirPath == null || dirPath.isEmpty()) {
            log.warn("External strategies path not configured. Skipping watcher.");
            return;
        }

        Path path = Paths.get(dirPath);
        if (!Files.exists(path)) {
            try {
                Files.createDirectories(path);
            } catch (IOException e) {
                log.error("Failed to create external strategies directory: {}", dirPath, e);
                return;
            }
        }

        try (WatchService watchService = FileSystems.getDefault().newWatchService()) {
            path.register(watchService, ENTRY_CREATE, ENTRY_MODIFY, ENTRY_DELETE);
            log.info("Started StrategyWatcher on directory: {}", dirPath);

            while (!Thread.currentThread().isInterrupted()) {
                WatchKey key;
                try {
                    key = watchService.take();
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                    break;
                }

                boolean shouldReload = false;
                for (WatchEvent<?> event : key.pollEvents()) {
                    @SuppressWarnings("unchecked")
                    WatchEvent<Path> ev = (WatchEvent<Path>) event;
                    Path filename = ev.context();

                    if (filename.toString().endsWith(".json")) {
                        log.info("Detected change in strategy file: {} (Event: {})", filename, ev.kind());
                        shouldReload = true;
                    }
                }

                if (shouldReload) {
                    // Slight delay to allow file write to complete
                    Thread.sleep(500);
                    handler.reloadPatterns();
                }

                boolean valid = key.reset();
                if (!valid) {
                    log.error("WatchKey no longer valid. Stopping StrategyWatcher.");
                    break;
                }
            }
        } catch (IOException | InterruptedException e) {
            log.error("Error in StrategyWatcher", e);
        }
    }
}
