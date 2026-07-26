"""Execution & HFT endpoints: execution algos, Nexus engine, Ghost Exchange,
day trading desk, intraday backtester, tactical scanner, RL training."""
import asyncio
import json
import os
import subprocess
import sys
import time
from fastapi import APIRouter
from .. import state
from ..schemas import ExecutionRequest, GhostRequest, PaperOrder

router = APIRouter(tags=["execution"])

# Path constants (project root is three levels up from web/backend/api/)
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
NEXUS_BIN = os.path.join(BASE_DIR, "nexus", "build", "nexus_core")
LOG_FILE = os.path.join(BASE_DIR, "data", "nexus_core.log")
LIVE_JSON = os.path.join(BASE_DIR, "data", "nexus_live.json")
STATIC_JSON = os.path.join(BASE_DIR, "data", "nexus_telemetry.json")


@router.post("/api/execution/simulate")
async def simulate_execution(req: ExecutionRequest):
    from quantcore.execution.algos import ExecutionEngine
    return await asyncio.to_thread(ExecutionEngine.simulate_execution, req.symbol, req.shares, req.algo)


@router.get("/api/nexus/telemetry")
async def get_nexus_telemetry():
    path = LIVE_JSON if os.path.exists(LIVE_JSON) else STATIC_JSON
    if not os.path.exists(path):
        return {"status": "IDLE", "message": "Engine has not been run yet."}
    with open(path, "r") as f:
        return json.load(f)


@router.post("/api/nexus/start")
async def start_nexus_engine():
    os.system(f"pkill -f '{NEXUS_BIN}' >/dev/null 2>&1")
    with open(LOG_FILE, "w") as log_file:
        subprocess.Popen(["stdbuf", "-oL", NEXUS_BIN], cwd=BASE_DIR, stdout=log_file, stderr=subprocess.STDOUT)
    return {"status": "STARTED", "message": "Nexus Live Engine engaged."}


@router.get("/api/nexus/logs")
async def get_nexus_logs():
    if not os.path.exists(LOG_FILE):
        return {"logs": "Waiting for engine to start..."}
    with open(LOG_FILE, "r") as f:
        lines = f.readlines()
    return {"logs": "".join(lines[-30:])}


@router.post("/api/nexus/ghost_execute")
async def ghost_execute(req: GhostRequest):
    with open("data/ghost_trigger.json", "w") as f:
        json.dump({"shares": req.shares, "vol": req.volatility}, f)
    return {"status": "TRIGGERED"}


@router.get("/api/nexus/ghost_status")
async def ghost_status():
    live_path = os.path.join(BASE_DIR, "data", "nexus_live.json")
    if not os.path.exists(live_path):
        return {"ghost_active": False}
    with open(live_path, "r") as f:
        data = json.load(f)
    return {
        "active": data.get("ghost_active", False),
        "target": data.get("ghost_target", 0),
        "filled": data.get("ghost_filled", 0),
        "theo": data.get("ghost_theo", 0),
        "actual": data.get("ghost_actual", 0),
        "slippage_usd": data.get("ghost_slippage_usd", 0),
        "queue": data.get("ghost_queue", 0),
        "partials": data.get("ghost_partial_fills", 0)
    }


@router.get("/api/day_trading/analyze/{symbol}")
async def analyze_intraday(symbol: str, interval: str = "5m", period: str = "5d"):
    return await asyncio.to_thread(state.day_trading_engine.analyze, symbol, interval, period)


@router.get("/api/intraday/backtest/{symbol}")
async def run_intraday_backtest(symbol: str, interval: str = "5m"):
    return await asyncio.to_thread(state.intraday_bt.run_orb, symbol, "5d", interval)


@router.post("/api/day_trading/scalp")
async def execute_scalp(order: PaperOrder):
    result = state.paper_broker.submit_order(order.symbol, order.side, order.qty, "VWAP")
    if result.get("status") == "FILLED":
        asyncio.create_task(state.broadcast_tape(result))
    return result


@router.get("/api/day_trading/alerts")
async def get_tactical_alerts():
    symbols = await asyncio.to_thread(state.analytics.get_symbols)
    universe = symbols[:15]
    alerts = await asyncio.to_thread(state.tactical_engine.scan_universe, universe)
    return {"alerts": alerts, "timestamp": time.time(), "scanned": len(universe)}


@router.post("/api/rl/train")
async def train_rl():
    subprocess.Popen([sys.executable, "python/quantcore/rl/train.py"], cwd=BASE_DIR)
    subprocess.Popen([sys.executable, "python/quantcore/rl/export_cpp.py"], cwd=BASE_DIR)
    return {"status": "TRAINING_STARTED"}
