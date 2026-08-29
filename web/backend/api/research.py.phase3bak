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
    symbols = state.analytics.get_symbols()
    if len(symbols) < 2:
        return {"error": "Need 2+ symbols"}
    import yfinance as yf
    import pandas as pd
    tickers = " ".join(symbols[:10])
    data = yf.download(tickers, period="1y", interval="1d", progress=False)
    if data.empty:
        return {"error": "Data fetch failed"}
    if isinstance(data.columns, pd.MultiIndex):
        prices = data['Close']
    else:
        prices = data[['Close']]
        prices.columns = symbols[:1]
    from quantcore.portfolio.hrp import HRPOptimizer
    return await asyncio.to_thread(HRPOptimizer.optimize, prices)


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
