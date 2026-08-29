import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import state
from .api.analytics import router as analytics_router
from .api.ws import router as ws_router
from .api.infra import router as infra_router
from .api.ops import router as ops_router
from .api.execution import router as execution_router
from .api.research import router as research_router
from .api.broker import router as broker_router
from python.quantcore.config import load_config
from python.quantcore.data.seed_guard import start_guard_async

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.config = load_config()
    state.init_state()
    start_guard_async()
    try:
        yield
    finally:
        state.close_state()

app = FastAPI(title="QuantCore Dashboard", lifespan=lifespan)

app.include_router(analytics_router)
app.include_router(ws_router)
app.include_router(infra_router)
app.include_router(ops_router)
app.include_router(execution_router)
app.include_router(research_router)
app.include_router(broker_router)

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

@app.get("/nexus", response_class=HTMLResponse)
async def nexus_page(request: Request): return templates.TemplateResponse(request, "nexus.html")

@app.get("/alpha", response_class=HTMLResponse)
async def alpha_lab(request: Request): return templates.TemplateResponse(request, "alpha.html")

@app.get("/backtest", response_class=HTMLResponse)
async def backtest_lab(request: Request): return templates.TemplateResponse(request, "backtest.html")

@app.get("/paper", response_class=HTMLResponse)
async def paper_trading_desk(request: Request): return templates.TemplateResponse(request, "paper_trading.html")

@app.get("/statarb", response_class=HTMLResponse)
async def statarb_page(request: Request): return templates.TemplateResponse(request, "statarb.html")

@app.get("/hivemind", response_class=HTMLResponse)
async def hivemind_page(request: Request): return templates.TemplateResponse(request, "hivemind.html")

@app.get("/sim_lab", response_class=HTMLResponse)
async def sim_lab_page(request: Request): return templates.TemplateResponse(request, "sim_lab.html")

@app.get("/ops", response_class=HTMLResponse)
async def ops_page(request: Request): return templates.TemplateResponse(request, "ops.html")

@app.get("/alt_data", response_class=HTMLResponse)
async def alt_data_lab(request: Request): return templates.TemplateResponse(request, "alt_data.html")

@app.get("/rl_lab", response_class=HTMLResponse)
async def rl_lab(request: Request): return templates.TemplateResponse(request, "rl_lab.html")

@app.get("/cio", response_class=HTMLResponse)
async def cio_war_room(request: Request): return templates.TemplateResponse(request, "cio.html")

@app.get("/time_machine", response_class=HTMLResponse)
async def time_machine_page(request: Request): return templates.TemplateResponse(request, "time_machine.html")

@app.get("/alpha_decay", response_class=HTMLResponse)
async def alpha_decay_page(request: Request): return templates.TemplateResponse(request, "alpha_decay.html")

@app.get("/volatility", response_class=HTMLResponse)
async def vol_desk(request: Request): return templates.TemplateResponse(request, "volatility.html")

@app.get("/macro", response_class=HTMLResponse)
async def macro_desk(request: Request): return templates.TemplateResponse(request, "macro.html")

@app.get("/day_trading", response_class=HTMLResponse)
async def day_trading_page(request: Request): return templates.TemplateResponse(request, "day_trading.html")
