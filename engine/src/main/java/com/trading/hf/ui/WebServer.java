package com.trading.hf.ui;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import static spark.Spark.*;

public class WebServer {

    private static final Logger log = LoggerFactory.getLogger(WebServer.class);

    public void start() {
        // Serve static files from the 'public' directory in the classpath
        staticFiles.location("/public");

        // Set the port
        port(8080);

        // Initialize the routes
        init();

        log.info("Web server started on port 8080");
    }
}
