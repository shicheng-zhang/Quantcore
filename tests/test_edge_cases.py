import sys
import os
import pytest
import numpy as np
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from python.quantcore.research.backtester import Backtester
from python.quantcore.broker.paper_broker import PaperBroker
from web.backend.analytics import AnalyticsEngine

def test_backtester_single_asset_fails_gracefully():
    """Backtester requires at least 2 assets for cross-sectional momentum."""
    bt = Backtester()
    res = bt.run_cross_sectional_momentum(["SPY"], lookback=60, slippage_bps=5.0)
    assert "error" in res
    assert "at least 2" in res["error"]

def test_backtester_missing_data_fails_gracefully():
    """Backtester handles missing parquet files gracefully."""
    bt = Backtester()
    res = bt.run_cross_sectional_momentum(["FAKE_TICKER_1", "FAKE_TICKER_2"], lookback=60, slippage_bps=5.0)
    assert "error" in res

def test_analytics_nan_sanitization():
    """Analytics engine sanitizes NaN/Inf values for JSON serialization."""
    dirty_data = {"val": float('nan'), "list": [1.0, float('inf'), 2.0]}
    clean = AnalyticsEngine._sanitize_for_json(dirty_data)
    assert clean["val"] is None
    assert clean["list"][1] is None
    assert clean["list"][0] == 1.0

def test_paper_broker_slippage_calculation():
    """Paper broker correctly applies slippage based on algo."""
    broker = PaperBroker(db_path=":memory:")
    
    # Market order should have higher slippage
    res_market = broker.submit_order("AAPL", "BUY", 100, "MARKET")
    assert res_market["status"] == "FILLED"
    assert res_market["slippage_bps"] > 5.0
    
    # VWAP should have lower slippage
    res_vwap = broker.submit_order("MSFT", "BUY", 100, "VWAP")
    assert res_vwap["status"] == "FILLED"
    assert res_vwap["slippage_bps"] < 5.0
