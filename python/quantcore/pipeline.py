import yaml, time, signal, logging
from typing import Optional
import quantcore.quantcore_cpp as core
from .strategy.base import BaseStrategy
from .models.trainer import ModelTrainer
from .nlp.sentiment import SentimentEngine

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("pipeline")

class TradingPipeline:
    def __init__(self, config_path: str = "config/system.yaml"):
        with open(config_path) as f: self.config = yaml.safe_load(f)
        self.event_bus = core.EventBus()
        self.data_engine = core.DataEngine(self.config.get("database_path", "data/analytics.db"))
        self.risk_engine = core.RiskEngine(core.RiskConfig(), self.event_bus)
        self.strategies: list[BaseStrategy] = []
        self.running = False
        signal.signal(signal.SIGINT, lambda s,f: self._shutdown())

    def register_strategy(self, strategy: BaseStrategy):
        self.strategies.append(strategy)

    def initialize(self):
        logger.info("=== Initializing ===")
        for name, path in self.config.get("data", {}).get("parquet_views", {}).items():
            self.data_engine.load_parquet_directory(name, path)
        for s in self.strategies: s.on_init(self.data_engine)
        logger.info("=== Ready ===")

    def run_live(self):
        self.running = True
        self.initialize()
        logger.info("=== Live Trading ===")
        while self.running: time.sleep(1.0)

    def _shutdown(self):
        logger.info("Shutting down...")
        self.running = False
