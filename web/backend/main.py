import sys
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager
import asyncio

import os
# Calculate the absolute root directory of the project
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
NEXUS_BIN = os.path.join(BASE_DIR, "nexus", "build", "nexus_core")
LOG_FILE = os.path.join(BASE_DIR, "data", "nexus_core.log")
LIVE_JSON = os.path.join(BASE_DIR, "data", "nexus_live.json")
STATIC_JSON = os.path.join(BASE_DIR, "data", "nexus_telemetry.json")

from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "python"))
from .analytics import AnalyticsEngine

analytics: AnalyticsEngine = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global analytics
    analytics = AnalyticsEngine()
    yield

app = FastAPI(title="QuantCore Dashboard", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="web/static"), name="static")
templates = Jinja2Templates(directory="web/templates")

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request): return templates.TemplateResponse(request, "dashboard.html")
@app.get("/trends", response_class=HTMLResponse)
async def trends(request: Request): return templates.TemplateResponse(request, "trends.html")
@app.get("/predictions", response_class=HTMLResponse)
async def predictions(request: Request): return templates.TemplateResponse(request, "predictions.html")
@app.get("/execution", response_class=HTMLResponse)
async def execution(request: Request): return templates.TemplateResponse(request, "execution.html")
@app.get("/signals", response_class=HTMLResponse)
async def signals(request: Request): return templates.TemplateResponse(request, "signals.html")


@app.get("/research", response_class=HTMLResponse)
async def research(request: Request): return templates.TemplateResponse(request, "research.html")

@app.get("/api/research/hrp")
async def get_hrp_allocation():
    # Fetch last 1y of daily data for the whole universe
    symbols = analytics.get_symbols()
    if len(symbols) < 2: return {"error": "Need 2+ symbols"}

    import yfinance as yf
    import pandas as pd

    # Download matrix
    tickers = " ".join(symbols[:10]) # Limit to 10 for speed in demo
    data = yf.download(tickers, period="1y", interval="1d", progress=False)
    if data.empty: return {"error": "Data fetch failed"}

    # Handle MultiIndex columns if yfinance returns them
    if isinstance(data.columns, pd.MultiIndex):
        prices = data['Close']
    else:
        prices = data[['Close']]
        prices.columns = symbols[:1]

    from quantcore.portfolio.hrp import HRPOptimizer
    return await asyncio.to_thread(HRPOptimizer.optimize, prices)

@app.get("/api/research/validation")
async def get_validation_metrics():
    # Simulate a strategy backtest result for the dashboard demo
    from quantcore.research.validation import ResearchValidator

    # Mock data: A strategy with SR 1.5 after 50 trials
    return await asyncio.to_thread(
        ResearchValidator.deflated_sharpe_ratio,
        observed_sr=1.5,
        num_trials=50,
        skewness=-0.5,
        kurtosis=4.0
    )


import subprocess
import json
import os

@app.get("/nexus", response_class=HTMLResponse)
async def nexus_page(request: Request): return templates.TemplateResponse(request, "nexus.html")

@app.get("/api/nexus/telemetry")
async def get_nexus_telemetry():
    path = LIVE_JSON if os.path.exists(LIVE_JSON) else STATIC_JSON
    if not os.path.exists(path):
        return {"status": "IDLE", "message": "Engine has not been run yet."}
    with open(path, "r") as f:
        return json.load(f)

@app.post("/api/nexus/start")
async def start_nexus_engine():
    os.system(f"pkill -f '{NEXUS_BIN}' >/dev/null 2>&1")
    with open(LOG_FILE, "w") as log_file:
        subprocess.Popen(["stdbuf", "-oL", NEXUS_BIN], cwd=BASE_DIR, stdout=log_file, stderr=subprocess.STDOUT)
    return {"status": "STARTED", "message": "Nexus Live Engine engaged."}


@app.get("/alpha", response_class=HTMLResponse)
async def alpha_lab(request: Request): return templates.TemplateResponse(request, "alpha.html")

@app.post("/api/alpha/scan")
async def scan_alpha():
    from quantcore.research.alpha_hunter import AlphaHunter
    hunter = AlphaHunter()
    # Run in thread to avoid blocking the ASGI server during the heavy math
    return await asyncio.to_thread(hunter.scan)

@app.get("/api/alpha/signals")
async def get_alpha_signals():
    path = "data/alpha_signals.json"
    if not os.path.exists(path): return {"signals": []}
    with open(path, "r") as f: return json.load(f)


from pydantic import BaseModel
from typing import List

class BacktestRequest(BaseModel):
    universe: List[str]
    slippage_bps: float
    lookback: int

@app.get("/backtest", response_class=HTMLResponse)
async def backtest_lab(request: Request): return templates.TemplateResponse(request, "backtest.html")

@app.post("/api/backtest/run")
async def run_backtest(req: BacktestRequest):
    from quantcore.research.backtester import Backtester
    bt = Backtester()
    return await asyncio.to_thread(bt.run_cross_sectional_momentum, req.universe, req.lookback, req.slippage_bps)

@app.get("/api/overview")
async def get_overview(): return await asyncio.to_thread(analytics.get_overview)
@app.get("/api/symbols")
async def get_symbols(): return await asyncio.to_thread(analytics.get_symbols)

@app.get("/api/trend/{symbol}")
async def get_trend(symbol: str, period: str = "1y", interval: str = "1d"):
    return await asyncio.to_thread(analytics.get_trend_analysis, symbol, period, interval)

@app.get("/api/predictions/{symbol}")
async def get_predictions(symbol: str, period: str = "1y", interval: str = "1d"):
    return await asyncio.to_thread(analytics.get_predictions, symbol, period, interval)

@app.get("/api/signals")
async def get_signals(): return await asyncio.to_thread(analytics.get_recent_signals)
@app.get("/api/performance")
async def get_performance(): return await asyncio.to_thread(analytics.get_performance_metrics)


from pydantic import BaseModel
class ExecutionRequest(BaseModel):
    symbol: str
    shares: int
    algo: str

@app.post("/api/execution/simulate")
async def simulate_execution(req: ExecutionRequest):
    from quantcore.execution.algos import ExecutionEngine
    return await asyncio.to_thread(ExecutionEngine.simulate_execution, req.symbol, req.shares, req.algo)

class SymbolRequest(BaseModel):
    symbol: str

@app.post("/api/symbols")
async def add_symbol(req: SymbolRequest):
    try:
        await asyncio.to_thread(analytics.add_symbol, req.symbol)
        return {"status": "success", "symbol": req.symbol.upper()}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/api/symbols/{symbol}")
async def remove_symbol(symbol: str):
    try:
        await asyncio.to_thread(analytics.remove_symbol, symbol)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/api/nexus/logs")
async def get_nexus_logs():
    if not os.path.exists(LOG_FILE): return {"logs": "Waiting for engine to start..."}
    with open(LOG_FILE, "r") as f:
        lines = f.readlines()
        return {"logs": "".join(lines[-30:])}
