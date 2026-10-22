# QuantCore 1.2 — Remediation Masterplan

**Status:** Read-only assessment (no code has been modified yet)
**Generated from:** Full codebase review of `cpp/`, `nexus/`, `python/`, `web/`, `tests/`, docs, and git history
**Scope:** Everything that should be seriously fixed before this codebase is considered production-ready or even robustly maintainable.

---

## How to Use This Document

Each item is tagged with a severity tier:

- **[P0] Critical** — will break in production, cause silent data corruption, or prevent builds/tests entirely.
- **[P1] High** — quant correctness, API reliability, or major usability hazard.
- **[P2] Medium** — robustness, observability, or maintainability debt.
- **[P3] Low** — cleanup, documentation, polish.

Each item includes: location, problem, impact, and suggested fix direction.

---

# Tier 1: Build System & Dependencies ([P0] Critical)

## 1.1 Network-mandatory `FetchContent` at CMake configure time

**Location:** `CMakeLists.txt` (root), `cpp/CMakeLists.txt`, `nexus/CMakeLists.txt`

**Problem:** The build pulls **pybind11, DuckDB v1.1.0, nlohmann/json, and spdlog directly from GitHub** during `cmake`. There is no vendored fallback, no offline cache, and no clear error if GitHub is unreachable. A build machine without internet cannot compile the C++ core.

**Impact:** Builds are non-deterministic and impossible in air-gapped or restricted networks. CI cannot run without external access.

**Fix direction:** Vendoring or a local `FetchContent` source directory with a clear offline fallback. Document a `make fetch-deps` step that can be run once on a connected machine.

---

## 1.2 Three separate build directories

**Location:** `build/`, `build-cpptests/`, `build-nexus/` (all present in repo)

**Problem:** Multiple parallel CMake build trees exist with no documentation on which is canonical. New contributors cannot tell where to run `cmake` or `ctest`.

**Impact:** Confusion, duplicated artifacts, potential stale builds.

**Fix direction:** Consolidate to a single out-of-source build directory convention, e.g. `build/` for the main library and `build/tests` or a single `ctest` target inside the same tree. Update README and CONTRIBUTING.

---

## 1.3 No CI/CD pipeline

**Location:** `.github/` (minimal/absent per git log)

**Problem:** The git log explicitly states GitHub Actions workflows were removed because of DuckDB build issues. The README claims `pytest` and `ctest` run in CI on every push, but that is no longer true.

**Impact:** Regressions merge silently. No automated gating on PRs.

**Fix direction:** Reintroduce CI (GitHub Actions) with matrix builds for Linux/macOS, running `pytest` and `ctest --test-dir build-cpptests`. Allow DuckDB build failures to be isolated rather than killing the whole pipeline.

---

## 1.4 Python dependencies unpinned and implicit

**Location:** `requirements.txt`, various `import` statements across `python/`

**Problem:** Modules import `polars`, `yfinance`, `scipy`, `textual`, `psutil`, `fastapi`, `uvicorn`, `duckdb`, `pyarrow`, `nltk`/VADER without a lock file. `satellite.py` attempts `from python.quantcore.nlp.vader_engine import VaderEngine` (see 4.1) which may not exist in the tree.

**Impact:** Environment drift; `pip install -r requirements.txt` may not be sufficient. Missing modules cause silent degradation or confusing import errors.

**Fix direction:** Add `requirements.lock` or `pyproject.toml` with pinned versions. Add a startup dependency check (`python -m quantcore.doctor`) that verifies all imports before launching.

---

## 1.5 `setup.sh` failure mode inconsistency

**Location:** `setup.sh`

**Problem:** Recent commit made `setup.sh` fail loudly if `quantcore_cpp` or `libduckdb` are missing, but older documentation/users may still assume soft `|| true` failures. The script behavior is not clearly documented.

**Impact:** Users may run setup and get a half-working installation without realizing the C++ engine is absent.

**Fix direction:** Make `setup.sh` emit a clear summary at the end: which components built, which failed, and what functionality is degraded without them.

---

# Tier 2: C++ Core — `quantcore_cpp` / pybind11 ([P0] Critical)

## 2.1 `RiskEngine::update_portfolio()` never re-anchors equity on new day

**Location:** `cpp/src/risk_engine.cpp`, lines 143–163

