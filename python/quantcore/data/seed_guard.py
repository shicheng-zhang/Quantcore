"""
Seed Guard: Automatic data freshness enforcement.

Triggers a universe reseed when:
  - Parquet files are older than MAX_AGE_DAYS (default: 7)
  - Boot count exceeds MAX_BOOTS (default: 50)
  - Key source files have been modified since last seed

Runs in a background thread to avoid blocking app startup.
"""
import os
import json
import time
import hashlib
import threading
from pathlib import Path
from datetime import datetime, timedelta

META_FILE = "data/.seed_meta.json"
DATA_DIR = "data/raw/equities"
MAX_AGE_DAYS = 7
MAX_BOOTS = 50

# Files whose modification should trigger a reseed
WATCHED_FILES = [
    "python/quantcore/research/backtester.py",
    "python/quantcore/portfolio/hrp.py",
    "web/backend/analytics.py",
]


def _file_hash(path: str) -> str:
    """MD5 of a file's content (fast, not cryptographic - just change detection)."""
    try:
        h = hashlib.md5()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()
    except FileNotFoundError:
        return ""


def _load_meta() -> dict:
    try:
        with open(META_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_meta(meta: dict):
    os.makedirs("data", exist_ok=True)
    with open(META_FILE, "w") as f:
        json.dump(meta, f, indent=2)


def _parquet_max_age_days() -> float:
    """Age of the oldest parquet file in days."""
    if not os.path.exists(DATA_DIR):
        return 999.0
    files = [f for f in os.listdir(DATA_DIR) if f.endswith(".parquet")]
    if not files:
        return 999.0
    oldest_mtime = min(os.path.getmtime(os.path.join(DATA_DIR, f)) for f in files)
    age = datetime.now() - datetime.fromtimestamp(oldest_mtime)
    return age.total_seconds() / 86400.0


def _source_files_changed(meta: dict) -> bool:
    """Check if any watched source file has been modified since last seed."""
    saved_hashes = meta.get("source_hashes", {})
    for path in WATCHED_FILES:
        current = _file_hash(path)
        if current and current != saved_hashes.get(path, ""):
            return True
    return False


def _do_reseed():
    """Actually reseed the universe (blocking - runs in background thread)."""
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    try:
        from web.backend.analytics import AnalyticsEngine
        engine = AnalyticsEngine()
        starter = ["SPY", "QQQ", "IWM", "GLD", "TLT", "BTC-USD", "ETH-USD"]
        existing = engine.get_symbols()
        reseeded = 0
        for sym in starter:
            # Always re-download to refresh stale data
            print(f"[SEED GUARD] Refreshing {sym}...")
            try:
                engine.add_symbol(sym)
                reseeded += 1
            except Exception as e:
                print(f"[SEED GUARD] Failed {sym}: {e}")
        print(f"[SEED GUARD] Reseed complete. {reseeded} symbols refreshed.")
        return reseeded
    except Exception as e:
        print(f"[SEED GUARD] Reseed failed: {e}")
        return 0


def check_and_reseed(force: bool = False) -> dict:
    """
    Main entry point. Checks all conditions and reseeds if needed.
    Returns a status dict for logging/UI.
    """
    meta = _load_meta()
    boot_count = meta.get("boot_count", 0) + 1
    meta["boot_count"] = boot_count

    age = _parquet_max_age_days()
    sources_changed = _source_files_changed(meta)
    needs_reseed = force or age > MAX_AGE_DAYS or boot_count > MAX_BOOTS or sources_changed

    reasons = []
    if force:
        reasons.append("FORCED")
    if age > MAX_AGE_DAYS:
        reasons.append(f"DATA_STALE ({age:.1f}d > {MAX_AGE_DAYS}d)")
    if boot_count > MAX_BOOTS:
        reasons.append(f"BOOT_LIMIT ({boot_count} > {MAX_BOOTS})")
    if sources_changed:
        reasons.append("SOURCE_MODIFIED")

    status = {
        "boot_count": boot_count,
        "data_age_days": round(age, 1),
        "needs_reseed": needs_reseed,
        "reasons": reasons,
        "timestamp": datetime.now().isoformat(),
    }

    if needs_reseed:
        print(f"[SEED GUARD] Reseed triggered: {', '.join(reasons)}")
        reseeded = _do_reseed()
        # Update meta after successful reseed
        meta["last_seed"] = datetime.now().isoformat()
        meta["boot_count"] = 0  # Reset boot counter after reseed
        meta["source_hashes"] = {path: _file_hash(path) for path in WATCHED_FILES}
        meta["reseed_count"] = meta.get("reseed_count", 0) + 1
        status["reseeded_symbols"] = reseeded
    else:
        print(f"[SEED GUARD] Data fresh. Age: {age:.1f}d | Boots: {boot_count}/{MAX_BOOTS} | No reseed needed.")

    _save_meta(meta)
    return status


def start_guard_async():
    """Launch the seed guard in a daemon thread (non-blocking)."""
    def _worker():
        time.sleep(2)  # Let the app fully initialize first
        check_and_reseed()

    t = threading.Thread(target=_worker, daemon=True, name="seed-guard")
    t.start()
    print("[SEED GUARD] Background freshness check scheduled.")
