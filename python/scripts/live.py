#!/usr/bin/env python3
import sys
sys.path.insert(0, 'python')
from quantcore.pipeline import TradingPipeline
from quantcore.strategy.stat_arb import StatArbStrategy

def main():
    pipeline = TradingPipeline("config/system.yaml")
    pipeline.register_strategy(StatArbStrategy({"pairs": [("AAPL", "MSFT")], "entry_zscore": 2.0, "lookback": 100}))
    pipeline.run_live()

if __name__ == "__main__":
    main()
