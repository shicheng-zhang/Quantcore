import sys
import os
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from python.quantcore.portfolio.hrp import HRPOptimizer

def test_hrp_weights_sum_to_one():
    np.random.seed(42)
    returns = np.random.randn(100, 3) * 0.01
    returns[:, 1] = returns[:, 0] * 0.8 + np.random.randn(100) * 0.005
    prices = pd.DataFrame(100 * np.cumprod(1 + returns, axis=0), columns=["A", "B", "C"])
    
    res = HRPOptimizer.optimize(prices)
    assert "weights" in res
    weights = list(res["weights"].values())
    assert abs(sum(weights) - 1.0) < 1e-5
