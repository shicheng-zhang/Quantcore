"""Broker endpoints: paper trading, Alpaca integration, autopilot control."""
import asyncio
import os
from fastapi import APIRouter, Depends
from .. import state
from ..schemas import PaperOrder, AlpacaCreds
from ..security import require_control_access

router = APIRouter(tags=["broker"])


@router.get("/api/paper/state")
async def get_paper_state():
    try:
        if state.paper_broker is None:
            return {"error": "Paper broker unavailable", "state": {"cash": 0, "initial_cash": 0, "positions": []}, "trades": []}
        s = await asyncio.to_thread(state.paper_broker.ledger.get_state)
        trades = await asyncio.to_thread(state.paper_broker.ledger.get_recent_trades)
        return {"state": s, "trades": trades}
    except Exception as e:
        return {"error": str(e), "state": {"cash": 0, "initial_cash": 0, "positions": []}, "trades": []}


@router.post("/api/paper/order")
async def submit_paper_order(order: PaperOrder, _: None = Depends(require_control_access)):
    try:
        if state.paper_broker is None:
            return {"status": "REJECTED", "reason": "Broker unavailable"}
        result = await asyncio.to_thread(
            state.paper_broker.submit_order, order.symbol, order.side, order.qty, order.algo
        )
        if result.get("status") == "FILLED":
            asyncio.create_task(state.broadcast_tape(result))
        return result
    except Exception as e:
        return {"status": "REJECTED", "reason": str(e)}


@router.post("/api/paper/reset")
async def reset_paper_account(_: None = Depends(require_control_access)):
    await asyncio.to_thread(state.paper_broker.ledger.reset_account)
    return {"status": "RESET"}


@router.post("/api/paper/autopilot/engage")
async def engage_autopilot(_: None = Depends(require_control_access)):
    with open("data/autopilot.flag", "w") as f:
        f.write("ACTIVE")
    return {"status": "ENGAGED"}


@router.post("/api/paper/autopilot/disengage")
async def disengage_autopilot(_: None = Depends(require_control_access)):
    if os.path.exists("data/autopilot.flag"):
        os.remove("data/autopilot.flag")
    return {"status": "DISENGAGED"}


@router.get("/api/paper/autopilot/status")
async def autopilot_status():
    return {"active": os.path.exists("data/autopilot.flag")}


# --- Alpaca (single definition — duplicate removed per release checklist #12) ---
@router.post("/api/alpaca/config")
async def config_alpaca(creds: AlpacaCreds, _: None = Depends(require_control_access)):
    state.alpaca_broker.save_creds(creds.key_id, creds.secret_key, creds.base_url)
    return {"status": "SAVED"}


@router.get("/api/alpaca/status")
async def alpaca_status():
    if not state.alpaca_broker.is_configured():
        return {"configured": False}
    acc = state.alpaca_broker.get_account()
    if acc:
        return {"configured": True, "equity": acc.get("equity"), "buying_power": acc.get("buying_power")}
    return {"configured": True, "error": "Failed to fetch account"}


@router.post("/api/alpaca/order")
async def submit_alpaca_order(order: PaperOrder, _: None = Depends(require_control_access)):
    return state.alpaca_broker.submit_order(order.symbol, order.side, order.qty, order.algo)
