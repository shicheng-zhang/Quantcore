# QuantCore Releases

## v1.0.0

**Status:** Stable — first public release

QuantCore 1.0 is the first stable release of the open-source quantitative research and simulation platform. It pairs a C++20 computation and execution engine with a Python research layer and a FastAPI dashboard, all running locally with no real capital at risk.

This release is the result of a full stability, correctness, and honesty hardening pass. Every subsystem boots cleanly, survives data-provider outages, and reports truthfully about what is computed versus what is simulated.

### Highlights

**Reliability**
- Clean, reproducible builds via a Python virtual environment (no more system-wide `--break-system-packages` installs).
- The C++ analytics extension resolves `libduckdb.so` via a baked-in `$ORIGIN` RPATH — no `LD_LIBRARY_PATH` hacks required.
- Local-cache-first data availability: the dashboard stays usable when market-data providers are down or rate-limited.

**Correctness**
- Limit Order Book rebuilt on ordered price-keyed maps — fixes price-hash collisions, volume aggregation, cancel handling, and best-price walk-back. Covered by a standalone C++ unit test (`nexus/tests/test_lob.cpp`).
- Backtester look-ahead bias eliminated (a signal at day *t* earns returns from day *t+1*).
- Deflated Sharpe Ratio uses the full Euler–Mascheroni correction for the multiple-testing penalty.
- SQL construction hardened with input validation and identifier whitelisting.

**Resilience**
- Unified market-data provider with yfinance → Stooq fallback, wired through analytics, research/HRP, alpha scanning, intraday desks, and execution sims.
- Process lifecycle consolidated on a local supervisor; the TUI kill switch now terminates processes by exact PID instead of pattern-matching.
- Bare `except:` handlers hardened to `except Exception:` with logging on hot paths.

**Transparency**
- Dashboard relabeled honestly: "AI Forecast" → mean-reversion projection, "Merkle Ledger" → simulated hash chain, RL export marked as a heuristic surrogate.
- README gains a real-vs-simulated transparency table.
- Experimental modules clearly badged `EXP` in navigation.

### What's included

- C++20 Nexus HFT engine (SPSC ring buffer, lock-free atomics, Binance WebSocket ingest)
- C++ analytics core (DuckDB-backed data engine, feature engine, risk engine) via pybind11
- Python research layer: backtester, HRP, Deflated Sharpe Ratio, StatArb, alpha hunter, volatility desk
- FastAPI dashboard with 20+ pages across Command Center, Alpha & Research, Execution & HFT, and Infrastructure
- Paper broker with DuckDB ledger and Almgren-Chriss slippage model
- Infrastructure TUI for process and health management
- Risk Committee gauntlet (DSR overfit check, stress test, friction check)

### Known limitations (see ROADMAP)

- RL execution policy is a hand-tuned heuristic surrogate; PPO distillation into the C++ header is not yet automated.
- The Nexus LOB is fed synthetic order flow plus Binance trade ticks, not real L2 depth snapshots.
- Control-plane POST endpoints rely on local-only binding plus an optional token; CSRF tokens are not yet implemented.
- Several simulation desks (Macro, Time Machine, CIO attribution) generate synthetic data for demonstration.

### Install / upgrade notes

Fresh install:

```bash
python3 -m venv .venv && source .venv/bin/activate
bash setup.sh
python3 infra_tui.py   # or: bash run_web.sh
```

See `USER_GUIDE.md` for the full walkthrough and `TROUBLESHOOTING.md` for known issues.

---

## Prior history

Pre-1.0 development proceeded through release candidates (RC1–RC4). Those intermediate states are preserved in git history but are not supported.
