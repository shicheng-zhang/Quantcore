"""Execution & HFT endpoints: execution algos, Nexus engine, Ghost Exchange,
day trading desk, intraday backtester, tactical scanner, RL training."""
import asyncio
import json
import os
import subprocess
import sys
import time
from fastapi import APIRouter, Depends
from .. import state
from ..schemas import ExecutionRequest, GhostRequest, PaperOrder
from ..security import require_control_access
from ..runtime import read_json, write_json_atomic

router = APIRouter(tags=["execution"])

# Path constants (project root is three levels up from web/backend/api/)
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
NEXUS_BIN = os.path.join(BASE_DIR, "nexus", "build", "nexus_core")
LOG_FILE = os.path.join(BASE_DIR, "data", "runtime", "nexus.log")
LIVE_JSON = os.path.join(BASE_DIR, "data", "nexus_live.json")
STATIC_JSON = os.path.join(BASE_DIR, "data", "nexus_telemetry.json")


@router.post("/api/execution/simulate")
async def simulate_execution(req: ExecutionRequest):
    try:
        from quantcore.execution.algos import ExecutionEngine
        return await asyncio.to_thread(ExecutionEngine.simulate_execution, req.symbol, req.shares, req.algo)
    except Exception as e:
        return {"error": str(e)}


NEXUS_BIN = os.path.join(BASE_DIR, "nexus", "build", "nexus_core")
LOG_FILE = os.path.join(BASE_DIR, "data", "runtime", "nexus.log")
LIVE_JSON = os.path.join(BASE_DIR, "data", "nexus_live.json")
STATIC_JSON = os.path.join(BASE_DIR, "data", "nexus_telemetry.json")
SUPERVISOR_STATE = os.path.join(BASE_DIR, "data", "runtime", "supervisor.json")

# The engine rewrites telemetry every ~1s. Anything older than this is either a
# crashed engine or a file left behind by an earlier run — either way it must
# not be presented as live.
TELEMETRY_LIVE_WINDOW_S = 5.0
TELEMETRY_STALE_AFTER_S = 60.0

# Engine's own documented bound for dark-pool price improvement
# (see nexus/include/institutional_ops.h: 0.5 + U(0,1.5) bps).
DARK_IMPROVEMENT_MIN_BPS = 0.5
DARK_IMPROVEMENT_MAX_BPS = 2.0


def _humanize_age(seconds: float) -> str:
    if seconds < 1:
        return "now"
    if seconds < 60:
        return f"{int(seconds)}s"
    if seconds < 3600:
        return f"{int(seconds // 60)}m"
    if seconds < 86400:
        return f"{seconds / 3600:.1f}h"
    return f"{seconds / 86400:.1f}d"


def _engine_process_alive() -> bool | None:
    """Is nexus running under the supervisor?

    Returns None when there is no supervisor state at all, which means "not
    managed here" rather than a confident "not running".
    """
    try:
        with open(SUPERVISOR_STATE, encoding="utf-8") as f:
            state = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    service = state.get("nexus")
    if not service:
        return False
    pid = service.get("pid")
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _audit_telemetry(payload: dict, age_s: float) -> dict:
    """Flag values that cannot be produced by the engine.

    Silently clamping impossible readings would hide a real defect; reporting
    them keeps the operator informed. Mutates and returns the payload.
    """
    warnings: list[str] = []

    imp = payload.get("dark_improvement")
    if isinstance(imp, (int, float)) and not (
        DARK_IMPROVEMENT_MIN_BPS <= imp <= DARK_IMPROVEMENT_MAX_BPS
    ):
        warnings.append(
            f"dark_improvement={imp}bps is outside the engine range "
            f"[{DARK_IMPROVEMENT_MIN_BPS}, {DARK_IMPROVEMENT_MAX_BPS}] bps"
        )

    bid, ask = payload.get("best_bid"), payload.get("best_ask")
    if isinstance(bid, (int, float)) and isinstance(ask, (int, float)):
        if bid >= ask:
            warnings.append(f"crossed book: best_bid={bid} >= best_ask={ask}")
        if bid <= 0 or ask <= 0:
            warnings.append(f"non-positive quote: bid={bid} ask={ask}")

    lat = payload.get("latency_ns_mean")
    if isinstance(lat, (int, float)) and lat and lat < 0:
        warnings.append(f"negative latency_ns_mean={lat}")

    if age_s > TELEMETRY_STALE_AFTER_S:
        warnings.append(f"telemetry is {_humanize_age(age_s)} old — engine is not writing")

    payload["warnings"] = warnings
    payload["telemetry_age_s"] = round(age_s, 1)
    payload["telemetry_age_human"] = _humanize_age(age_s)
    payload["telemetry_state"] = (
        "LIVE" if age_s <= TELEMETRY_LIVE_WINDOW_S
        else ("STALE" if age_s <= TELEMETRY_STALE_AFTER_S else "OFFLINE")
    )
    running = _engine_process_alive()
    payload["engine_managed"] = running if running is not None else False
    payload["engine_running"] = bool(running)
    payload["sor_dark_pct"] = payload.get("sor_dark_pct", 0.30)
    return payload


