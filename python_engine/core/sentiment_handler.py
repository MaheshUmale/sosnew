from python_engine.models.data_models import MarketEvent, Sentiment, MessageType

class SentimentHandler:
    PCR_EXTREME_BULLISH = 0.7
    PCR_EXTREME_BEARISH = 1.3
    PCR_NEUTRAL = 1.0

    def __init__(self):
        self._current_regime = "SIDEWAYS"

    def on_event(self, event: MarketEvent):
        if event.type in (MessageType.MARKET_UPDATE, MessageType.SENTIMENT_UPDATE):
            sentiment = event.sentiment
            if sentiment:
                regime = sentiment.regime
                if regime is None:
                    regime = self._determine_regime(sentiment)
                    sentiment.regime = regime
                self._current_regime = regime

    def get_regime(self) -> str:
        return self._current_regime

    def _determine_regime(self, sentiment: Sentiment) -> str:
        pcr = sentiment.pcr
        if pcr < self.PCR_EXTREME_BULLISH:
            return "COMPLETE_BULLISH"
        elif pcr < self.PCR_NEUTRAL:
            return "BULLISH"
        elif pcr > self.PCR_EXTREME_BEARISH:
            return "COMPLETE_BEARISH"
        elif pcr > self.PCR_NEUTRAL:
            return "BEARISH"
        else:
            return "SIDEWAYS"