**Problem:** `day_start_date_ns_`, `session_start_date_ns_`, `day_start_equity_`, and `session_start_equity_` are initialized only when `day_start_date_ns_ == 0`. The trade-counter reset logic (lines 155–162) correctly detects day rollover via `last_trade_day_ns_` but resets **only** `trades_today_` and `consecutive_losses_` — not the equity anchors. Unless `reset_day()` is called externally at session start, intraday-loss and drawdown checks compare against stale equity from a prior day.

**Impact:** Intraday loss limit (2%) and max drawdown (10%) can use the wrong baseline, allowing excessive risk or falsely halting trading.

**Fix direction:** In `update_portfolio()`, when a new day is detected, reset `day_start_equity_` and `session_start_equity_` to `snapshot.total_equity`, and update the date anchors.

---

## 2.2 Session and flat-deadline checks assume ET-aligned timestamps

**Location:** `cpp/src/risk_engine.cpp` (`is_outside_session`, `is_flat_deadline`)

**Problem:** Time-of-day is extracted with `timestamp_ns % (86400s in ns)` and compared against `session_start_ns`/`session_end_ns`/`flat_deadline_ns`. Comments admit: *"assume timestamp is ET-aligned; production should use tz conversion."* If timestamps arrive in UTC, the 15:55 ET flat deadline fires at the wrong wall-clock time.

**Impact:** Day-trading risk gates trigger at incorrect times — positions may not be forced flat by 15:55 ET, or may be blocked prematurely.

**Fix direction:** Accept a timezone offset or require UTC timestamps with explicit conversion to America/New_York before comparing to session boundaries. Document the expected timestamp timezone in `types.h`.

---

## 2.3 Concentration check uses `average_cost`, not mark-to-market price

**Location:** `cpp/src/risk_engine.cpp` (`get_position_notional`)

**Problem:** `get_position_notional()` multiplies `pos.quantity * pos.average_cost`. For overnight positions, average cost is stale. The post-trade notional check should use the current reference price (`order.limit_price` or a live mark).

**Impact:** Position concentration can be materially understated or overstated. A long position that has appreciated will appear smaller than it is; a depreciated short will appear larger.

**Fix direction:** Pass the current reference price into the concentration check, or look up the latest mark from a price store. At minimum, document that `average_cost` is used and is not mark-to-market.

---

## 2.4 MARKET orders without `limit_price` are hard-rejected

**Location:** `cpp/src/risk_engine.cpp`, lines 121–123

**Problem:** `if (!order.limit_price.has_value() || *order.limit_price <= 0) return REJECT "Missing market price for risk check"`. A genuine market order has no limit price. This makes the engine unusable for market-order workflows unless the caller fabricates a reference price.

**Impact:** Any paper broker or execution layer sending MARKET orders will see them all rejected by the risk engine.

**Fix direction:** Allow MARKET orders with `std::nullopt` limit_price by using the latest known mark price for that symbol, or by skipping the concentration check for MARKET orders and applying only session/daily-loss checks.

---
## 2.5 SQL injection surface in `DataEngine` and Python fallback

**Location:** `cpp/include/quantcore/data_engine.h`, `cpp/src/data_engine.cpp`, `web/backend/analytics.py` (`_FallbackDataEngine`)

**Problem:** `query_features(const std::string& sql)` takes raw SQL with no visible whitelist enforcement despite the architecture doc claiming a "SQL whitelist." The Python fallback interpolates `dir` directly into `CREATE VIEW ... AS SELECT * FROM read_parquet('{dir}/*.parquet')` and interpolates `name` into `DROP/CREATE VIEW {name}` after only an alnum+underscore check.

**Impact:** Arbitrary SQL execution if an attacker controls `name`, `dir`, or the SQL string.

**Fix direction:** Implement a true SQL whitelist (SELECT only, no DROP/INSERT/ATTACH/Copy), parameterize or strictly validate identifiers, and avoid string interpolation into DDL.

---

## 2.6 Python fallback for `FeatureEngine` is incomplete

**Location:** `web/backend/analytics.py` (`_FallbackFeatureEngine`)

