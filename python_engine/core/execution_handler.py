from python_engine.models.data_models import MarketEvent

class ExecutionHandler:
    def __init__(self, order_orchestrator):
        self._order_orchestrator = order_orchestrator

    def on_event(self, event: MarketEvent):
        triggered_machine = event.triggered_machine
        if triggered_machine:
            triggered_state = triggered_machine.state
            definition = triggered_machine.definition
            self._order_orchestrator.execute_trade(triggered_state, definition)
            initial_phase_id = definition.phases[0].id
            triggered_state.reset(initial_phase_id)
