"""Research endpoints: HRP allocation, DSR validation, backtesting, alpha scanning."""
import asyncio
import json
import os
from fastapi import APIRouter
from .. import state
from ..schemas import BacktestRequest

router = APIRouter(tags=["research"])


@router.get("/api/research/hrp")
async def get_hrp_allocation():
    """HRP allocation using local-cache-first data (provider fallback active)."""
    try:
        if state.analytics is None:
            return {"error": "Analytics unavailable"}
        symbols = state.analytics.get_symbols()
        if len(symbols) < 2:
            return {"error": "Need 2+ symbols"}

        import pandas as pd

        def build_prices():
            frames = {}
            for sym in symbols[:10]:
                try:
                    df = state.analytics.fetch_live_data(sym, "1y", "1d")
                    if df is None or df.empty or "Close" not in df.columns:
                        continue
                    series = pd.to_numeric(df["Close"], errors="coerce")
                    series.index = pd.to_datetime(df["Date"], utc=True, errors="coerce")
                    frames[sym] = series
                except Exception:
                    continue
            if len(frames) < 2:
                return None
            prices = pd.DataFrame(frames).sort_index().ffill().dropna(axis=1, how="any")
            return prices if len(prices.columns) >= 2 else None

        prices = await asyncio.to_thread(build_prices)
        if prices is None or prices.empty:
            return {"error": "Data unavailable: providers failed and no local cache exists"}

        from quantcore.portfolio.hrp import HRPOptimizer
        return await asyncio.to_thread(HRPOptimizer.optimize, prices)
    except Exception as e:
        return {"error": str(e)}

@router.get("/api/research/validation")
async def get_validation_metrics():
    from quantcore.research.validation import ResearchValidator
    return await asyncio.to_thread(
        ResearchValidator.deflated_sharpe_ratio,
        observed_sr=1.5,
        num_trials=50,
        skewness=-0.5,
        kurtosis=4.0
    )


@router.post("/api/backtest/run")
async def run_backtest(req: BacktestRequest):
    from quantcore.research.backtester import Backtester
    bt = Backtester()
    return await asyncio.to_thread(bt.run_cross_sectional_momentum, req.universe, req.lookback, req.slippage_bps)


@router.post("/api/alpha/scan")
async def scan_alpha():
    from quantcore.research.alpha_hunter import AlphaHunter
    hunter = AlphaHunter()
    return await asyncio.to_thread(hunter.scan)


@router.get("/api/alpha/signals")
async def get_alpha_signals():
    path = "data/alpha_signals.json"
    if not os.path.exists(path):
        return {"signals": []}
    with open(path, "r") as f:
        return json.load(f)
