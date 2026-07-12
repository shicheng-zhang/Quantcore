# 🏛️ QuantCore Architecture & "Vibe-Coding" Manifesto

Welcome to the architectural blueprint of **QuantCore**. 

This document serves as both a technical breakdown of the system's infrastructure and a manifesto on the **"Vibe-Coding"** methodology used to build it. QuantCore was not built by manually typing thousands of lines of boilerplate. It was architected by a human CTO directing an AI pair-programmer to build a multi-lingual, institutional-grade quantitative trading simulation from scratch.

---

## 🧠 The "Vibe-Coding" Methodology
"Vibe-coding" is the practice of acting as the Systems Architect and CTO, while delegating the syntactical implementation to an AI. 
- **The Human Role:** Define the boundaries, dictate the physics (e.g., Almgren-Chriss slippage, Ornstein-Uhlenbeck mean reversion), enforce concurrency models (lock-free SPSC queues), and demand institutional realism (Risk Gauntlets, Deflated Sharpe Ratios).
- **The AI Role:** Generate the C++20 templates, write the Pybind11 bindings, configure the CMake toolchains, and wire the FastAPI WebSockets.

This project proves that a single developer, armed with an AI and a deep understanding of market microstructure, can build a stack that rivals the architectural fidelity of mid-tier prop shops.

---

## 🏗️ System Architecture

QuantCore is divided into three distinct execution domains, communicating via shared memory and high-speed IPC.

### 1. The Muscle: C++20 HFT Core (`nexus/`)
The low-latency execution engine. It operates entirely outside the Python GIL.
- **SPSC Ring Buffers:** Lock-free, single-producer/single-consumer queues with 64-byte `alignas` padding to prevent CPU cache-line false sharing.
- **Limit Order Book (LOB):** O(1) flat-array reconstruction for sub-microsecond updates.
- **Ghost Exchange:** A synthetic microstructure simulator that models Almgren-Chriss market impact, queue toxicity, and adverse selection.
- **WebSocket Ingest:** Direct `wss://` ingest from Binance via `ixwebsocket`, parsing JSON and pushing to the SPSC queue in nanoseconds.

### 2. The Brain: Python Research Brain (`python/quantcore/`)
The statistical and strategic brain, leveraging vectorized math and ML.
- **Polars & DuckDB:** Blazing fast vectorized backtesting and SQL-based ledger management.
- **StatArb Crucible:** Engle-Granger cointegration and Ornstein-Uhlenbeck half-life calculations for pairs trading.
- **HRP Portfolio Optimization:** Hierarchical Risk Parity using SciPy graph theory to cluster correlated assets and bypass Markowitz matrix inversion instability.
- **Risk Gauntlet:** An automated CI/CD pipeline for strategies. Strategies must pass the Deflated Sharpe Ratio (DSR) test and a Time Machine stress test (e.g., 2022 Crypto Winter) before deployment.

### 3. The Interface: FastAPI & WebSockets (`web/`)
The trading desk interface.
- **FastAPI & Uvicorn:** Async HTTP routing.
- **WebSockets:** Direct telemetry streaming from the C++ engine to the browser for the Bookmap Heatmap.
- **Jinja2 & Tailwind:** Dark-mode, institutional-grade dashboard.

---

## 🔗 The Concurrency & IPC Model

Bridging C++ and Python without bottlenecking is the hardest part of quant stack development. QuantCore solves this via:

1. **Shared Memory IPC (`mmap`):** The Python `quant_daemon.py` and the C++ `nexus_core` share a `HiveMindState` C-struct via memory mapping. Python writes target portfolio weights; C++ reads them and executes, writing back slippage and PnL atomically.
2. **DuckDB Concurrency:** DuckDB is used for the Paper Broker ledger. To prevent "database locked" errors between the FastAPI web server and the execution daemon, the CIO War Room reads directly from the Paper Broker's in-memory connection handle rather than opening a second file lock.
3. **Asyncio Thread Offloading:** Blocking operations (like `yfinance` network calls or heavy Polars matrix math) are offloaded to background threads via `asyncio.to_thread()` to prevent freezing the FastAPI event loop.

---

## 🛡️ The Risk & Validation Pipeline

A backtest is a lie until proven otherwise. QuantCore enforces institutional realism via:
- **The Time Machine:** Vectorized Monte Carlo simulations that inject historical fat-tail crashes (e.g., LUNA/FTX contagion, 2020 Pandemic Flash Crash) to test strategy survivability.
- **Deflated Sharpe Ratio (DSR):** Penalizes the Sharpe Ratio based on the number of trials run, protecting against backtest overfitting (data snooping).
- **Almgren-Chriss Slippage:** The Ghost Exchange simulates temporary and permanent market impact. A strategy that is profitable before slippage but unprofitable after is rejected by the Risk Gauntlet.

---

## 🚀 V1.0 Deployment

QuantCore is designed to be deployed as a "Firm-in-a-Box".
- **Native WSL:** Run `./setup.sh` to compile the C++ engines and seed the database.
- **Docker:** Run `docker-compose up --build` to spin up the entire multi-stage build environment and web server in an isolated container.

---

*Built with caffeine, market microstructure theory, and AI-assisted vibe-coding.*
