# 🏛️ QuantCore: Architecting a Hedge Fund via AI-Assisted Engineering

> **An experiment in "Vibe-Coding".**
> This repository was architected by a human CTO and implemented via iterative AI pair-programming. It demonstrates how a single developer can leverage LLMs to build a multi-lingual, institutional-grade quantitative trading simulation from scratch.

---

## 🧠 The Philosophy: Vibe-Coding
"Vibe-coding" is the practice of acting as the Systems Architect while delegating syntactical implementation to AI.
- **The Human Role:** Define the physics (Almgren-Chriss slippage, Ornstein-Uhlenbeck mean reversion), enforce concurrency models (lock-free SPSC queues), and demand institutional realism (Risk Gauntlets, Deflated Sharpe Ratios).
- **The AI Role:** Generate the C++20 templates, write the Pybind11 bindings, configure CMake toolchains, and wire FastAPI WebSockets.

This project proves that a single developer, armed with an AI and a deep understanding of market microstructure, can build a stack that rivals the architectural fidelity of mid-tier prop shops.

---

## 🏗️ System Architecture

QuantCore is divided into three distinct execution domains, communicating via shared memory and high-speed IPC.

### 1. The Muscle: C++20 Nexus Engine (`nexus/`)
The low-latency execution engine. It operates entirely outside the Python GIL.
- **Lock-Free SPSC Queues:** Single-Producer/Single-Consumer ring buffers with 64-byte `alignas` padding to prevent CPU cache-line false sharing.
- **Zero-Allocation Hot Paths:** Pre-allocated memory pools for Limit Order Book (LOB) updates.
- **Ghost Exchange:** A synthetic microstructure simulator that models Almgren-Chriss market impact, queue toxicity, and adverse selection.
- **WebSocket Ingest:** Direct `wss://` ingest from Binance via `ixwebsocket`.

### 2. The Brain: Python Research Brain (`python/quantcore/`)
The statistical and strategic brain, leveraging vectorized math.
- **Polars & DuckDB:** Blazing fast vectorized backtesting and ACID-compliant paper trading ledgers.
- **StatArb Crucible:** Engle-Granger cointegration and Ornstein-Uhlenbeck half-life calculations.
- **HRP Portfolio Optimization:** Hierarchical Risk Parity using SciPy graph theory to cluster correlated assets.
- **The Risk Gauntlet:** An automated CI/CD pipeline for strategies. Strategies must pass the Deflated Sharpe Ratio (DSR) test and a Time Machine stress test (e.g., 2022 Crypto Winter) before deployment.

### 3. The Interface: FastAPI & WebSockets (`web/`)
The institutional trading desk interface.
- **Day Trading Desk:** Real-time VWAP, Opening Range Breakouts (ORB), and RSI signals.
- **Bookmap Heatmap:** Canvas-rendered Limit Order Book depth visualization.
- **Mini-Wiki:** An interactive educational layer that translates "Wall Street Reality" into "Day Trader" terms.

---

## 🔗 The Concurrency Model
Bridging C++ and Python without bottlenecking is the hardest part of quant stack development. QuantCore solves this via:
1. **Shared Memory IPC (`mmap`):** The Python `quant_daemon` and C++ `nexus_core` share a `HiveMindState` C-struct. Python writes target weights; C++ reads them and executes, writing back slippage atomically.
2. **DuckDB Concurrency:** Handled via in-memory connections to prevent database locks during high-frequency paper trading.

---

## 🚀 V1.0 Deployment
QuantCore is designed to be deployed as a "Firm-in-a-Box".
- **Native WSL:** Run `./setup.sh` to compile engines and seed the database.
- **Docker:** Run `docker-compose up` to spin up the entire stack in an isolated container.

---

*Built with caffeine, market microstructure theory, and AI-assisted vibe-coding.*
