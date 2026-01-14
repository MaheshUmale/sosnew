from typing import Dict

class PriceRegistry:
    _prices: Dict[str, float] = {}

    @classmethod
    def update_price(cls, symbol: str, price: float):
        cls._prices[symbol] = price

    @classmethod
    def get_price(cls, symbol: str) -> float:
        return cls._prices.get(symbol, 0.0)
