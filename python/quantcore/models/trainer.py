import numpy as np
import lightgbm as lgb
from pathlib import Path
import quantcore.quantcore_cpp as core

class ModelTrainer:
    def __init__(self, data_engine: core.DataEngine, models_dir: str = "data/models"):
        self.data_engine = data_engine
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(parents=True, exist_ok=True)

    def train_lightgbm(self, name: str, X: np.ndarray, y: np.ndarray):
        params = {'objective': 'regression', 'metric': 'rmse', 'learning_rate': 0.01, 'num_leaves': 31, 'max_depth': 6, 'n_jobs': -1, 'verbose': -1}
        train_data = lgb.Dataset(X, label=y)
        model = lgb.train(params, train_data, num_boost_round=100)
        model.save_model(str(self.models_dir / f"{name}.txt"))
        return model
