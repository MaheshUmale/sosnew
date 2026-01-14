from typing import Dict, List
from python_engine.models.data_models import MarketEvent, OptionChainData, MessageType

class OptionChainHandler:
    def __init__(self):
        self._latest_option_chain: Dict[int, OptionChainData] = {}

    def on_event(self, event: MarketEvent):
        if event.type == MessageType.OPTION_CHAIN_UPDATE:
            if event.option_chain:
                for data in event.option_chain:
                    self._latest_option_chain[data.strike] = data

    def get_latest_option_chain(self) -> Dict[int, OptionChainData]:
        return self._latest_option_chain
