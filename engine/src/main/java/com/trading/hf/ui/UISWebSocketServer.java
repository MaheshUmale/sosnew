package com.trading.hf.ui;

import org.java_websocket.WebSocket;
import org.java_websocket.handshake.ClientHandshake;
import org.java_websocket.server.WebSocketServer;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.net.InetSocketAddress;
import java.util.concurrent.CopyOnWriteArraySet;

public class UISWebSocketServer extends WebSocketServer {

    private static final Logger log = LoggerFactory.getLogger(UISWebSocketServer.class);
    private final CopyOnWriteArraySet<WebSocket> connections = new CopyOnWriteArraySet<>();

    public UISWebSocketServer(int port) {
        super(new InetSocketAddress(port));
    }

    @Override
    public void onOpen(WebSocket conn, ClientHandshake handshake) {
        connections.add(conn);
        log.info("UI WebSocket connection opened: {}", conn.getRemoteSocketAddress());
    }

    @Override
    public void onClose(WebSocket conn, int code, String reason, boolean remote) {
        connections.remove(conn);
        log.info("UI WebSocket connection closed: {}", conn.getRemoteSocketAddress());
    }

    @Override
    public void onMessage(WebSocket conn, String message) {
        // Not expecting messages from the UI
    }

    @Override
    public void onError(WebSocket conn, Exception ex) {
        log.error("UI WebSocket error", ex);
        if (conn != null) {
            connections.remove(conn);
        }
    }

    @Override
    public void onStart() {
        log.info("UI WebSocket server started on port {}", getPort());
    }

    public void broadcast(String message) {
        for (WebSocket conn : connections) {
            conn.send(message);
        }
    }
}
