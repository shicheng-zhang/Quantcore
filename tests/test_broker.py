import sys
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
