"""Regression coverage for dashboard availability without external data access."""
import pandas as pd

import web.backend.analytics as analytics_module
from web.backend.analytics import AnalyticsEngine


def test_live_fetch_falls_back_to_local_parquet(monkeypatch):
    engine = AnalyticsEngine()
    engine._live_cache = {}

    def unavailable(*_args, **_kwargs):
        raise ValueError("provider unavailable")

    monkeypatch.setattr(analytics_module, "fetch_ohlcv", unavailable)
    data = engine.fetch_live_data("AMD", "1y", "1d")

    assert not data.empty
    assert {"Date", "Close", "Volume"}.issubset(data.columns)
    assert data.attrs["data_source"] == "local_cache"
    assert pd.api.types.is_datetime64_any_dtype(data["Date"])


def test_trends_and_predictions_remain_available_offline(monkeypatch):
    engine = AnalyticsEngine()

    def unavailable(*_args, **_kwargs):
        raise ValueError("provider unavailable")

    monkeypatch.setattr(analytics_module, "fetch_ohlcv", unavailable)
    trend = engine.get_trend_analysis("AMD", "1y", "1d")
    prediction = engine.get_predictions("AMD", "1y", "1d")

    assert "error" not in trend
    assert trend["data_source"] == "local_cache"
    assert len(trend["prices"]) >= 20
    assert "error" not in prediction
    assert len(prediction["predictions"]) == 5
