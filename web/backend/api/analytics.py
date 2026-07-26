"""Analytics endpoints: overview, symbols, trend, predictions, signals, performance."""
import asyncio
from fastapi import APIRouter, HTTPException
from .. import state
from ..schemas import SymbolRequest

router = APIRouter(tags=["analytics"])


@router.get("/api/overview")
async def get_overview():
    return await asyncio.to_thread(state.analytics.get_overview)


@router.get("/api/symbols")
async def get_symbols():
    return await asyncio.to_thread(state.analytics.get_symbols)


@router.get("/api/trend/{symbol}")
async def get_trend(symbol: str, period: str = "1y", interval: str = "1d"):
    return await asyncio.to_thread(state.analytics.get_trend_analysis, symbol, period, interval)


@router.get("/api/predictions/{symbol}")
async def get_predictions(symbol: str, period: str = "1y", interval: str = "1d"):
    return await asyncio.to_thread(state.analytics.get_predictions, symbol, period, interval)


@router.get("/api/signals")
async def get_signals():
    return await asyncio.to_thread(state.analytics.get_recent_signals)


@router.get("/api/performance")
async def get_performance():
    return await asyncio.to_thread(state.analytics.get_performance_metrics)


@router.post("/api/symbols")
async def add_symbol(req: SymbolRequest):
    try:
        await asyncio.to_thread(state.analytics.add_symbol, req.symbol)
        return {"status": "success", "symbol": req.symbol.upper()}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/api/symbols/{symbol}")
async def remove_symbol(symbol: str):
    try:
        await asyncio.to_thread(state.analytics.remove_symbol, symbol)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))
