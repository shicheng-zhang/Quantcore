import numpy as np
from typing import Optional
import quantcore.quantcore_cpp as core
from .base import BaseStrategy, Signal

class StatArbStrategy(BaseStrategy):
    def __init__(self, config: dict):
        super().__init__("stat_arb", config)
        self.pairs = config.get("pairs", [])
        self.entry_z = config.get("entry_zscore", 2.0)
        self.lookback = config.get("lookback", 100)
        self.feature_engine = core.FeatureEngine()
        self.spread_history: dict[str, list[float]] = {}

    def on_init(self, data_engine: core.DataEngine):
        symbols = set()
        for a, b in self.pairs: symbols.update([a, b])
        for symbol in symbols:
            results = data_engine.query_sql(f"SELECT \"Close\" FROM market_data WHERE symbol = '{symbol}' ORDER BY \"Date\"")
            self.spread_history[symbol] = [float(r['Close']) for r in results if r['Close'] is not None]

    def on_bar(self, symbol: str, bar_data: dict) -> Optional[Signal]:
        price = bar_data.get('Close', 0.0)
        if symbol in self.spread_history: self.spread_history[symbol].append(price)

        for pair_a, pair_b in self.pairs:
            if symbol not in (pair_a, pair_b): continue
            hist_a, hist_b = self.spread_history.get(pair_a, []), self.spread_history.get(pair_b, [])
            if len(hist_a) < self.lookback or len(hist_b) < self.lookback: continue

            spread = np.array(hist_a[-self.lookback:]) - np.array(hist_b[-self.lookback:])
            # Pybind11 seamlessly converts the Python list to std::vector<double> here
            zscores = self.feature_engine.rolling_zscore(spread.tolist(), self.lookback)
            if not zscores: continue

            current_z = zscores[-1]
            if abs(current_z) > self.entry_z:
                direction = core.Side.SELL if current_z > 0 else core.Side.BUY
                return Signal(symbol=pair_a, direction=direction, strength=min(abs(current_z)/4.0, 1.0), confidence=0.7)
        return None