@router.get("/api/nexus/telemetry")
async def get_nexus_telemetry():
    path = LIVE_JSON if os.path.exists(LIVE_JSON) else STATIC_JSON
    if not os.path.exists(path):
        return {
            "status": "IDLE",
            "message": "Engine has not been run yet.",
            "telemetry_state": "OFFLINE",
            "telemetry_age_human": "never",
            "engine_running": False,
            "sor_dark_pct": 0.30,
            "warnings": ["no telemetry file on disk"],
        }
    payload = read_json(path, {"status": "DEGRADED", "message": "Telemetry is being updated; retry shortly."})
    if not isinstance(payload, dict):
        return {"status": "ERROR", "message": "telemetry payload is not an object", "warnings": ["malformed telemetry"]}
    try:
        age_s = max(0.0, time.time() - os.path.getmtime(path))
    except OSError:
        age_s = float("inf")
    return await asyncio.to_thread(_audit_telemetry, payload, age_s)


@router.post("/api/nexus/start")
async def start_nexus_engine(_: None = Depends(require_control_access)):
    result = await asyncio.to_thread(
        subprocess.run,
        [sys.executable, "python/scripts/supervisor.py", "start", "nexus"],
        cwd=BASE_DIR, capture_output=True, text=True, timeout=10,
    )
    if result.returncode:
        return {"status": "ERROR", "message": result.stderr or result.stdout}
    return {"status": "STARTED", "message": "Nexus Live Engine engaged."}


@router.get("/api/nexus/logs")
async def get_nexus_logs():
    if not os.path.exists(LOG_FILE):
        return {"logs": "Waiting for engine to start..."}
    with open(LOG_FILE, "r") as f:
        lines = f.readlines()
    return {"logs": "".join(lines[-30:])}


@router.post("/api/nexus/ghost_execute")
async def ghost_execute(req: GhostRequest, _: None = Depends(require_control_access)):
    write_json_atomic("data/ghost_trigger.json", {"shares": req.shares, "vol": req.volatility})
    return {"status": "TRIGGERED"}


@router.get("/api/nexus/ghost_status")
async def ghost_status():
    live_path = os.path.join(BASE_DIR, "data", "nexus_live.json")
    if not os.path.exists(live_path):
        return {"ghost_active": False}
    data = read_json(live_path, {})
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
    try:
        if state.day_trading_engine is None:
            return {"error": "Day trading engine unavailable"}
        return await asyncio.to_thread(state.day_trading_engine.analyze, symbol, interval, period)
    except Exception as e:
        return {"error": str(e)}


@router.get("/api/intraday/backtest/{symbol}")
async def run_intraday_backtest(symbol: str, interval: str = "5m"):
    try:
        if state.intraday_bt is None:
            return {"error": "Backtester unavailable"}
        return await asyncio.to_thread(state.intraday_bt.run_orb, symbol, "5d", interval)
    except Exception as e:
        return {"error": str(e)}


@router.post("/api/day_trading/scalp")
async def execute_scalp(order: PaperOrder, _: None = Depends(require_control_access)):
    try:
        if state.paper_broker is None:
            return {"status": "REJECTED", "reason": "Broker unavailable"}
        result = await asyncio.to_thread(
            state.paper_broker.submit_order, order.symbol, order.side, order.qty, "VWAP"
        )
        if result.get("status") == "FILLED":
            asyncio.create_task(state.broadcast_tape(result))
        return result
    except Exception as e:
        return {"status": "REJECTED", "reason": str(e)}


@router.get("/api/day_trading/alerts")
async def get_tactical_alerts():
    try:
        symbols = await asyncio.to_thread(state.analytics.get_symbols) if state.analytics else []
        universe = symbols[:15] if symbols else []
        if not universe:
            return {"alerts": [], "timestamp": time.time(), "scanned": 0, "note": "No symbols in universe"}
        if state.tactical_engine is None:
            return {"alerts": [], "timestamp": time.time(), "scanned": 0, "error": "Scanner unavailable"}
        alerts = await asyncio.to_thread(state.tactical_engine.scan_universe, universe)
        return {"alerts": alerts, "timestamp": time.time(), "scanned": len(universe)}
    except Exception as e:
        return {"alerts": [], "timestamp": time.time(), "scanned": 0, "error": str(e)}


@router.post("/api/rl/train")
async def train_rl(_: None = Depends(require_control_access)):
    # Export depends on a completed training artifact; doing both concurrently
    # can export a stale or partially written model.
    def train_then_export():
        subprocess.run([sys.executable, "python/quantcore/rl/train.py"], cwd=BASE_DIR, check=True)
        subprocess.run([sys.executable, "python/quantcore/rl/export_cpp.py"], cwd=BASE_DIR, check=True)
    asyncio.create_task(asyncio.to_thread(train_then_export))
    return {"status": "TRAINING_STARTED"}
