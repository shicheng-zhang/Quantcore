"""Infrastructure endpoints: Hive-Mind IPC, StatArb, Time Machine, Macro Desk,
Satellite alt-data, Volatility Desk, Alpha Decay (MLOps), Risk Gauntlet, Seed Guard."""
import asyncio
import json
import os
import subprocess
import sys
import numpy as np
from fastapi import APIRouter
from .. import state
from ..schemas import GauntletRequest

router = APIRouter(tags=["infra"])

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))


# --- HIVE-MIND IPC ---
@router.post("/api/hivemind/start_daemon")
async def start_daemon():
    os.system("pkill -f quant_daemon.py >/dev/null 2>&1")
    log_path = os.path.join(BASE_DIR, "data", "quant_daemon.log")
    with open(log_path, "w") as log_file:
        subprocess.Popen(
            [sys.executable, "-u", "python/quantcore/hivemind/quant_daemon.py"],
            cwd=BASE_DIR, stdout=log_file, stderr=subprocess.STDOUT
        )
    return {"status": "STARTED"}


@router.get("/api/hivemind/status")
async def hivemind_status():
    path = os.path.join(BASE_DIR, "data", "hivemind_ui.json")
    if not os.path.exists(path):
        return {"active": False}
    with open(path, "r") as f:
        return json.load(f)


@router.get("/api/hivemind/logs")
async def hivemind_logs():
    path = os.path.join(BASE_DIR, "data", "quant_daemon.log")
    if not os.path.exists(path):
        return {"logs": "Waiting for daemon..."}
    with open(path, "r") as f:
        lines = f.readlines()
    return {"logs": "".join(lines[-20:])}


# --- STATARB CRUCIBLE ---
@router.get("/api/statarb/status")
async def statarb_status():
    path = os.path.join(BASE_DIR, "data", "stat_arb_ui.json")
    if not os.path.exists(path):
        return {"active": False, "top_pairs": [], "active_pair": None}
    with open(path, "r") as f:
        return json.load(f)


# --- TIME MACHINE ---
@router.post("/api/time_machine/run")
async def run_time_machine(req: dict):
    scenario = req.get("scenario", "2022_crypto_winter")
    return await asyncio.to_thread(state.time_machine.run_stress_test, scenario)


@router.get("/api/time_machine/report")
async def get_tm_report():
    path = os.path.join(BASE_DIR, "data", "time_machine_report.json")
    if not os.path.exists(path):
        return {"status": "IDLE"}
    with open(path, "r") as f:
        return json.load(f)


# --- MACRO DESK ---
@router.get("/api/macro/state")
async def get_macro_state():
    return state.macro_engine.get_regime()


# --- SATELLITE LAYER (ALT DATA) ---
@router.get("/api/alt_data/feed")
async def get_alt_feed():
    # Threaded: RSS fetches must never block the ASGI event loop.
    try:
        await asyncio.to_thread(state.satellite_engine.generate_feed)
        feed_path = os.path.join(BASE_DIR, "data", "satellite_feed.json")
        if not os.path.exists(feed_path):
            return []
        with open(feed_path, "r") as f:
            return json.load(f)
    except Exception:
        return []


# --- VOLATILITY DESK ---
@router.get("/api/vol/surface")
async def get_vol_surface(spot: float = 65000.0, iv: float = 0.45):
    from python.quantcore.vol.black_scholes import VolSurface
    return VolSurface.generate_surface(spot, iv)


@router.get("/api/vol/chain")
async def get_options_chain(spot: float = 65000.0, iv: float = 0.45, T_days: int = 30):
    from python.quantcore.vol.black_scholes import BlackScholes
    T = T_days / 365.0
    r = 0.05
    strikes = np.linspace(spot * 0.9, spot * 1.1, 9)
    chain = []
    for K in strikes:
        call_p = BlackScholes.price(spot, K, T, r, iv, 'call')
        put_p = BlackScholes.price(spot, K, T, r, iv, 'put')
        call_g = BlackScholes.greeks(spot, K, T, r, iv, 'call')
        put_g = BlackScholes.greeks(spot, K, T, r, iv, 'put')
        chain.append({
            "strike": round(K, 2), "moneyness": round(K / spot, 3),
            "call_price": round(call_p, 2), "call_delta": round(call_g['delta'], 3), "call_theta": round(call_g['theta'], 2),
            "put_price": round(put_p, 2), "put_delta": round(put_g['delta'], 3), "put_theta": round(put_g['theta'], 2)
        })
    return {"spot": spot, "T_days": T_days, "chain": chain}


# --- ALPHA DECAY MONITOR (MLOps) ---
@router.get("/api/mlops/health")
async def get_model_health():
    results, history = await asyncio.to_thread(state.decay_monitor.evaluate_models)
    return {"models": results, "history": history}


# --- RISK COMMITTEE GAUNTLET ---
@router.post("/api/risk/gauntlet")
async def run_gauntlet_api(req: GauntletRequest):
    return await asyncio.to_thread(
        state.risk_committee.evaluate_strategy,
        req.strategy_name, req.observed_sr, req.num_trials, req.universe
    )


# --- SEED GUARD (AUTO-RESEED) ---
@router.post("/api/seed/force")
async def force_reseed():
    from python.quantcore.data.seed_guard import check_and_reseed
    return await asyncio.to_thread(check_and_reseed, True)


@router.get("/api/seed/status")
async def seed_status():
    from python.quantcore.data.seed_guard import _load_meta, _parquet_max_age_days
    meta = _load_meta()
    return {
        "boot_count": meta.get("boot_count", 0),
        "last_seed": meta.get("last_seed", "never"),
        "reseed_count": meta.get("reseed_count", 0),
        "data_age_days": round(_parquet_max_age_days(), 1),
        "max_age_days": 7,
        "max_boots": 50
    }
