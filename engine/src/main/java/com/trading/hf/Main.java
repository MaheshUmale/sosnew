package com.trading.hf;

import com.trading.hf.core.*;
import com.trading.hf.execution.OrderOrchestrator;
import com.trading.hf.model.PatternState;
import com.trading.hf.patterns.PatternStateMachine;
import com.trading.hf.pnl.PnlHandler;
import com.trading.hf.pnl.PortfolioManager;
import com.trading.hf.state.RecoveryManager;
import com.trading.hf.streamer.TVMarketDataStreamer;
import com.trading.hf.ui.UIBroadcastHandler;
import com.trading.hf.ui.UISWebSocketServer;
import com.trading.hf.ui.WebServer;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.net.URI;
import java.net.URISyntaxException;
import java.util.Map;
import java.util.stream.Collectors;

public class Main {
    private static final Logger log = LoggerFactory.getLogger(Main.class);

    public static void main(String[] args) {
        // 1. Initialize core components
        RecoveryManager recoveryManager = new RecoveryManager();

        // 2. Start UI Servers
        WebServer webServer = new WebServer();
        webServer.start();
        UISWebSocketServer uiWebSocketServer = new UISWebSocketServer(8081);
        uiWebSocketServer.start();

        PortfolioManager portfolioManager = new PortfolioManager(uiWebSocketServer);
        OrderOrchestrator orderOrchestrator = new OrderOrchestrator(portfolioManager);

        // 3. Set up the Disruptor handlers
        OptionChainHandler optionChainHandler = new OptionChainHandler();
        SentimentHandler sentimentHandler = new SentimentHandler();
        PatternMatcherHandler patternMatcherHandler = new PatternMatcherHandler();
        ExecutionHandler executionHandler = new ExecutionHandler(orderOrchestrator);
        UIBroadcastHandler uiBroadcastHandler = new UIBroadcastHandler(uiWebSocketServer);
        PnlHandler pnlHandler = new PnlHandler(portfolioManager);

        // 4. Initialize the Disruptor orchestrator
        int bufferSize = Config.getInt("disruptor.bufferSize", 1024);
        DisruptorOrchestrator orchestrator = new DisruptorOrchestrator(
                bufferSize,
                optionChainHandler,
                sentimentHandler,
                patternMatcherHandler,
                executionHandler,
                uiBroadcastHandler,
                pnlHandler
        );

        // 5. Add a shutdown hook to save the state on exit
        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            log.info("Shutting down... saving state.");
            if (patternMatcherHandler != null && recoveryManager != null && orchestrator != null) {
                // Convert the map of state machines to a map of states for persistence
                Map<String, PatternState> statesToSave = patternMatcherHandler.getActiveStateMachines().entrySet().stream()
                        .collect(Collectors.toMap(Map.Entry::getKey, e -> e.getValue().getState()));
                recoveryManager.saveState(statesToSave);
                orchestrator.shutdown();
            }
        }));

        // 6. Start the Disruptor
        orchestrator.start();
        log.info("DisruptorOrchestrator started with buffer size {}.", bufferSize);

        // 7. Start Strategy Watcher for dynamic reloading
        StrategyWatcher strategyWatcher = new StrategyWatcher(patternMatcherHandler);
        Thread watcherThread = new Thread(strategyWatcher, "StrategyWatcher");
        watcherThread.setDaemon(true);
        watcherThread.start();

        // 8. Load previous state (if any)
        patternMatcherHandler.restoreState(recoveryManager.loadState());

        // 8. Connect to the Python bridge
        try {
            String websocketUri = Config.get("websocket.uri");
            URI uri = new URI(websocketUri);
            TVMarketDataStreamer streamer = new TVMarketDataStreamer(uri, orchestrator);
            log.info("Connecting to Python Bridge at {}", uri);
            streamer.connectBlocking(); // Use connect() for non-blocking
        } catch (URISyntaxException | InterruptedException e) {
            log.error("Failed to connect to WebSocket bridge:", e);
            orchestrator.shutdown();
        }
    }
}
