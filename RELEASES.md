# QuantCore Releases

## v1.0.0

**Status:** Stable

**Highlights:**
- Boot reliability: `libduckdb.so` resolved via `$ORIGIN` RPATH + venv (no more `LD_LIBRARY_PATH` hacks).
- Dependencies: removed unused multi-GB `torch`; added missing RL/NLP/TUI deps.
- Runtime isolation: state moved out of source tree; poisoned `surveillance_halt.flag` cleared.
- Security: SQL injection hardened in C++ `DataEngine` and Python StatArb (input validation + identifier whitelisting).
- Correctness: Limit Order Book rewritten (ordered price-keyed maps) — fixes hash collisions, volume aggregation, cancel handling, and best-price walk-back. Standalone C++ unit test added.
- Resilience: yfinance→Stooq provider fallback wired through analytics, research/HRP, alpha hunter, intraday engine/signals/backtester, and execution algos. Local-cache-first availability.
- Honesty: "AI Forecast" → "Mean-Reversion Projection", "Merkle Ledger" → simulated hash chain, RL export labeled as heuristic surrogate. README gains a real-vs-simulated transparency table.
- Code health: `main.py` slimmed; obsolete `final_sweep.sh` string-surgery removed; bare `except:` hardened to `except Exception:`; `.gitignore` added; `testclient` removed from control whitelist.

**Known non-goals (see v1.1 backlog):**
- PPO distillation into the C++ execution header (currently a hand-tuned surrogate).
- Real L2 order-book depth reconstruction (current LOB is fed synthetic + trade ticks).
- CSRF protection on control-plane POST endpoints.
