```bash# ⚡ QuantCore

**A local, institutional-grade quantitative trading research & simulation platform.**

`C++20 HFT Core` · `Python Research Brain` · `FastAPI Dashboard` · **v1.0.0-RC4**

> QuantCore simulates the full lifecycle of a multi-strategy quantitative hedge fund on a single workstation — data ingestion, factor research, backtesting, statistical arbitrage, portfolio construction, risk validation, and simulated execution — bridging a lock-free C++20 engine and a vectorized Python research brain through zero-copy shared memory.
>
> **This is a research and simulation platform. No real capital is ever at risk.**

---

## Status

**v1.0.0 Release Candidate 4.** The architecture is stable and the core pipeline is proven end-to-end. Recent hardening includes a modular API-router migration, a multi-provider data layer (yfinance → Stooq fallback), centralized structured logging, an activated Deflated Sharpe Ratio overfit detector, and NaN-safety across every analytics endpoint. See [CHANGELOG.md](CHANGELOG.md) for the full history.

---

## What's Inside

Organized by institutional function (mirrors the dashboard navigation):

### 🖥️ Command Center
- **Dashboard** — portfolio overview, live signals, system health
- **Paper Trading Desk** — realistic fills with Almgren-Chriss slippage, a DuckDB ledger, and Alpaca paper integration
- **CIO War Room** — P&L attribution waterfall, execution alpha, rolling Sharpe
- **Signals** — aggregated trading signals across the universe

### 🔬 Alpha & Research
- **Backtest Lab** — cross-sectional momentum factor backtester with transaction costs and look-ahead-bias-free evaluation
- **StatArb Crucible** — Engle-Granger cointegration, Ornstein-Uhlenbeck half-life, purged cross-validation
- **Research Lab** — Hierarchical Risk Parity (HRP) allocation + Deflated Sharpe Ratio (DSR) overfit detection
- **Volatility Desk** — 3D vol surface, synthetic options chain, theta-harvest simulator (Black-Scholes)
- **Alpha Lab** — lead-lag information-flow detection via cross-correlation
- **Alpha Decay Monitor** — rolling model health with auto-quarantine
- **Trends & Predictions** — z-score mean-reversion signals and forecast horizons

### ⚙️ Execution & HFT
- **Nexus HFT Core** — C++20 lock-free engine, SPSC ring buffers, live Binance WebSocket ingest, Bookmap-style LOB heatmap
- **Ghost Exchange** — microstructure stress test modeling Almgren-Chriss impact, queue position, and adverse selection
- **Execution Algos** — TWAP / VWAP / Market order-slicing simulator
- **Day Trading Desk** — intraday VWAP, Opening Range Breakouts, tactical scanner, Wilder's RSI
- **RL Execution Lab** — PPO agent for slippage minimization, exported as a C++ decision tree

### 🛠️ Infrastructure
- **Hive-Mind IPC** — zero-copy `mmap` shared-memory bridge between the Python quant daemon and the C++ trader (597-byte struct, compile-time verified)
- **Level 4 Sim** — agent-based microstructure digital twin with a hash-chained audit ledger
- **Institutional Ops** — kill switch, Smart Order Routing (lit/dark), regulatory surveillance
- **Time Machine** — historical stress testing (2022 Crypto Winter, 2020 Pandemic)
- **Satellite Lab** — NLP news sentiment (live RSS + VADER) and synthetic on-chain whale flow
- **Macro Desk** — synthetic yield/regime monitor

> **PRO / LEARN mode** — every page toggles between a dense professional view and an educational mode that highlights quant concepts and opens an interactive **Mini-Wiki** (Day-Trader vs. Wall-Street translations).

### 🛡️ The Risk Gauntlet
Every strategy must survive an automated committee before "deployment":
1. **Minimum Sharpe floor** — rejects garbage submissions
2. **Deflated Sharpe Ratio** — penalizes for multiple testing (backtest-overfitting detection)
3. **Time Machine stress test** — hard 20% drawdown mandate under historical crash regimes
4. **High-friction slippage test** — strategy must stay profitable at 15 bps execution cost

---

## Architecture

Three execution domains communicating via shared memory and high-speed IPC:

```
┌─────────────────────────────────────────────────────────────┐
│  FastAPI Dashboard (web/)                                     │
│  7 modular API routers · Jinja2 + Plotly · WebSocket tape     │
│  analytics · research · broker · execution · ops · infra · ws │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│  Python Research Brain (python/quantcore/)                    │
│  Polars · DuckDB · SciPy · yfinance + Stooq fallback          │
│  Backtester · HRP · StatArb · Risk Gauntlet · MLOps           │
└───────────────────────────┬─────────────────────────────────┘
                            │  mmap shared memory (597-byte struct)
