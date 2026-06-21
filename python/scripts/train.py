#!/usr/bin/env python3
import sys
sys.path.insert(0, 'python')
import numpy as np
from quantcore.models.trainer import ModelTrainer
import quantcore.quantcore_cpp as core

def main():
    data_engine = core.DataEngine("data/analytics.db")
    data_engine.load_parquet_directory("market_data", "data/raw/equities/")
    trainer = ModelTrainer(data_engine)
    print("Generating dummy features for compilation test...")
    X = np.random.rand(1000, 10).astype(np.float32)
    y = np.random.rand(1000).astype(np.float32)
    trainer.train_lightgbm("production_v1", X, y)
    print("✅ Model saved to data/models/production_v1.txt")

if __name__ == "__main__":
    main()
