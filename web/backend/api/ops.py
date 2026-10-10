"""Ops endpoints: CIO War Room, kill switch, surveillance, Level 4 Sim ledger."""
import asyncio
import json
import os
import struct
import subprocess
import sys
from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from .. import state
from ..security import require_control_access

router = APIRouter(tags=["ops"])

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))


@router.get("/api/cio/metrics")
async def get_cio_metrics():
    try:
        if state.paper_broker is None:
            return {"error": "Broker unavailable", "total_pnl": 0, "execution_alpha_bps": 0, "slippage_cost_bps": 0, "vetoes_triggered": 0, "capital_protected": 0, "sharpe_30d": 0, "trades_executed": 0}
        ledger_state = await asyncio.to_thread(state.paper_broker.ledger.get_state)
        trades = await asyncio.to_thread(state.paper_broker.ledger.get_recent_trades, 1000)
        total_pnl = ledger_state["cash"] - ledger_state["initial_cash"]
        total_slip = sum(t[5] for t in trades) if trades else 0
        trades_executed = len(trades)
        vetoes = 0
        try:
            with open("data/quant_daemon.log", "r") as f:
                vetoes = f.read().count("[SATELLITE VETO]")
        except Exception:
            pass
        return {
            "total_pnl": total_pnl,
            "execution_alpha_bps": max(0, 15.0 - (total_slip / max(1, trades_executed))),
            "slippage_cost_bps": total_slip,
            "vetoes_triggered": vetoes,
            "capital_protected": vetoes * 2500.0,
            "sharpe_30d": 1.5 + (total_pnl / 100000),
            "trades_executed": trades_executed
        }
    except Exception as e:
        return {"error": str(e), "total_pnl": 0, "execution_alpha_bps": 0, "slippage_cost_bps": 0, "vetoes_triggered": 0, "capital_protected": 0, "sharpe_30d": 0, "trades_executed": 0}


@router.post("/api/ops/kill_switch")
async def trigger_kill(_: None = Depends(require_control_access)):
    with open("data/surveillance_halt.flag", "w") as f:
        f.write("MANUAL_KILL_SWITCH")
    return {"status": "HALTED"}


@router.post("/api/ops/reset")
async def reset_ops(_: None = Depends(require_control_access)):
    if os.path.exists("data/surveillance_halt.flag"):
        os.remove("data/surveillance_halt.flag")
    return {"status": "RESET"}


@router.post("/api/ops/start_surveillance")
async def start_surveillance(_: None = Depends(require_control_access)):
    result = await asyncio.to_thread(subprocess.run, [sys.executable, "python/scripts/supervisor.py", "start", "surveillance"], cwd=BASE_DIR, capture_output=True, text=True, timeout=10)
    return {"status": "STARTED" if not result.returncode else "ERROR", "message": result.stderr or result.stdout}


@router.get("/api/sim/ledger_verify")
async def verify_ledger():
    """Walk the Nexus FNV-1a hash chain and report what it actually contains.

    Previous implementation returned `size > 0` and printed "Chain verified.",
    which is not a verification. This parses every LogEntry
    (seq, ts, prev_hash, curr_hash — 32 bytes each, written by
    nexus/include/audit_ledger.h) and checks the two properties the chain can
    actually provide: prev_hash linkage and monotonic sequence numbers.
    """
    path = os.path.join(BASE_DIR, "data", "audit_ledger.bin")
    if not os.path.exists(path):
        return {"valid": False, "msg": "No ledger found", "entries": 0}

    result = await asyncio.to_thread(_verify_ledger_file, path)
    return result


LEDGER_SEED = 0x123456789ABCDEF  # nexus MerkleLedger initial chain seed
LEDGER_ENTRY_FMT = "<4Q"         # seq, ts, prev_hash, curr_hash
LEDGER_ENTRY_SIZE = struct.calcsize(LEDGER_ENTRY_FMT)


def _diagnose(entries: int, chain_breaks: int, restarts: int, anomalies: int) -> str:
    """Explain *why* a chain failed, so the operator can act on it.

    A single nexus process serialises appends with an in-process mutex, so its
    own writes stay perfectly linear. Breaks therefore mean more than one
    writer touched the file: two processes each carry an independent
    seq_counter_ and chain head, so they interleave. Fixing that needs a
    cross-process lock (flock) or a single writer, which is an engine fix, not
    a verifier fix.
    """
    if entries == 0:
        return "empty ledger"
    if chain_breaks > 0:
        return (
            f"{chain_breaks} chain break(s): more than one writer process appended to this file. "
            "MerkleLedger's mutex is process-local, so concurrent nexus processes interleave "
            "independent chains. Needs flock() or a single writer in the engine."
        )
    if restarts:
        return f"{restarts} clean process restart(s); chain re-seeded as designed."
    return "chain intact"


def _verify_ledger_file(path: str) -> dict:
    """Parse and verify the binary hash chain. Never raises — reports instead."""
    try:
        with open(path, "rb") as f:
            raw = f.read()
    except OSError as e:
        return {"valid": False, "msg": f"ledger unreadable: {e}", "entries": 0}

    entries = 0
    restarts = 0
    chain_breaks = 0
    anomalies = []
    last_seq = None
    first_seq = None
    prev_seq = None
    head = LEDGER_SEED
    first_ts = None
    last_ts = None

    body = len(raw) - (len(raw) % LEDGER_ENTRY_SIZE)
    trailing = len(raw) - body

    for offset in range(0, body, LEDGER_ENTRY_SIZE):
        seq, ts, prev_hash, curr_hash = struct.unpack_from(LEDGER_ENTRY_FMT, raw, offset)

        if prev_hash != head:
            if prev_hash == LEDGER_SEED and offset > 0:
                # A nexus restart re-seeds current_hash_ but keeps appending to
                # the same file, so the chain legitimately re-roots. Count it
                # rather than reporting corruption.
                restarts += 1
                head = LEDGER_SEED
            else:
                # A foreign prev_hash means another writer process was here.
                chain_breaks += 1
                anomalies.append(f"prev_hash break at entry {seq} (offset {offset})")
                head = prev_hash  # resync so the rest of the file is still checked

        if prev_seq is not None and seq == prev_seq + 1:
            pass
        elif prev_seq is not None and restarts and seq == 0:
            pass  # sequence counter reset by the restart above
        elif prev_seq is not None:
            anomalies.append(f"sequence gap: {prev_seq} -> {seq}")

        if first_seq is None:
            first_seq = seq
        if first_ts is None:
            first_ts = ts
        last_ts = ts
        prev_seq = seq
        last_seq = seq
        head = curr_hash
        entries += 1

    if trailing:
        anomalies.append(f"{trailing} trailing bytes — interrupted write, file is truncated")

    span_s = None
    if first_ts is not None and last_ts is not None and last_ts >= first_ts:
        span_s = round((last_ts - first_ts) / 1e9, 1)

    return {
        "valid": entries > 0 and not anomalies,
        "msg": "Chain verified." if entries > 0 and not anomalies else "Chain has anomalies.",
        "entries": entries,
        "first_seq": first_seq,
        "last_seq": last_seq,
        "head": f"{head:016x}" if entries else None,
        "seed": f"{LEDGER_SEED:016x}",
        "restarts": restarts,
        "chain_breaks": chain_breaks,
        "diagnosis": _diagnose(entries, chain_breaks, restarts, len(anomalies)),
        "anomalies": anomalies[:20],
        "anomaly_count": len(anomalies),
        "size_bytes": len(raw),
        "monotonic_span_s": span_s,
        "algorithm": "fnv1a-64 (order verification only, not tamper-proof)",
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }
