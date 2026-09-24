# QuantCore 1.2

QuantCore is an open-source quantitative research and simulation platform. It is released under the MIT License. Contributions are welcome, and the project is maintained as a community-driven portfolio piece and educational tool. **No real capital is ever at risk.**

## Overview

QuantCore is a modular quantitative research, simulation, paper-trading, and execution platform. It combines a C++20 computation and execution engine with a Python research layer and a FastAPI dashboard, all running locally. **V1.2 is a day-trading-first release** — macro depth with micro execution.

### Goals

- Reproducible quantitative research
- Reliable backtesting (no look-ahead, correct DSR)
- Paper trading with unified Almgren-Chriss slippage
- Day-trading edge: RVOL, ORB, VWAP bands, delta & queue imbalance, macro gating
- Modular architecture + operational transparency (real vs. synthetic disclosed)

## Features

- Historical data ingestion with provider fallback (yfinance → Stooq) and a durable local cache; **tick store** (`data/ticks.duckdb`) for session-anchored intraday bars
- Technical indicators and vectorized **microstructure** feature generation (C++): `OBI`, `queue_imbalance`, `cumulative_delta`, `delta_imbalance`, `kyle_lambda`, `effective_spread`, `VPIN`, `parkinson/garman-klass` vol, session `volume_profile` (POC/VAH/VAL), `rvol` (time-of-day curve)
- Portfolio analytics: **Hierarchical Risk Parity** (inverse-variance cluster, Lou de Prado) + **Deflated Sharpe Ratio** (Lo 2002, `T=n_obs` not `252`)
- Risk management: Risk Committee gauntlet (overfit, **strategy-aware** stress, **relative** friction) + session-aware `RiskEngine` (intraday loss, `max_trades/day`, `max_consecutive_losses`, `flat_deadline 15:55 ET`, hold-time)
- Paper broker with DuckDB ledger, unified `η=0.15` slippage (MARKET×3.0, VWAP×0.43, TWAP×1.2) + `ADV` per asset
- Replay / stress-testing engine (Time Machine) — recalibrated crashes (`-1.5%` not `-2.5%`, non-deterministic)
- C++20 HFT engine (Nexus) with lock-free SPSC (2M), price-keyed LOB (quantized, walk-back), microstructure sim (unified η), audit hash chain (FNV-1a + mutex), Binance ingest, ghost exchange
- Dashboard 1.1 — **power-user UI**: command palette (`⌘K`), keyboard `G D/P/T/N/S`, `Alt+T/D/Y`, sidebar favorites/recent, density `◫▭▢`, `light/dark` themes, sortable `qc-table` (dbl-click copy), toasts, skeletons, `light` RPATH fallback
- 20+ pages + REST API with Python fallback if `quantcore_cpp` not built (web stays up, degraded `200 {error}` not 500)

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
bash setup.sh          # builds C++ engines, installs deps, seeds data
python3 infra_tui.py   # Infrastructure TUI — press W for the Web UI
```

Then open http://127.0.0.1:8765. See `USER_GUIDE.md` for the full walkthrough.

## Architecture at a glance

- **C++ core** — `quantcore_cpp` (DuckDB data engine, feature engine — 12 methods —, session-aware risk engine) and `nexus_core` (SPSC ring buffer, quantized price LOB, microstructure sim, ghost exchange, audit ledger, RL policy, Binance ingest).
- **Python research** — backtester (lagged weights), HRP (inverse-variance), Deflated Sharpe Ratio (correct `T`), StatArb (intercept-aware spread, purged CV lagged), alpha hunter (demeaned Pearson), volatility desk (Black-Scholes with `rho`, `vega/theta` dual conventions), prediction suite (Wilder ATR, log OU drift, tick-aggregated bars), tick store (DuckDB).
- **FastAPI backend** — seven routers with resilient `state.init_state` (per-singleton try/except, stub fallback) + pure-Python fallback if C++ not built; local-only control plane with `QUANTCORE_CONTROL_TOKEN`.
- **IPC** — layout-verified 597-byte `HiveMindState` (`pack(1)`, `static_assert 597`) + atomic double helpers for unaligned mmap.

See `ARCHITECTURE.md` for details.

## Project status

Version 1.2 is the day-trading-first stable release. Some advanced modules remain `EXP`. See `RELEASES.md` for what changed and `ROADMAP.md` for what's next.

## Documentation

| File | Contents |
|---|---|
| `USER_GUIDE.md` | Install, launch, and use |
| `ARCHITECTURE.md` | Layers and data flow |
| `DEVELOPER_GUIDE.md` | Repo layout and how to extend |
| `CONFIGURATION.md` | Config and environment variables |
| `TROUBLESHOOTING.md` | Known issues and fixes |
| `STABILITY_PLAN.md` | Operational defaults |
| `RELEASES.md` | Release history |

## What's real vs. simulated

Transparency is a core design principle. Here is exactly what is computed from real-world data versus what is synthetically generated for educational and architectural demonstration:

| Component | Status |
|---|---|
| **Backtester, DSR (Lo 2002 `T=n_obs`), HRP (inverse-variance), Black-Scholes (`rho`, dual theta/vega)** | Real math, real historical data (via yfinance/Stooq fallback + 60s TTL cache) |
| **Intraday VWAP/RVOL/Gap/Delta, Volume Profile POC/VAH/VAL, Parkinson/Garman-Klass** | Real from `ticks`/`1m` bars, session-anchored |
| **Microstructure (`OBI`, `queue_imbalance`, `kyle_lambda`, `VPIN`, `effective_spread`)** | Real formulas, synthetic order flow until L2 depth subscribed |
| **Satellite RSS Feed** | Real financial RSS (CNBC, MarketWatch) + VADER with calibrated confidence `0.5+0.35|compound|` |
| **Paper Broker Fills** | Simulated against mock/live prices + unified `η=0.15` Almgren-Chriss (MARKET×3.0/VWAP×0.43/TWAP×1.2) |
| **Nexus LOB & Bookmap** | Order-book logic real (quantized map, walk-back), flow synthetic Poisson `500(1+10σ)` |
| **Macro Desk & Time Machine** | Synthetic regimes / recalibrated crashes (`-1.5%` not `-2.5%`, non-deterministic, strategy-aware option) |
| **RL Execution Policy** | Heuristic surrogate with documented thresholds (`GHRP`); PPO ONNX export via `python/quantcore/rl/export_cpp.py` |
| **Audit Ledger** | FNV-1a hash chain + `prev_hash` mixing + mutex (order-verified, NOT SHA-256 tamper-proof) |
| **Tick Store** | DuckDB `ticks`/`bars_1m`/`tod_volume` (1m → 5m/15m aggregation, 24-bin profile) |

## Disclaimer

QuantCore is an educational and research tool, not investment advice. Paper trading only — no live-broker defaults, and no real capital is ever at risk.
