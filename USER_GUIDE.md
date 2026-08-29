# User Guide

This guide walks you through installing, launching, and using QuantCore.

## Requirements

- Linux (tested on Ubuntu / WSL2)
- Python 3.12 (pyenv recommended)
- GCC 13+ and CMake 3.24+
- Several GB of free disk and RAM for the build (DuckDB compiles from source)

## Installation

1. Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Run the setup script. It installs system build tools and Python dependencies, compiles the C++ analytics engine and the Nexus HFT engine, and seeds the starter universe (SPY, QQQ, IWM, GLD, TLT, BTC-USD, ETH-USD):

```bash
bash setup.sh
```

## First launch

With the venv active, start the Infrastructure TUI:

```bash
source .venv/bin/activate
python3 infra_tui.py
```

From the TUI:

| Key | Action |
|---|---|
| `W` | Start the Web UI (dashboard on http://127.0.0.1:8765) |
| `1` / `2` | Start / stop the Nexus C++ engine |
| `3` | Start the Hive-Mind quant daemon |
| `A` | Start the entire stack |
| `S` | Stop everything |
| `K` | Kill switch — halts all processes immediately |

To launch just the dashboard without the TUI:

```bash
bash run_web.sh
```

## The dashboard

Open http://127.0.0.1:8765. Navigation is grouped by institutional function:

- **Command Center** — Dashboard, Paper Desk, CIO War Room, Signals
- **Alpha & Research** — Trends, Predictions, Backtest Lab, Volatility Desk, Alpha Decay, Alpha Lab, StatArb Crucible, Research Lab
- **Execution & HFT** — Execution Algos, Nexus HFT, Day Trading Desk, RL Execution
- **Infrastructure** — Hive-Mind, Level 4 Sim, Institutional Ops, Satellite Lab, Macro Desk, Time Machine

Toggle **PRO / LEARN** mode in the top-right. LEARN mode highlights concepts and opens a mini-wiki explaining each term (day-trader translation vs. Wall Street reality).

## Paper trading

QuantCore ships paper-only. The Paper Desk simulates fills with an Almgren-Chriss slippage model and records every fill in a DuckDB ledger. No real capital is at risk, and no broker credentials are persisted unless you explicitly connect Alpaca's paper API.

## Typical workflow

1. Add symbols (Dashboard → Add Symbol) or rely on the seeded universe.
2. Explore Trends and Predictions.
3. Run a backtest in the Backtest Lab.
4. Submit the result to the Risk Committee gauntlet.
5. Paper-trade via the Paper Desk.
6. Monitor execution quality in the CIO War Room.

## What is real vs. simulated

See the transparency table in `README.md`. In short: the research math (backtester, HRP, DSR, Black-Scholes) and historical data are real; the microstructure, macro, and several ops desks are clearly-labeled simulations.
