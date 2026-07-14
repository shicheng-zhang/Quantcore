import os

def build_tests():
    os.makedirs("tests", exist_ok=True)
    
    # 1. Patch paper_broker.py to accept db_path for testing isolation
    broker_file = "python/quantcore/broker/paper_broker.py"
    if os.path.exists(broker_file):
        with open(broker_file, "r") as f:
            content = f.read()
        if "def __init__(self, db_path=None):" not in content:
            content = content.replace(
                "def __init__(self):\n        self.ledger = PaperLedger()",
                "def __init__(self, db_path=None):\n        self.ledger = PaperLedger(db_path) if db_path else PaperLedger()"
            )
            with open(broker_file, "w") as f:
                f.write(content)
            print("[✓] Patched paper_broker.py to accept db_path for test isolation")

    # 2. test_validation.py
    test_val = '''import sys
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
'''
    with open("tests/test_validation.py", "w") as f:
        f.write(test_val)
    print("[✓] Generated tests/test_validation.py")

    # 3. test_black_scholes.py
    test_bs = '''import sys
import os
import numpy as np
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from python.quantcore.vol.black_scholes import BlackScholes

def test_call_put_parity():
    S, K, T, r, sigma = 100, 100, 1.0, 0.05, 0.2
    call = BlackScholes.price(S, K, T, r, sigma, 'call')
    put = BlackScholes.price(S, K, T, r, sigma, 'put')
    # Put-Call Parity: C - P = S - K * e^(-rT)
    parity_diff = call - put
    expected_diff = S - K * np.exp(-r * T)
    assert abs(parity_diff - expected_diff) < 1e-5

def test_greeks_delta_bounds():
    S, K, T, r, sigma = 100, 100, 1.0, 0.05, 0.2
    call_g = BlackScholes.greeks(S, K, T, r, sigma, 'call')
    put_g = BlackScholes.greeks(S, K, T, r, sigma, 'put')
    assert 0 <= call_g["delta"] <= 1
    assert -1 <= put_g["delta"] <= 0
'''
    with open("tests/test_black_scholes.py", "w") as f:
        f.write(test_bs)
    print("[✓] Generated tests/test_black_scholes.py")

    # 4. test_broker.py
    test_broker = '''import sys
import os
import pytest
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from python.quantcore.broker.paper_broker import PaperBroker

@pytest.fixture
def broker(tmp_path):
    db_path = str(tmp_path / "test_broker.duckdb")
    return PaperBroker(db_path=db_path)

def test_buy_order_success(broker):
    res = broker.submit_order("AAPL", "BUY", 10, "MARKET")
    assert res["status"] == "FILLED"
    assert res["qty"] == 10
    state = broker.ledger.get_state()
    assert state["cash"] < 1000000.0

def test_buy_order_rejection_insufficient_funds(broker):
    # Drain cash by buying a massive amount
    broker.ledger.execute_fill("AAPL", "BUY", 1000000, 100, 0, 0) 
    res = broker.submit_order("TSLA", "BUY", 100, "MARKET")
    assert res["status"] == "REJECTED"
    assert "INSUFFICIENT" in res["reason"]
'''
    with open("tests/test_broker.py", "w") as f:
        f.write(test_broker)
    print("[✓] Generated tests/test_broker.py")

    # 5. test_portfolio.py
    test_port = '''import sys
import os
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from python.quantcore.portfolio.hrp import HRPOptimizer

def test_hrp_weights_sum_to_one():
    np.random.seed(42)
    returns = np.random.randn(100, 3) * 0.01
    returns[:, 1] = returns[:, 0] * 0.8 + np.random.randn(100) * 0.005
    prices = pd.DataFrame(100 * np.cumprod(1 + returns), columns=["A", "B", "C"])
    
    res = HRPOptimizer.optimize(prices)
    assert "weights" in res
    weights = list(res["weights"].values())
    assert abs(sum(weights) - 1.0) < 1e-5
'''
    with open("tests/test_portfolio.py", "w") as f:
        f.write(test_port)
    print("[✓] Generated tests/test_portfolio.py")

    # 6. Create pytest.ini
    with open("pytest.ini", "w") as f:
        f.write("[pytest]\ntestpaths = tests\npythonpath = .\n")
    print("[✓] Generated pytest.ini")

    # 7. Update requirements.txt
    with open("requirements.txt", "a") as f:
        f.write("\npytest>=7.0.0\n")
    print("[✓] Added pytest to requirements.txt")

if __name__ == "__main__":
    build_tests()
