# QuantCore 1.0

QuantCore is an open-source quantitative research and simulation platform. It is released under the MIT License. Contributions are welcome, and the project is maintained as a community-driven portfolio piece and educational tool. **No real capital is ever at risk.**

## Overview

QuantCore is a modular quantitative research, simulation, paper-trading, and execution platform. It combines a C++20 computation and execution engine with a Python research layer and a FastAPI dashboard, all running locally.

### Goals

- Reproducible quantitative research
- Reliable backtesting
- Paper trading
- Modular architecture
- Operational transparency

## Features

- Historical data ingestion with provider fallback (yfinance → Stooq) and a durable local cache
- Technical indicators and vectorized feature generation (C++)
- Portfolio analytics: Hierarchical Risk Parity, Deflated Sharpe Ratio
- Risk management: Risk Committee gauntlet (overfit, stress, friction checks)
- Paper broker with DuckDB ledger and Almgren-Chriss slippage model
- Replay / stress-testing engine (Time Machine)
- C++20 HFT engine (Nexus) with a lock-free queue and live WebSocket ingest
- Dashboard with 20+ pages and a REST API

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
bash setup.sh          # builds C++ engines, installs deps, seeds data
python3 infra_tui.py   # Infrastructure TUI — press W for the Web UI
```

Then open http://127.0.0.1:8765. See `USER_GUIDE.md` for the full walkthrough.

## Architecture at a glance

- **C++ core** — `quantcore_cpp` (DuckDB data engine, feature engine, risk engine) and `nexus_core` (HFT engine: SPSC ring buffer, limit order book, microstructure sim, Binance ingest).
- **Python research** — backtester, HRP, Deflated Sharpe Ratio, StatArb, alpha hunter, volatility desk.
- **FastAPI backend** — seven routers with shared state; local-only control plane.
- **IPC** — a layout-verified 597-byte memory-mapped bridge between Python and C++.

See `ARCHITECTURE.md` for details.

## Project status

Version 1.0 is the first stable public release. Some advanced modules are experimental and clearly marked `EXP` in the navigation. See `RELEASES.md` for what changed and `ROADMAP.md` for what's next.

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
| **Backtester, DSR, HRP, Black-Scholes** | Real math, real historical data (via yfinance/Stooq fallback) |
| **Satellite RSS Feed** | Real financial RSS (CNBC, MarketWatch) + VADER NLP sentiment |
| **Paper Broker Fills** | Simulated against mock prices + Almgren-Chriss slippage model |
| **Nexus LOB & Bookmap** | Simulated microstructure (synthetic Poisson order flow) |
| **Macro Desk & Time Machine** | Synthetic regimes and Monte Carlo stress tests |
| **RL Execution Policy** | Hand-tuned heuristic surrogate (PPO distillation TODO) |
| **Audit Ledger** | Polynomial hash chain (order-verified, NOT cryptographically tamper-proof) |

## Disclaimer

QuantCore is an educational and research tool, not investment advice. Paper trading only — no live-broker defaults, and no real capital is ever at risk.
