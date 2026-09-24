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

## The dashboard (1.1 Power UI)

Open http://127.0.0.1:8765. Top bar: `⌘K`/ `Ctrl+K` command palette (jump anywhere, `>action`), `/` quick symbol jump, `◫▭▢` density (`compact/comfortable/spacious` → CSS `--qc-*`), `◐` theme `light/dark`, sidebar `280px` with filter, `★` favorites, recent. Footer status bar shows latency + UTC.

Keyboard: `G D` Dashboard, `G P` Paper, `G T` Day Trading, `G N` Nexus, `G S` Signals, `Alt+T/D/Y` theme/density/copy, `?` help, `Esc` close. Tables: click header to sort, `dblclick` row to copy. `R` refreshes current view. `Y` copies link. All persisted in `localStorage` (`qc_prefs`, `qc_favs`, `qc_recent`).

Navigation is grouped by institutional function:

- **Command Center** — Dashboard, Paper Desk, CIO War Room, Signals
- **Alpha & Research** — Trends, Predictions, Backtest Lab, Volatility Desk, Alpha Decay, Alpha Lab, StatArb Crucible, Research Lab
- **Execution & HFT** — Execution Algos, Nexus HFT, Day Trading Desk (RVOL/Gap/Delta + macro gating), RL Execution
- **Infrastructure** — Hive-Mind, Level 4 Sim, Institutional Ops, Satellite Lab, Macro Desk, Time Machine

Toggle **PRO / LEARN** mode in the top-right. LEARN mode highlights concepts and opens a mini-wiki explaining each term (day-trader translation vs. Wall Street reality).

> If `quantcore_cpp` not built, web still boots via Python fallback (`_FallbackFeatureEngine` — slower but functional, `200 {error}` not 500). Build for acceleration: `mkdir -p build && cmake .. && make -j$(nproc) && cp build/quantcore_cpp*.so python/quantcore/`.

## Paper trading

QuantCore ships paper-only. The Paper Desk simulates fills with an Almgren-Chriss slippage model and records every fill in a DuckDB ledger. No real capital is at risk, and no broker credentials are persisted unless you explicitly connect Alpaca's paper API.

## Typical workflow (day-trading)

1. Add symbols (Dashboard → Add Symbol or `⌘K` → `>Jump to AAPL`) or rely on seeded universe.
2. Day Trading Desk: check `RVOL` (≥1.5x), `GAP` (±1% + drive), `ORB` (true 30m), `VWAP ±1/2σ`, `DELTA` confirmation, `POC` — macro gate shows `RISK-OFF`/`STAGFLATION` filter note.
3. Trends/Predictions: session-anchored VWAP; prediction suite uses Wilder ATR + log OU gravity.
4. Backtest Lab → Run with `60d lookback`, then Risk Committee gauntlet (`DSR T=n_obs`, strategy-aware stress `-50/-35/-30%`, relative friction `drag<10pp`).
5. Paper-trade via Paper Desk or Day Trading `Quick Scalp Ticket` (`SCALP LONG/SHORT` → `VWAP` `η=0.15`).
6. Monitor `CIO War Room` (real `sharpe = mean/std·√252`), `Tactical Scanner` (`GAP UP/DOWN + DRIVE` priority, `R` refresh, `Export`), Nexus `p99` tail.

Classic research workflow still: Trends → Predictions → Backtest → Gauntlet → Paper → CIO.

## What is real vs. simulated

See the transparency table in `README.md`. In short: the research math (backtester, HRP, DSR, Black-Scholes) and historical data are real; the microstructure, macro, and several ops desks are clearly-labeled simulations.