**Problem:** The fallback implements only `rolling_mean`, `rolling_std`, `rolling_zscore`, and `order_book_imbalance`. The C++ engine has 12 methods (queue imbalance, cumulative delta, delta imbalance, Kyle's lambda, effective spread, VPIN, intraday volume profile, RVOL, tick-to-bar aggregation, Parkinson, Garman-Klass). If `quantcore_cpp` is missing, calls to the other 8 methods silently fail or are undefined.

**Impact:** Degraded mode is not actually functional for microstructure features.

**Fix direction:** Implement all 12 methods in the Python fallback, or raise a clear `NotImplementedError` / service-unavailable response rather than silently returning wrong data.

---

## 2.7 Global static initialization order hazard in Nexus (`main.cpp`)

**Location:** `nexus/src/main.cpp`, lines 57–66

**Problem:** Global objects are constructed before `main()`: `SPSCQueue<Event, 2097152> event_queue`, `LimitOrderBook lob`, `MerkleLedger audit_log("data/audit_ledger.bin")`, `InstitutionalOps ops`, `GhostExchange ghost_lob`. `audit_log` opens/truncates a file during static initialization. If `data/` does not exist or permissions are wrong, the program crashes before `main()` can log anything.

**Impact:** Non-deterministic startup failure depending on working directory and file permissions.

**Fix direction:** Move all global object construction into `main()` or an explicit `init()` function after verifying directory existence.

---

## 2.8 `types.h` uses `std::optional<double>` in `Order` and `FeatureRow`

**Location:** `cpp/include/quantcore/types.h`

**Problem:** Pybind11 bindings for `std::optional` and nested `std::vector<Position>` inside `PortfolioSnapshot` require careful definitions. The Python test notes that `def_readwrite` returns a *copy* of `std::vector`, so `pf.positions = list(pf.positions) + [pos]` is required — appending to the returned list is a no-op.

**Impact:** Easy-to-miss footgun for Python callers; silent data loss when mutating positions.

**Fix direction:** Add explicit pybind11 vector/suite bindings and document the copy-on-read behavior. Consider returning `std::vector<Position>` by value with a dedicated setter method.

---

# Tier 3: Nexus HFT Engine ([P0] Critical)

## 3.1 `GhostExchange::reality.is_active` never resets after simulation

**Location:** `nexus/include/ghost_exchange.h`, line 97; `nexus/src/main.cpp` (`trigger_ghost_execution`)

**Problem:** `simulate_execution()` ends with a comment: *"Keep is_active true so the UI shows the final brutal result."* But `trigger_ghost_execution()` guards spawning with `if (!ghost_lob.reality.is_active.load())`. **Once the first ghost execution runs, `is_active` stays true forever, so no subsequent ghost execution can ever be triggered.**

**Impact:** The GhostExchange / execution-simulation path works exactly once per process lifetime, then dead-silently.

**Fix direction:** Reset `is_active` to `false` when `remaining == 0` (simulation complete) or add an explicit `reset()` call after the UI reads the final state. Guard the respawn logic correctly.

---

## 3.2 `SPSCQueue` mislabeled "multi-producer"

**Location:** `nexus/include/spsc_queue.h`

**Problem:** `push()` serializes behind a single `std::mutex push_mutex_`. That is **not** multi-producer lock-free; it is a mutex-protected producer with a lock-free consumer. The comment claims "Multi-producer safe" — contradictory with SPSC semantics.

**Impact:** Misleading documentation; the mutex is a contention point under multiple producers despite the lock-free consumer design.

**Fix direction:** Rename to reflect single-producer-under-lock, or implement a true multi-producer SPSC (e.g., with a mutex-free atomic spinlock or separate per-producer slots). Update comments.

---

## 3.3 `SPSCQueue<Event, 2097152>` allocates 2M `Event` objects up front

**Location:** `nexus/src/main.cpp`, line 57

**Problem:** The buffer is `T buffer_[Capacity]` inline in the struct. If `Event` contains strings or large payloads, this is a massive static footprint (tens to hundreds of MB), allocated whether used or not.

**Impact:** High memory baseline, potential OOM in constrained environments.

**Fix direction:** Use a `std::unique_ptr<Event[]>` heap allocation, or make capacity configurable and smaller by default. Lazily initialize the buffer.

---

## 3.4 Audit ledger mutex is process-local; concurrent Nexus processes interleave chains

**Location:** `nexus/include/audit_ledger.h`; `web/backend/api/ops.py` (`_verify_ledger_file`)

**Problem:** `MerkleLedger` uses a single `std::mutex`. Two Nexus instances writing to `data/audit_ledger.bin` will interleave independent chains. The Python verifier explicitly diagnoses this: *"MerkleLedger's mutex is process-local, so concurrent nexus processes interleave independent chains. Needs flock() or a single writer in the engine."*

**Impact:** Cross-process ledger corruption; chain verification reports false breaks.

**Fix direction:** Add `flock()`/file locking around append, or enforce a single-writer process architecture. Document that only one Nexus instance may write to a given ledger file.

---

## 3.5 Audit ledger 50 MB rotation breaks hash-chain continuity

**Location:** `nexus/include/audit_ledger.h` (`append_event`)

**Problem:** When the file exceeds 50 MB, `append_event()` truncates and re-seeds `current_hash_`, `prev_hash_`, and `seq_counter_`. The chain is deliberately broken at rotation. `verify_ledger()` treats a re-root as a legitimate restart but cannot distinguish planned rotation from corruption.

**Impact:** Chain verification cannot tell a scheduled rotation from a tamper event or process crash.

**Fix direction:** Write a rotation marker entry with a distinct `prev_hash` sentinel before truncating, so the verifier can identify planned chain resets.

---

## 3.6 FNV-1a ledger is not tamper-proof

**Location:** `nexus/include/audit_ledger.h` (class doc comment)

**Problem:** The header admits FNV-1a is *"trivially forgeable in O(n) time"* and *"NOT sufficient for adversarial tamper detection / regulatory audit compliance / legal evidence."*

**Impact:** If presented as an "audit ledger" to users or auditors, it is misleading.

**Fix direction:** Add a SHA-256 via OpenSSL (`EVP_DigestUpdate`) upgrade path, or clearly label the ledger as "order verification only, not tamper-evident" in all user-facing outputs.

---

## 3.7 `mmap`'d HiveMind bridge never unmapped

**Location:** `nexus/src/main.cpp` (`init_hivemind_bridge`)

**Problem:** `mmap()` is called but there is no corresponding `munmap()` on shutdown; `fd` is closed immediately after mmap (valid), but the mapping is never released. Shared-memory state can persist after process kill.

**Impact:** Resource leakage; stale shared memory on abrupt termination.

**Fix direction:** Store the mapped pointer and fd, call `munmap()` and `close()` in a cleanup handler or destructor registered with `atexit()` / signal handling.

---

## 3.8 Blocking `sleep_for` inside `GhostExchange::simulate_execution()`

**Location:** `nexus/include/ghost_exchange.h`, line 93

**Problem:** The execution simulation sleeps 50–150 ms per child fill. This blocks the calling thread doing synthetic work rather than processing real events.

**Impact:** Unpredictable latency; slows the engine loop if called from the hot path.

**Fix direction:** Move simulation to a dedicated background thread with an async result channel; do not block the event consumer.

---

# Tier 4: Python Research Layer ([P1] High)

## 4.1 `satellite.py` imports a module that may not exist

**Location:** `python/quantcore/alt_data/satellite.py`, lines 55–63, 68–79

**Problem:** It tries `from python.quantcore.nlp.vader_engine import VaderEngine` then `from quantcore.nlp.vader_engine import VaderEngine`. No `python/quantcore/nlp/` directory or `vader_engine.py` was found in the tree. If VADER is unavailable, `_score()` returns `None` and falls back to synthetic scores without a clear error.

**Impact:** Silent degradation of sentiment analysis; confusing behavior when VADER is missing.

**Fix direction:** Create the `nlp` module or remove the import path; raise a clear `ImportError` with install instructions if VADER is required.

---

## 4.2 `backtester.py::_sanitize()` silently converts NaN/Inf to 0.0

**Location:** `python/quantcore/research/backtester.py`, lines 7–18

**Problem:** Every NaN or Inf float becomes `0.0` before returning to the UI/API. This hides missing data, division-by-zero, and pipeline failures. A backtest producing all-NaN equity reports `0%` returns instead of an error.

**Impact:** Data integrity issues are invisible; downstream consumers trust corrupt results.

**Fix direction:** Return `null` in JSON for NaN/Inf (per `_sanitize` in `prediction_suite.py`) or propagate an explicit `error` field. Do not silently zero.

---

## 4.3 `backtester.py` CAGR short-window guard is arbitrary

**Location:** `python/quantcore/research/backtester.py`, lines 158–167

**Problem:** If `total_return <= -1.0` → CAGR = -1.0; if `n_days < 30` → raw return. These guards are hardcoded with no configuration, and annualization assumes daily data regardless of actual frequency.

**Impact:** Misleading performance metrics for non-daily or very short windows.

**Fix direction:** Accept `annualization_factor` and `min_days_for_annualization` as parameters; document assumptions.

---

## 4.4 `gauntlet.py` runs the full backtest 3× per evaluation

**Location:** `python/quantcore/risk/gauntlet.py` (`evaluate_strategy`)

**Problem:** Calls `run_cross_sectional_momentum()` for TEST 2 and twice more for TEST 3 (5bps and 15bps). Each call fetches/loads universe data. Slow inside a "risk committee" gate that should be fast.

**Impact:** Poor latency for strategy approval; repeated data loading.

**Fix direction:** Load universe data once, pass it in, or cache backtest results by (universe, lookback, slippage) tuple.

---

## 4.5 `gauntlet.py`: `strategy_returns` may be unbound after failed backtest

**Location:** `python/quantcore/risk/gauntlet.py`, TEST 2 `try/except`

**Problem:** If the exception fires, `strategy_returns` remains `None`, and later code may use it. (Code was truncated in review; verify post-truncation.)

**Impact:** Potential `UnboundLocalError` or `NoneType` crash during risk evaluation.

**Fix direction:** Initialize `strategy_returns = None` before the try block and guard all downstream uses.

---

## 4.6 `gauntlet.py` DSR `n_obs` fallback to 504

**Location:** `python/quantcore/risk/gauntlet.py`, lines 29–40

**Problem:** If `data/raw/equities/` is empty or `polars` is not installed, `n_obs` stays at 504. DSR is highly sensitive to `T`; hardcoded default silently produces wrong overfit probabilities.

**Impact:** Incorrect Deflated Sharpe Ratio; strategies may be approved or rejected based on wrong noise thresholds.

**Fix direction:** Require explicit `n_obs` from the caller or fail loudly when data is unavailable instead of defaulting.

---

## 4.7 `time_machine.py` "veto savings" is hardcoded 35%

**Location:** `python/quantcore/replay/time_machine.py`, line 104

**Problem:** `veto_savings = abs(max_dd) * 1000000 * 0.35` with comment *"Synthetic — 35% savings is an illustrative assumption, not empirical."* Presented in JSON output as if measured.

**Impact:** Misleading stress-test report; stakeholders may treat illustrative numbers as real.

**Fix direction:** Prefix output field with `illustrative_`, add a prominent `model_note`, or move to a separate `synthetic_assumptions` section in the report.

---

## 4.8 `synthetic_macro.py` is pure Gaussian noise

**Location:** `python/quantcore/macro/synthetic_macro.py`

**Problem:** VIX/10Y/DXY drawn from normals with illustrative thresholds. Labeled synthetic but consumed by the dashboard as a live regime signal. No path to FRED/Markov-switching.

**Impact:** Macro gating of day-trading signals is driven by random numbers.

**Fix direction:** Add a clear interface to swap in FRED API (`VIXCLS`, `DGS10`, `DTWEXBGS`) and a calibrated regime model. Until then, gate dashboard display with a "SYNTHETIC" badge.

---

## 4.9 `stat_arb.py` hardcodes a 6-symbol universe and calls yfinance per pair

**Location:** `python/quantcore/research/stat_arb.py` (`scan_universe`)

**Problem:** 15 pairs × `yf.download`. No caching beyond yfinance internals. Not configurable.

**Impact:** Slow, rate-limit-prone, inflexible.

**Fix direction:** Parameterize universe; add local parquet cache; batch downloads.

---

## 4.10 `prediction_suite.py` is a 1,146-line monolith

**Location:** `python/quantcore/research/prediction_suite.py`

**Problem:** Contains `AdvancedPredictor`, `PredictionReviewer`, `PredictionScreener`, Monte Carlo, OU, walk-forward audit. Hard to review and test.

**Impact:** High maintenance burden; correctness hard to verify.

**Fix direction:** Split into modules: `predictor.py`, `reviewer.py`, `screener.py`, `monte_carlo.py`. Add unit tests for each.

---

## 4.11 `intraday_engine.py::_generate_synthetic()` uses `np.random.seed(hash(symbol) % 2**32)`

**Location:** `python/quantcore/day_trading/intraday_engine.py`, line 78

**Problem:** `hash()` is salted per Python process (PYTHONHASHSEED), so synthetic data differs between runs unless hash seeding is controlled. Also unstable across Python versions.

**Impact:** Non-reproducible synthetic data; flaky tests/UI.

**Fix direction:** Use `np.random.default_rng(seed)` with a stable seed derived from the symbol string (e.g., `hashlib.sha256(symbol.encode()).digest()`).

---

## 4.12 Hardcoded CWD-relative paths throughout

**Location:** `backtester.py`, `gauntlet.py`, `ops.py`, `time_machine.py`, etc.

**Problem:** All assume the process is launched from the repo root (`data/raw/equities`, `data/quant_daemon.log`, `data/time_machine_report.json`).

**Impact:** Breaks when run from any other directory.

**Fix direction:** Resolve all paths relative to `BASE_DIR = Path(__file__).resolve().parents[N]` or an explicit config `DATA_DIR`.

---

## 4.13 `sys.path.insert` manipulations in multiple modules

**Location:** `analytics.py`, `test_risk_engine.py`, others

**Problem:** Runtime `sys.path` inserts are fragile and cause module-shadowing risks.

**Impact:** Unpredictable import resolution.

**Fix direction:** Use proper package installation (`pip install -e .`) or a single bootstrap path setup in `main.py` lifespan.

---

# Tier 5: FastAPI / Web Backend ([P1] High)

## 5.1 Degraded `200 {error}` responses mask failures

**Location:** `web/backend/state.py`; architecture doc

**Problem:** The app deliberately returns HTTP 200 with JSON `{"error": ...}` instead of 500 when components fail. Monitoring/uptime checks see "200 OK" while the feature is broken.

**Impact:** Silent degradation; clients must inspect body to detect failure.

**Fix direction:** Return proper HTTP 503/500 for unavailable components, or add a `X-Service-Degraded` header and a `/healthz` endpoint that reports overall health.

---

## 5.2 `ops.py` CIO metrics read a log file for veto counts

**Location:** `web/backend/api/ops.py`, lines 29–33

**Problem:** `get_cio_metrics()` opens `data/quant_daemon.log` and counts `"[SATELLITE VETO]"` strings. Log parsing is not a metrics pipeline.

**Impact:** Log rotation, missing file, or format changes break the CIO dashboard silently.

**Fix direction:** Track vetoes in memory (a thread-safe counter in `state.py`) or in DuckDB; expose via API.

---

## 5.3 `state.py` returns `None` singletons; no stubs for most

**Location:** `web/backend/state.py` (`init_state`)

**Problem:** Only `analytics` gets a `_StubAnalytics` fallback. `paper_broker`, `risk_committee`, `satellite_engine`, etc., are `None`. Any router forgetting a `None` check crashes with `AttributeError`.

**Impact:** Request-time 500 errors on partially initialized systems.

**Fix direction:** Provide null-object stubs for every singleton, or enforce `None` checks with a helper decorator.

---

## 5.4 `analytics.py` imports `quantcore.quantcore_cpp` with broad `try/except`

**Location:** `web/backend/analytics.py`, lines 19–24

**Problem:** If the C++ module is partially built or symbol-mismatched, import may succeed but methods may be missing, causing `AttributeError` deep in request handling.

**Impact:** Hard-to-debug runtime failures.

**Fix direction:** Version-check the compiled module at startup; expose a `HAS_CPP` flag that routers consult.

---

## 5.5 Control-plane auth may be weak

**Location:** `web/backend/security.py` (`require_control_access`)

**Problem:** Relies on `QUANTCORE_CONTROL_TOKEN` and loopback check. Need to verify token enforcement; if unset or loopback bypassable, kill-switch/reset endpoints are exposed.

**Impact:** Unauthorized halt/reset of trading.

**Fix direction:** Enforce token strictly; default to deny if token unset; audit loopback check.

---

## 5.6 `start_surveillance()` shells out per HTTP request

**Location:** `web/backend/api/ops.py`, line 63

**Problem:** Spawning a Python subprocess per HTTP request is heavy and can leak processes if the supervisor hangs.

**Impact:** Resource exhaustion under repeated calls.

**Fix direction:** Manage daemons via the supervisor process, not per-request subprocesses.

---

## 5.7 No OpenAPI / response-model enforcement

**Location:** `web/backend/main.py` and routers

**Problem:** Routes return ad-hoc `dict`s. FastAPI serializes anything; schema drift between backend and frontend is not caught.

**Impact:** Frontend breaks when backend response shape changes.

**Fix direction:** Add Pydantic response models for all API endpoints.

---

# Tier 6: Data Storage & Providers ([P2] Medium)

## 6.1 yfinance is primary data source with no API key / rate-limit handling

**Location:** `backtester.py`, `stat_arb.py`, `analytics.py`, `intraday_engine.py`

**Problem:** Unofficial, rate-limited API that can break when Yahoo changes endpoints. No fallback quota management beyond a 60s TTL `live_cache`.

**Impact:** Data ingestion failures in production use.

**Fix direction:** Add Stooq/CSV fallback (already documented), retry with backoff, and a configurable provider priority list.

---

## 6.2 DuckDB file locking across processes

**Location:** `web/backend/state.py` (`close_state`), `analytics.py`, `paper_broker`

**Problem:** Multiple FastAPI workers or daemons opening the same DuckDB file concurrently will hit lock errors. No multi-process locking strategy visible.

**Impact:** Database locked errors under concurrent access.

**Fix direction:** Use a single writer process, or switch to a client-server DB for concurrent scenarios, or add file-locking around DuckDB access.

---

## 6.3 `data/` directory is gitignored — no seed data ships with repo

**Location:** `data/` (gitignored)

**Problem:** Fresh clone has no market data; backtester must fetch from yfinance on first run (slow, may fail offline).

**Impact:** Out-of-box experience is degraded.

**Fix direction:** Ship a small seed dataset (e.g., SPY, QQQ parquet) in the repo or provide a `python scripts/seed_universe.py` one-liner.

---

## 6.4 Parquet datetime resolution bugs already patched but fragile

**Location:** `python/quantcore/research/backtester.py::_normalize_date`

**Problem:** Casts to `us` microseconds to avoid ns/ms join mismatches — evidence of real parquet schema-drift incidents.

**Impact:** Future provider changes can reintroduce silent join failures.

**Fix direction:** Add schema validation on read; log a warning when datetime resolution differs from expected.

---

# Tier 7: IPC / HIVEMIND BRIDGE ([P2] Medium)

## 7.1 Python `HiveMindState` ctypes struct manually mirrors C++ packed struct

**Location:** `nexus/include/shared_bridge.h`; `python/quantcore/hivemind/quant_daemon.py`

**Problem:** No shared source of truth. `static_assert(sizeof == 597)` on C++ catches size changes only, not field reordering/type changes that preserve size.

**Impact:** Silent memory corruption if layouts drift.

**Fix direction:** Generate both C++ header and Python ctypes from a single JSON/YAML schema; add a magic number/version field to the struct.

---

## 7.2 No magic number / version field in `HiveMindState`

**Location:** `nexus/include/shared_bridge.h`

**Problem:** No way to detect that a Python process wrote the struct with a different layout version than the C++ consumer expects.

**Impact:** Garbage values interpreted as real data.

**Fix direction:** Add `uint32_t magic` and `uint32_t version` at the start; validate on both sides before use.

---

## 7.3 `__atomic` operations on potentially unaligned `double` fields

**Location:** `nexus/src/main.cpp` (`atomic_load_double`, etc.)

**Problem:** Correct on x86_64, but not portable to strict-alignment architectures (ARM can fault or tear).

**Impact:** Non-portable atomic access.

**Fix direction:** Use `memcpy` to/from aligned temporaries for atomic double ops, or require aligned access.

---

# Tier 8: Testing & Quality ([P2] Medium)

## 8.1 No CI pipeline (reinforced)

**Location:** Repo-wide

**Problem:** Pytest and ctest exist locally but never run automatically.

**Impact:** Regressions merge silently.

**Fix direction:** Add GitHub Actions workflows.

## 8.2 Python tests skip when `quantcore_cpp` not built

**Location:** `tests/test_risk_engine.py` (and others using `pytest.importorskip`)

**Problem:** In a fresh clone without `setup.sh`, C++-backed tests silently skip.

**Impact:** "Passing tests" may mean "no C++ tests ran."

**Fix direction:** Run CI with and without C++; fail if expected tests are skipped.

## 8.3 C++ tests in separate build tree

**Location:** `build-cpptests/`

**Problem:** Not part of default build target; easy to forget `ctest --test-dir build-cpptests`.

**Fix direction:** Unify into one CMake project with `enable_testing()` and `add_test`.

## 8.4 No property-based or fuzz testing

**Location:** `cpp/tests/`, `python/tests/`

**Problem:** The LOB, risk engine, and SPSC queue are deterministic, stateful, concurrency-sensitive. No fuzzing or property-based tests.

**Impact:** Edge cases in concurrency and order book matching are untested.

**Fix direction:** Add Hypothesis (Python) and rapidcheck/libFuzzer (C++) tests.

## 8.5 No latency/throughput benchmarks

**Location:** `nexus/`

**Problem:** Marketed as HFT engine (lock-free SPSC, 2M ring) but no benchmarks for enqueue/dequeue latency or LOB update latency.

**Impact:** Performance claims unverified.

**Fix direction:** Add microbenchmarks (Google Benchmark or `std::chrono` harness) for queue and LOB.

---

# Tier 9: Documentation & Configuration ([P3] Low)

## 9.1 `.phase3bak` / `.phase4bak` files still on disk

**Location:** `web/templates/`, `python/quantcore/research/`, `nexus/include/`

**Problem:** Backup copies of HTML, Python, and C++ files clutter the tree and may contain stale logic/secrets.

**Fix direction:** Delete or archive them; add `*.phase*bak` to `.gitignore`.

## 9.2 Hardcoded constants scattered in code

**Location:** Risk limits (2%, 50 trades, 5 losses, 15:55 ET), slippage (`η=0.15`), SOR split (70/30), Almgren-Chriss multipliers.

**Fix direction:** Centralize in `config/system.yaml` and load at startup; expose overrides via env vars.

## 9.3 `config/system.yaml` not deeply reviewed

**Location:** `config/system.yaml`

**Fix direction:** Audit that all hardcoded constants above are actually bound to YAML keys.

---

# Tier 10: Security & Operations ([P2] Medium)

## 10.1 Audit ledger explicitly not tamper-proof

**Location:** `nexus/include/audit_ledger.h`; README transparency table

**Problem:** FNV-1a is order verification only. Forgeable in O(n).

**Fix direction:** Either upgrade to SHA-256/OpenSSL or prominently label as non-tamper-evident in all user-facing docs and API outputs.

## 10.2 Kill switch is an unprotected file flag

**Location:** `web/backend/api/ops.py` (`kill_switch`, `reset`)

**Problem:** `data/surveillance_halt.flag` written/deleted with no atomicity, signing, or broadcast to running Nexus threads.

**Fix direction:** Use an atomic write (temp file + rename); broadcast halt state via the HiveMind bridge or a pub/sub channel; require signed control token.

## 10.3 Surveillance/quant daemons use file-based signaling

**Location:** `data/surveillance_halt.flag`, `data/ghost_trigger.json`, log-file grep

**Problem:** Race-prone, not observable.

**Fix direction:** Replace with the supervisor's IPC or a lightweight message bus.

## 10.4 No TLS/mTLS on local control plane

**Location:** `web/backend/main.py` (binds `127.0.0.1:8765`)

**Problem:** Limited network exposure, but any local user/process can hit the API. Control token is the only auth.

**Fix direction:** Document local-only binding; consider Unix socket instead of TCP.

---

# Suggested Execution Order (Next Up)

| Phase | Focus | Key Items |
|-------|-------|-----------|
| **1** | Stop the bleeding | 3.1 (GhostExchange one-shot), 2.1 (equity rollover), 1.3 (CI), 1.1 (offline build) |
| **2** | Make degraded mode honest | 5.1 (HTTP 503), 5.3 (singleton stubs), 4.2 (no silent NaN→0), 2.5 (SQL injection) |
| **3** | Harden C++ core & Nexus | 2.2 (ET timestamps), 2.4 (MARKET orders), 3.2–3.8 (SPSC, ledger, mmap, sleep) |
| **4** | Python research robustness | 4.1–4.13 (satellite import, backtester, paths, monolith, etc.) |
| **5** | Observability & ops | 5.2 (log parsing), 5.6 (subprocess per request), 10.2–10.4 (kill switch, TLS) |
| **6** | Cleanup & docs | 9.1–9.3 (bak files, constants, config), 8.4–8.5 (fuzz, benchmarks) |

---

**End of Masterplan.** No files were modified during this assessment. This document is intended as a backlog for the next round of work.