┌───────────────────────────▼─────────────────────────────────┐
│  C++20 Nexus Engine (nexus/)                                  │
│  SPSC queues (2M) · LOB · Ghost Exchange · Binance WS ingest  │
│  GCC 13 · -O3 -march=native -flto                             │
└─────────────────────────────────────────────────────────────┘
```

**Concurrency model:**
- **Shared-memory IPC** — the Python `quant_daemon` and C++ `nexus_core` share a packed `HiveMindState` struct. Python writes target weights; C++ reads and executes, writing slippage feedback atomically. The layout is guarded by a C++ `static_assert` and a Python runtime offset check.
- **Lock-free hot path** — single-producer/single-consumer ring buffers with 64-byte `alignas` padding to prevent cache-line false sharing.
- **DuckDB concurrency** — serialized via a reentrant lock to prevent corruption under threaded access.

> 📖 Read the full design and the vibe-coding manifesto in [ARCHITECTURE.md](ARCHITECTURE.md).

---

## Quick Start

**Prerequisites:** WSL2 / Ubuntu 22.04+, Python 3.10+ (3.12 tested), `build-essential`, `cmake`, `libssl-dev`, `zlib1g-dev`, GCC 13.

```bash
# 1. Build everything: compile C++ engines, install the Python stack, seed the data universe
./setup.sh

# 2. Launch the web dashboard → http://127.0.0.1:8765
./run_web.sh

# 3. (Optional) Prove the full pipeline headless: data → backtest → risk gauntlet
python3 quickstart.py

# 4. (Optional) Launch the full "firm" in tmux: Nexus + quant daemon + web UI
./start_firm.sh

