package com.trading.hf.core;

import com.lmax.disruptor.EventHandler;
import com.trading.hf.execution.OrderOrchestrator;
import com.trading.hf.model.MarketEvent;
import com.trading.hf.model.PatternDefinition;
import com.trading.hf.model.PatternState;
import com.trading.hf.patterns.PatternStateMachine;

public class ExecutionHandler implements EventHandler<MarketEvent> {

    private final OrderOrchestrator orderOrchestrator;

    public ExecutionHandler(OrderOrchestrator orderOrchestrator) {
        this.orderOrchestrator = orderOrchestrator;
    }

    @Override
    public void onEvent(MarketEvent event, long sequence, boolean endOfBatch) throws Exception {
        PatternStateMachine triggeredMachine = event.getTriggeredMachine();

        if (triggeredMachine != null) {
            PatternState triggeredState = triggeredMachine.getState();
            PatternDefinition definition = triggeredMachine.getDefinition();

            // Execute the trade
            orderOrchestrator.executeTrade(triggeredState, definition);

            // Reset the state machine to look for a new pattern
            triggeredState.reset();
        }
    }
}
