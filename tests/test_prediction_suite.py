"""
Tests for the Advanced Quantitative Prediction Suite & Prediction Review Engine.
"""
import sys
import os
import pytest
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from python.quantcore.research.prediction_suite import (
    AdvancedPredictor,
    PredictionReviewer,
    PredictionScreener,
)
from web.backend.analytics import AnalyticsEngine


@pytest.fixture
def synthetic_market_data():
    """Generates a synthetic price series with trending and mean-reverting regimes."""
    np.random.seed(42)
    n = 120
    t = np.arange(n)
    trend = 0.05 * t
    cycle = 5.0 * np.sin(2 * np.pi * t / 25)
    noise = np.random.normal(0, 0.5, n)
    prices = 100.0 + trend + cycle + noise

    highs = prices + np.random.uniform(0.2, 1.0, n)
    lows = prices - np.random.uniform(0.2, 1.0, n)
    volumes = np.random.randint(1000, 10000, n).astype(float)

    dates = pd.date_range("2024-01-01", periods=n, freq="D")
    df = pd.DataFrame({
        "Date": dates,
        "Open": prices,
        "High": highs,
        "Low": lows,
        "Close": prices,
        "Volume": volumes,
    })
    return df


def test_indicator_calculation(synthetic_market_data):
    df = AdvancedPredictor.calculate_indicators(synthetic_market_data)

    assert "EMA_9" in df.columns
    assert "EMA_21" in df.columns
    assert "EMA_50" in df.columns
    assert "MACD" in df.columns
    assert "MACD_Hist" in df.columns
    assert "RSI" in df.columns
    assert "ATR" in df.columns
    assert "BB_Upper" in df.columns
    assert "BB_Lower" in df.columns
    assert "TTM_Squeeze" in df.columns
    assert "VWAP" in df.columns

    # Verify RSI bounds
    clean_rsi = df["RSI"].dropna()
    assert (clean_rsi >= 0).all() and (clean_rsi <= 100).all()

    # Verify Bollinger Upper >= Lower
    clean_bb = df[["BB_Upper", "BB_Lower"]].dropna()
    assert (clean_bb["BB_Upper"] >= clean_bb["BB_Lower"]).all()


def test_hurst_exponent(synthetic_market_data):
    prices = synthetic_market_data["Close"].to_numpy()
    h = AdvancedPredictor.estimate_hurst_exponent(prices)
    assert 0.05 <= h <= 0.95


def test_ornstein_uhlenbeck_estimation(synthetic_market_data):
    prices = synthetic_market_data["Close"].to_numpy()
    theta, mu, sigma = AdvancedPredictor.estimate_ornstein_uhlenbeck(prices)

    assert theta > 0
    assert 50.0 < mu < 200.0
    assert sigma > 0


def test_volume_profile(synthetic_market_data):
    prices = synthetic_market_data["Close"].to_numpy()
    volumes = synthetic_market_data["Volume"].to_numpy()
    vp = AdvancedPredictor.compute_volume_profile(prices, volumes, bins=20)

    assert "poc" in vp
    assert "vah" in vp
    assert "val" in vp
    assert vp["vah"] >= vp["val"]
    assert len(vp["profile"]) == 20

    # Exactly one bin is POC
    poc_bins = [b for b in vp["profile"] if b["is_poc"]]
    assert len(poc_bins) == 1


def test_analyze_and_predict_structure(synthetic_market_data):
    res = AdvancedPredictor.analyze_and_predict(synthetic_market_data, horizon_steps=10)

    assert "current_price" in res
    assert "regime" in res
    assert "action" in res
    assert 0 <= res["conviction_score"] <= 100

    # Check scenarios
    sc = res["scenarios"]
    assert "bull" in sc and "base" in sc and "bear" in sc
    tot_prob = sc["bull"]["probability_pct"] + sc["base"]["probability_pct"] + sc["bear"]["probability_pct"]
    assert 99.0 <= tot_prob <= 101.0

    # Check Monte Carlo cone ordering: p5 <= p25 <= p50 <= p75 <= p95
    cone = res["monte_carlo_cone"]
    assert len(cone["p50"]) == 11  # 0 to 10
    for t in range(11):
        assert cone["p5"][t] <= cone["p25"][t] <= cone["p50"][t] <= cone["p75"][t] <= cone["p95"][t]

    # Check Trade Blueprint
    bp = res["trade_blueprint"]
    assert bp["recommended_action"] in ("LONG", "SHORT", "WAIT / RANGE TRADE")
    assert bp["risk_reward_ratio"] > 0


def test_prediction_reviewer_walk_forward(synthetic_market_data):
    audit = PredictionReviewer.audit_predictions(synthetic_market_data, walk_forward_bars=25, forecast_horizon=5)

    assert "directional_hit_rate_pct" in audit
    assert 0.0 <= audit["directional_hit_rate_pct"] <= 100.0
    assert audit["mae"] >= 0.0
    assert audit["rmse"] >= 0.0
    assert "model_grade" in audit
    assert len(audit["recent_audit_samples"]) > 0
    assert len(audit["historical_forecast_overlays"]) > 0


def test_analytics_engine_endpoints_integration():
    engine = AnalyticsEngine()
    # Test on seeded universe symbol
    res = engine.get_advanced_predictions("SPY", "1y", "1d", horizon_steps=10)
    assert "error" not in res
    assert res["symbol"] == "SPY"
    assert "prediction" in res
    assert "monte_carlo_cone" in res["prediction"]

    review = engine.get_prediction_review("SPY", "1y", "1d", walk_forward_bars=20)
    assert "error" not in review
    assert review["symbol"] == "SPY"
    assert "directional_hit_rate_pct" in review

    screener = engine.get_prediction_screener("1d", "1y")
    assert isinstance(screener, list)
    assert len(screener) > 0
    assert "conviction" in screener[0]
