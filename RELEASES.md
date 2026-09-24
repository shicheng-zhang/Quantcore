# QuantCore Releases

## V1.2-Stable — Day-Trading Power Release

**Status:** Stable — day-trading-first, power-user overhaul (24/09/26)

V1.2 builds on 1.1’s stability hardening with a full day-trading stack, microstructure correctness, web resilience, and a power-user UI. The Risk Committee’s “always REJECT” rig is fixed and the platform now boots without the C++ extension.

### Highlights vs 1.1

**Day-Trading Stack**
- Tick store `python/quantcore/data/tick_store.py` (DuckDB `ticks`/`bars_1m`/`tod_volume`) — `1m→5m/15m` aggregation, 24-bin `volume_profile` (POC/VAH/VAL), `rvol` via time-of-day curve (78 slots), session-anchored VWAP.
- Intraday engine `day_trading/intraday_engine.py` — `RVOL`, `GAP_PCT`, `DELTA_IMB/CUM_DELTA`, `VWAP ±1/2σ`, `PARKINSON`, session `POC`, ORB now true 30m per `interval` (was 30 bars of 5d), macro gating (`RISK-OFF` gates longs `RVOL>2 & RSI>60`, `STAGFLATION` suppresses breakouts).
- Tactical scanner `day_trading/intraday_signals.py` — `GAP UP/DOWN + DRIVE`, `BREAKOUT` requires `RVOL≥1.5 & |delta|>0.1`, `rvol/gap/delta` returned, macro gated.
- Wilder ATR (`ewm α=1/14`) now consistent across `intraday_engine`, `intraday_signals`, `prediction_suite` (was SMA).

**Microstructure Correctness (C++)**
- `FeatureEngine` 4→12 methods: `queue_imbalance`, `cumulative_delta`, `delta_imbalance`, `kyle_lambda (Δp·signed_vol/Σvol²)`, `effective_spread_bps`, `vpin`, `intraday_volume_profile`, `rvol`, `aggregate_ticks_to_bars`, `parkinson`, `garman_klass`; `order_book_imbalance` fixed + `NaN` prefix (was `0.0` polluting zscore).
- `RiskEngine` session-aware: `max_intraday_loss 2%`, `max_trades/day 50`, `max_consecutive_losses 5`, `flat_deadline 15:55 ET`, `hold 120m`, `post-trade concentration` (was single-order notional), day/sess reset via `timestamp_ns`.
- Nexus: `MicrostructureSim` unified `η=0.15 ADV=50000` (was `0.015/0.005` mismatch), `InstitutionalOps` dark `0.5-2.0bps` via `thread_local mt19937` (was `500bps` + `rand()`), `LimitOrderBook` quantized cent tick, `MerkleLedger` FNV-1a deterministic + `prev_hash` mixing + `mutex`, `RLPolicy` clamped + `get_rl_action_normalized`, `main.cpp` atomic double helpers for `pack(1)` unaligned `HiveMindState`, PnL fixed to `qty·slip + |z|·2%·notional` (was `(fill1-fill2)·sign`).

**Quant Correctness (Python)**
- Black-Scholes `vol/black_scholes.py` — guards `S,K≤0/σ≤0`, `T→1min` not `0.0001`, added `rho`/`rho_1pct`, `vega` dual (`vega` per 100 + `vega_1pct`), `theta_calendar/trading` (was `/365` only).
- HRP `portfolio/hrp.py` — inverse-variance `w=1/σ²/Σ1/σ²` (was equal-weight), linkage cast preserves distances (`link_idx`).
- DSR `research/validation.py` — `T=n_obs` via `num_observations` (Lo 2002, was `/252`), `signal_decay` NaN/constant guards.
- StatArb `research/stat_arb.py` — spread `y-βx-α` (was `y-βx`), `half_life` realigned `Δs vs s_{t-1}`, `purged CV` lagged `signal.shift(1)·spread.diff`, `z_entry` param.
- AlphaHunter `research/alpha_hunter.py` — demeaned Pearson `r(k)` per lag (was `Σxy/√Σx²Σy²` zero-mean assumption).
- TimeMachine `replay/time_machine.py` — strategy-aware `strategy_returns` param, crash `-1.5%/2%` not `-2.5%/3.5%`, non-deterministic seed (was fixed `42` → always `-49.52%`), thresholds recalibrated `-50/-35/-30%` (was `-20%` rigged).
- Gauntlet `risk/gauntlet.py` — `T` inferred from parquet length (4361 not 504), thresholds `-50/-35/-30`, friction relative `drag<10pp` not absolute `>0`.
- PredictionSuite `research/prediction_suite.py` — ATR Wilder `ewm`, OU `θ(μ-P)dt` (was `×10`), gravity `θ·ln(gravity/P)` (was `θ(gravity-P)/P`).
- CIO `cio/attribution.py` — real `sharpe = mean/std·√252` from trades (was invented `ret·252/max(0.01,|ret|*2)`), Vader `score_with_confidence 0.5+0.35|compound|`.

**Web Resilience**
- `web/backend/analytics.py` Python fallback (`_FallbackFeatureEngine/DataEngine`) if `quantcore_cpp` missing → `200 {error}` not 500 crash; `state.py` per-singleton `try/except` + stub `Analytics`.
- All routers `api/analytics|broker|execution|infra|ops|research` wrapped to return `200 {error}` not 500.
- `state.py` `TAPE_CLIENTS` safe.

**Power UI 1.1**
- `web/templates/base.html` — top bar `⌘K` palette, `/` symbol jump, density `◫▭▢`, theme, sidebar `280px` filter/fav/recent, status bar, skip-link, `app.js?v=1.1.1` cache-bust, `data-term` preserved.
- `web/static/css/style.css` — tokens `--qc-*`, `light/dark`, density vars, `qc-table` sortable, `qc-toast`, `skeleton`, ultrawide `92%`.
- `web/static/js/app.js` 7→375 lines: `QC.prefs` persist, `initDensity/Theme/Sidebar/CommandPalette/Hotkeys (G D/P/T/N/S, ?=help, Alt+T/D/Y)`, `initTables` (click sort dblclick copy), `initClocks`, `qcPoll`, `toast`.
- `dashboard.html` `→` KPI `qc-card`, sortable latest-prices, dblclick copy, `exportDashboard` JSON, `R` refresh.
- `day_trading.html`/`nexus.html` `→` `PRO` badges, `qc-table`, export.

## V1.1-Stable

QuantCore 1.1 is the first stable release of the open-source quantitative research and simulation platform. It pairs a C++20 computation and execution engine with a Python research layer and a FastAPI dashboard, all running locally with no real capital at risk.

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

Pre-1.1 development proceeded through release candidates (RC1–RC4). Those intermediate states are preserved in git history but are not supported.
