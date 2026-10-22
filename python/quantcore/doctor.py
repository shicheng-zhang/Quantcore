"""QuantCore installation health check.

Run with:  python -m quantcore.doctor

Imports every critical module and reports OK/FAIL without starting any
services, opening any databases, or making any network calls. Purely
diagnostic — nothing is modified.
"""

from __future__ import annotations

import importlib
import sys
from typing import List, Tuple

# Modules that should always be importable (pure Python, no external deps)
CORE_MODULES: List[str] = [
    "quantcore.config",
    "quantcore.logging_config",
    "quantcore.safe_inputs",
    "quantcore.pipeline",
]

# Modules with third-party dependencies (may fail if not installed)
OPTIONAL_MODULES: List[str] = [
    "quantcore.data.provider",
    "quantcore.research.backtester",
    "quantcore.research.stat_arb",
    "quantcore.research.prediction_suite",
    "quantcore.risk.gauntlet",
    "quantcore.replay.time_machine",
    "quantcore.macro.synthetic_macro",
    "quantcore.alt_data.satellite",
    "quantcore.day_trading.intraday_engine",
    "quantcore.vol.black_scholes",
    "quantcore.rl.train",
    "quantcore.strategy.base",
]

# The compiled C++ extension (optional — Python fallback exists)
CPP_MODULE: str = "quantcore.quantcore_cpp"


def _try_import(name: str) -> Tuple[bool, str]:
    """Try to import a module. Return (ok, error_message)."""
    try:
        importlib.import_module(name)
        return True, ""
    except Exception as exc:  # noqa: BLE001 — we want to capture any failure
        return False, type(exc).__name__ + ": " + str(exc)


def main() -> int:
    failures = 0

    print("=" * 60)
    print("  QuantCore doctor — installation health check")
    print("=" * 60)
    print()

    # --- Core modules (must pass) ---
    print("Core modules (required):")
    for name in CORE_MODULES:
        ok, err = _try_import(name)
        status = "OK " if ok else "FAIL"
        print(f"  [{status}] {name}" + (f"  — {err}" if not ok else ""))
        if not ok:
            failures += 1

    print()

    # --- Optional modules (may fail if deps missing) ---
    print("Optional modules (third-party deps):")
    for name in OPTIONAL_MODULES:
        ok, err = _try_import(name)
        status = "OK " if ok else "FAIL"
        print(f"  [{status}] {name}" + (f"  — {err}" if not ok else ""))
        if not ok:
            failures += 1

    print()

    # --- Compiled C++ extension ---
    print("Compiled C++ extension:")
    ok, err = _try_import(CPP_MODULE)
    status = "OK " if ok else "FAIL"
    print(f"  [{status}] {CPP_MODULE}" + (f"  — {err}" if not ok else ""))
    if not ok:
        print("      (Python fallback will be used — features will run slower but work)")
    # Don't count C++ absence as a failure — it's optional by design.

    print()
    print("=" * 60)
    if failures:
        print(f"  {failures} module(s) failed to import — see errors above.")
        print("  Install missing deps:  pip install -r requirements.txt")
        return 1
    print("  All core and optional modules imported successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())