# 5. (Optional) Infrastructure control TUI (start / stop / kill-switch / logs)
python3 infra_tui.py
```

See [SETUP.md](SETUP.md) for troubleshooting and performance expectations.

---

## Repository Layout

```
QuantCore/
├── nexus/                  # C++20 HFT engine (SPSC, LOB, Ghost Exchange, WS ingest)
│   ├── src/main.cpp
│   └── include/            # spsc_queue, limit_order_book, ghost_exchange,
│                           # shared_bridge, audit_ledger, institutional_ops, rl_policy
├── cpp/                    # pybind11 analytics extensions (DuckDB, features, risk)
│   ├── src/                # data_engine, feature_engine, risk_engine, event_bus, bindings
│   └── include/quantcore/
├── python/quantcore/       # Research brain
│   ├── research/           # backtester, validation (DSR), alpha_hunter, stat_arb
│   ├── portfolio/          # HRP optimizer
│   ├── risk/               # Risk Committee gauntlet
│   ├── broker/             # paper broker + DuckDB ledger + Alpaca
│   ├── vol/                # Black-Scholes, vol surface
│   ├── data/               # provider (yfinance → Stooq), seed_guard
│   ├── hivemind/           # shared-memory quant daemon
│   ├── day_trading/        # intraday engine, signals, backtester
│   ├── replay/             # time-machine stress tests
│   ├── mlops/              # alpha-decay monitor
│   ├── macro/ alt_data/ nlp/ rl/ ops/ cio/ execution/ strategy/
│   └── logging_config.py   # centralized structured logging
├── web/
│   ├── backend/            # FastAPI app + 7 API routers + state.py + schemas.py
│   ├── templates/          # 20+ Jinja2 dashboard pages
│   └── static/
├── config/system.yaml
├── tests/                  # pytest suite
├── setup.sh                # one-click build + seed
├── run_web.sh              # launch dashboard
├── start_firm.sh           # launch full stack in tmux
├── infra_tui.py            # infrastructure control TUI
├── quickstart.py           # headless pipeline proof
└── CMakeLists.txt
```

---

## Technology Stack

| Layer | Technologies |
|-------|-------------|
| **HFT Core** | C++20, pybind11, ixwebsocket, nlohmann/json, spdlog, OpenSSL |
| **Research Brain** | Python 3.12, Polars, DuckDB, NumPy, SciPy, scikit-learn, LightGBM, statsmodels |
| **Data** | yfinance (primary) + Stooq CSV (fallback), Apache Arrow / Parquet |
| **Web** | FastAPI, Uvicorn, Jinja2, Plotly, Tailwind CSS, WebSockets |
| **ML** | PyTorch, LightGBM, Stable-Baselines3 (PPO), VADER sentiment |
| **Build** | CMake 3.24+, FetchContent, GCC 13 |

---

## Testing

```bash
pytest -v
```

The suite (11 tests across 5 modules) covers:
- **Black-Scholes** — put-call parity, Greek bounds
- **Validation** — Deflated Sharpe Ratio significance vs. overfit rejection
- **Backtester & Analytics** — graceful failure on single-asset / missing data, NaN/Inf JSON sanitization
- **Broker** — fill execution, insufficient-funds rejection, algo-based slippage
- **Portfolio** — HRP weights sum to one

---

## AI Disclosure

This repository was developed almost entirely through AI-assisted ("vibe-coding") workflows. I did **not** hand-write the majority of the source code. Instead, I acted as the systems architect — defining the physics (Almgren-Chriss impact, Ornstein-Uhlenbeck mean reversion), enforcing the concurrency model (lock-free SPSC queues), and demanding institutional realism (Risk Gauntlets, Deflated Sharpe Ratios) — while iteratively guiding AI (primarily Qwen) to implement those ideas.

This repository is therefore as much an experiment in AI-assisted software engineering as it is a quantitative finance project.

---

## Current Scope & Limitations

QuantCore is a release candidate, not production trading software. Honest boundaries:

- **Broker integration** — Alpaca is paper-only and credential-only; not live-trading tested. Live trading would require additional safety guards.
- **Data sources** — yfinance is the primary feed with an automatic Stooq CSV fallback for daily US-equity/crypto data. Intraday intervals still depend on yfinance; both are best-effort free feeds subject to rate limits.
- **Synthetic components** — the Macro Desk, Time Machine crash paths, on-chain whale flow, and the C++ microstructure simulator use synthetic/random data. The Satellite Lab's news sentiment is real (live RSS + VADER); its whale flow is synthetic.
- **RL & stubs** — the RL Execution Lab exports a surrogate decision tree; some modules are structural placeholders that fail gracefully.
- **Audit ledger** — the C++ hash chain is simulation-grade (polynomial mix): sufficient for corruption detection and event ordering, but **not** cryptographic tamper-evidence.
- **Paper-broker pricing** — fills use a mock price table unless a live price is supplied.

---

## Disclaimer

This software is for research and educational purposes only. Nothing in this repository constitutes financial advice. Use at your own risk.

## License

GPLv3

---

## Screenshots

<img width="3413" height="1243" alt="Screenshot 2026-06-27 130117" src="https://github.com/user-attachments/assets/27122353-1743-4b9c-8af8-4823be7627d1" />
<img width="3418" height="1245" alt="Screenshot 2026-06-27 130137" src="https://github.com/user-attachments/assets/abb5e1cc-69fe-43be-ad35-1211d74ea25d" />
<img width="3415" height="1246" alt="Screenshot 2026-06-27 130215" src="https://github.com/user-attachments/assets/1cb484bb-e982-4cfb-94d7-3436de12986a" />
<img width="3438" height="1252" alt="Screenshot 2026-06-27 130229" src="https://github.com/user-attachments/assets/1d8d240d-6e96-4eb9-92db-4a6bf7cca5b3" />
<img width="3438" height="1247" alt="Screenshot 2026-06-27 130255" src="https://github.com/user-attachments/assets/9de558f8-d151-478c-bec5-e28d0a63ddf3" />
<img width="3420" height="1252" alt="Screenshot 2026-06-27 130326" src="https://github.com/user-attachments/assets/020e03d3-83b0-4daa-9247-92ca563de588" />
<img width="3432" height="1252" alt="Screenshot 2026-06-27 130404" src="https://github.com/user-attachments/assets/f1913b05-035e-47eb-94f9-d1fe7aeea211" />
<img width="3413" height="1245" alt="Screenshot 2026-06-27 130512" src="https://github.com/user-attachments/assets/7040f66a-92f8-4ca6-9318-a0e0d6092771" />
