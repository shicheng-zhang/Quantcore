"""Analytics endpoints: overview, symbols, trend, predictions, signals, performance."""
import asyncio
import re
from fastapi import APIRouter, Depends, HTTPException
from .. import state
from ..schemas import SymbolRequest
from ..security import require_control_access

router = APIRouter(tags=["analytics"])


@router.get("/api/overview")
async def get_overview():
    try:
        return await asyncio.to_thread(state.analytics.get_overview)
    except Exception as e:
        return {"error": str(e), "total_symbols": 0, "latest_prices": {}, "system_status": "Degraded"}


@router.get("/api/symbols")
async def get_symbols():
    try:
        return await asyncio.to_thread(state.analytics.get_symbols)
    except Exception as e:
        return []


@router.get("/api/trend/{symbol}")
async def get_trend(symbol: str, period: str = "1y", interval: str = "1d"):
    try:
        return await asyncio.to_thread(state.analytics.get_trend_analysis, symbol, period, interval)
    except Exception as e:
        return {"error": str(e), "symbol": symbol}


@router.get("/api/predictions/{symbol}")
async def get_predictions(symbol: str, period: str = "1y", interval: str = "1d"):
    try:
        return await asyncio.to_thread(state.analytics.get_predictions, symbol, period, interval)
    except Exception as e:
        return {"error": str(e)}


@router.get("/api/predictions/advanced/{symbol}")
async def get_advanced_predictions(symbol: str, period: str = "1y", interval: str = "1d", horizon: int = 10):
    try:
        return await asyncio.to_thread(state.analytics.get_advanced_predictions, symbol, period, interval, horizon)
    except Exception as e:
        return {"error": str(e)}


@router.get("/api/predictions/review/{symbol}")
async def get_prediction_review(symbol: str, period: str = "1y", interval: str = "1d", bars: int = 40):
    try:
        return await asyncio.to_thread(state.analytics.get_prediction_review, symbol, period, interval, bars)
    except Exception as e:
        return {"error": str(e)}


@router.get("/api/predictions/screener")
async def get_prediction_screener(interval: str = "1d", period: str = "1y"):
    try:
        return await asyncio.to_thread(state.analytics.get_prediction_screener, interval, period)
    except Exception as e:
        return {"error": str(e)}


@router.get("/api/signals")
async def get_signals():
    try:
        return await asyncio.to_thread(state.analytics.get_recent_signals)
    except Exception:
        return []


@router.get("/api/performance")
async def get_performance():
    try:
        return await asyncio.to_thread(state.analytics.get_performance_metrics)
    except Exception as e:
        return {"error": str(e), "total_trades": 0}


@router.post("/api/symbols")
async def add_symbol(req: SymbolRequest, _: None = Depends(require_control_access)):
    try:
        await asyncio.to_thread(state.analytics.add_symbol, req.symbol)
        return {"status": "success", "symbol": req.symbol.upper()}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/api/symbols/{symbol}")
async def remove_symbol(symbol: str, _: None = Depends(require_control_access)):
    try:
        if not re.fullmatch(r"[A-Za-z0-9._-]{1,16}", symbol):
            raise ValueError("Invalid symbol")
        await asyncio.to_thread(state.analytics.remove_symbol, symbol)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))
