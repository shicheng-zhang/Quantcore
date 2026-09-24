# Architecture

QuantCore is organized into six layers. Each can evolve independently, keeping research, execution, and presentation loosely coupled.

## Layers

1. **Data providers** — yfinance (primary) with automatic Stooq CSV fallback. Local caches: parquet `data/raw/equities/` (daily, durable) + DuckDB tick store `data/ticks.duckdb` (`ticks`, `bars_1m` aggregated to `5m/15m/1h`, `tod_volume` per 5m slot for `rvol`). Provider fallback includes 60s TTL `live_cache` to avoid hammering.
2. **Storage** — DuckDB for `analytics.db` + `paper_broker.duckdb` + `ticks.duckdb`; parquet for history; memory-mapped `HiveMindState` 597B (`pack(1)`, `static_assert`) between Python/C++ with atomic double helpers for unaligned doubles.
3. **C++ computational core** — two engines:
   - `quantcore_cpp` (pybind11): `DataEngine` (parquet view, SQL whitelist), `FeatureEngine` (12 methods: `rolling_mean/std/zscore` (NaN prefix), `order_book_imbalance`, `queue_imbalance`, `cumulative_delta`, `delta_imbalance`, `kyle_lambda`, `effective_spread_bps`, `vpin`, `intraday_volume_profile` (24-bin POC/VAH/VAL), `rvol`, `aggregate_ticks_to_bars`, `parkinson`/`garman_klass`), `RiskEngine` (post-trade concentration, `max_intraday_loss 2%`, `max_trades/day 50`, `max_consecutive_losses 5`, `flat_deadline 15:55 ET`, `hold 120m`, session TOD checks).
   - `nexus_core`: SPSC `2M` ring (`head/tail` 64B padded), quantized price LOB `map<double,PriceLevel>` (`cent` tick, `MAX 1024/side`, walk-back), `MicrostructureSim` (unified `η=0.15, ADV=50000`), `GhostExchange` (queue `child/1000*(1+10σ)`), `InstitutionalOps` SOR `70/30` lit/dark (`0.5-2.0bps` improvement via `thread_local mt19937`), `MerkleLedger` FNV-1a + `prev_hash` mixing + `mutex`, `RLPolicy` clamped thresholds, Binance `wss://stream.binance.com:9443/ws/btcusdt@trade` with auto-reconnect.
4. **Python research layer** — backtester (lagged `w_{t-1}·r_t`, `turnover L1/2`), HRP (inverse-variance `w=1/σ²/Σ1/σ²`), Deflated Sharpe Ratio (`Var=(1-skew·SR+(kurt-1)/4·SR²)/T`, `T=n_obs`), StatArb (`y-βx-α`, `HL=-ln2/λ`, purged CV lagged), alpha hunter (demeaned Pearson `r(k)`), VolSurface (synthetic `0.05m+0.10m²` disclosed), Black-Scholes (`rho`, `vega/vega_1pct`, `theta_calendar/trading`), `prediction_suite` (Wilder ATR `ewm α=1/14`, OU `θ(μ-P)dt` without `×10`, log gravity), `TickStore` (DuckDB).
5. **FastAPI backend** — seven routers (analytics, ws, infra, ops, execution, research, broker) with resilient `state.init_state` (per-singleton `try/except`, stub `Analytics` + Python fallback if `quantcore_cpp` missing → `200 {error}` not 500 crash), `require_control_access` loopback/token, `asyncio.to_thread` for blocking.
6. **Dashboard / UI 1.1** — Jinja2 + Plotly + Tailwind, `PRO/LEARN` wiki drawer + **power-user layer**: top bar (`⌘K` palette, `/` symbol jump, `Alt+T/D/Y`), collapsible sidebar (`280px`, filter, favorites `★`, recent `G` history), `◫▭▢` density (`compact/comfortable/spacious` via CSS vars `--qc-*`), `light/dark` themes, `qc-table` sortable (`dblclick` copy), `qc-toast`, `skeleton`, status bar, `skip-link`, `light` RPATH fallback.

## Data flow

```
Market data (yfinance/Stooq → local parquet → tick store ticks/bars_1m)
  -> provider fallback + TickStore aggregation (1m →5m/15m)
  -> DuckDB views + intraday volume profile (24-bin, POC/VAH/VAL)
  -> feature generation (C++ 12 methods + VWAP/TOD) or Python fallback if quantcore_cpp missing
  -> strategy / research (backtester lagged, HRP inverse-var, DSR T=n_obs, StatArb β+α, alpha demeaned)
  -> risk checks (C++ session-aware: intraday loss 2%, consecutive losses 5, flatDeadline)
  -> paper broker / execution (unified η=0.15, ADV 50k/1e6)
  -> dashboard 1.1 power UI (command palette, sortable tables, skeletons) + REST API (degraded 200 {error} not 500)
```

## Inter-process communication

The Hive-Mind bridge links Python and C++ through a packed 597-byte memory-mapped struct (`data/hivemind.dat`). Both sides verify the layout at startup: Python asserts each field offset, and the C++ header carries a matching `static_assert`. This catches struct drift before it causes silent corruption.

## Process management

A single local supervisor (`python/scripts/supervisor.py`) owns child PIDs for `web`, `nexus`, `hivemind`, and `surveillance`. The Infrastructure TUI terminates processes by exact PID rather than pattern-matching, so stopping one service never touches unrelated processes.

## Key directories

```
cpp/          C++ analytics core (pybind11 module)
nexus/        C++ HFT engine
python/       quantcore package (research, broker, data, strategies)
web/          FastAPI backend + templates + static assets
config/       system.yaml
data/         runtime data, caches, logs (gitignored)
tests/        pytest suite
```
