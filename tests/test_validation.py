import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from python.quantcore.research.validation import ResearchValidator

def test_deflated_sharpe_ratio_significant():
    # High Sharpe, few trials -> should be significant
    res = ResearchValidator.deflated_sharpe_ratio(observed_sr=2.5, num_trials=10)
    assert res["is_significant"] is True
    assert res["dsr_probability"] > 0.90

def test_deflated_sharpe_ratio_overfit():
    # Low Sharpe, many trials -> should be rejected (overfit)
    res = ResearchValidator.deflated_sharpe_ratio(observed_sr=0.5, num_trials=100)
    assert res["is_significant"] is False
