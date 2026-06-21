from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional
import quantcore.quantcore_cpp as core

@dataclass
class Signal:
    symbol: str
    direction: core.Side
    strength: float
    confidence: float
    metadata: dict = field(default_factory=dict)

    def to_order(self, quantity: float, price: Optional[float] = None) -> core.Order:
        order = core.Order()
        order.symbol = self.symbol
        order.side = self.direction
        order.type = core.OrderType.LIMIT if price else core.OrderType.MARKET
        order.quantity = quantity
        if price: order.limit_price = price
        return order

class BaseStrategy(ABC):
    def __init__(self, name: str, config: dict):
        self.name = name
        self.config = config

    def on_init(self, data_engine: core.DataEngine): pass

    @abstractmethod
    def on_bar(self, symbol: str, bar_data: dict) -> Optional[Signal]: ...
