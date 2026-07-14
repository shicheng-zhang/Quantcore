# 🏛️ QuantCore: Architecting a Quantitative Hedge Fund via AI-Assisted Engineering

> **An experiment in AI-assisted software engineering.**
> This repository was architected by a human CTO and implemented via iterative AI pair-programming ("vibe-coding"). It demonstrates how a single developer can leverage LLMs to build a multi-lingual, institutional-grade quantitative trading simulation from scratch.

---

## 🏗️ System Architecture

QuantCore is divided into three distinct execution domains, communicating via shared memory and high-speed IPC.

### 1. The Muscle: C++20 Nexus Engine (`nexus/`)
The low-latency execution and market microstructure engine. It operates entirely outside the Python GIL.
*   **Lock-Free SPSC Queues:** Single-Producer/Single-Consumer ring buffers with 64-byte `alignas` padding to prevent CPU cache-line false sharing.
*   **Zero-Allocation Hot Paths:** Pre-allocated memory pools for Limit Order Book (LOB) updates and event routing.
*   **Ghost Exchange:** A synthetic microstructure simulator that models Almgren-Chriss market impact, queue toxicity, and adverse selection.
*   **WebSocket Ingest:** Direct `wss://` ingest via `ixwebsocket` for sub-millisecond event routing.

### 2. The Brain: Python Research Brain (`python/quantcore/`)
The statistical, strategic, and risk-management brain.
*   **Polars & DuckDB:** Blazing fast vectorized backtesting and an ACID-compliant paper trading ledger.
*   **StatArb Crucible:** Engle-Granger cointegration and Ornstein-Uhlenbeck half-life calculations for pairs trading.
*   **HRP Portfolio Optimization:** Hierarchical Risk Parity using SciPy graph theory to cluster correlated assets and bypass Markowitz matrix inversion instability.
*   **The Risk Gauntlet:** An automated validation pipeline that rejects strategies failing the Deflated Sharpe Ratio (DSR) or Time Machine stress tests.

### 3. The Interface: FastAPI & WebSockets (`web/`)
The institutional trading desk interface.
*   **Real-Time Telemetry:** WebSocket broadcasting of C++ engine telemetry directly to the browser.
*   **Tailwind CSS Dashboards:** Dark-mode, high-density data visualization.
*   **Plotly Visualizations:** Interactive equity curves, 3D Volatility Surfaces, and P&L Attribution Waterfalls.

---

## 🔄 The Concurrency & IPC Model

Bridging C++ and Python without bottlenecking is the hardest part of quant stack development. QuantCore solves this via:

1.  **Shared Memory IPC (`mmap`):** The Python `quant_daemon` and the C++ `nexus_core` share a `HiveMindState` C-struct via memory mapping. Python writes target portfolio weights; C++ reads them and executes, writing back slippage and PnL atomically.
2.  **DuckDB Concurrency:** Handled via in-memory connections and strict read/write separation to prevent database locks during high-frequency paper trading.
3.  **Asyncio Thread Offloading:** Blocking I/O operations (like `yfinance` network calls) are offloaded to background threads via `asyncio.to_thread()` to prevent freezing the FastAPI event loop.

---

## 🛡️ The Risk & Validation Pipeline

A backtest is a lie until proven otherwise. QuantCore enforces institutional realism via:

*   **The Risk Gauntlet:** Before a strategy is deployed, it must pass the Deflated Sharpe Ratio (DSR) test to prove it isn't overfit, and survive a "Time Machine" stress test (e.g., 2022 Crypto Winter).
*   **Satellite NLP Vetoes:** Synthetic NLP sentiment analysis acts as a macro veto, blocking the Autopilot from taking long positions during hostile news regimes.
*   **Almgren-Chriss Slippage:** The Ghost Exchange simulates temporary and permanent market impact. A strategy that is profitable before slippage but unprofitable after is rejected by the Gauntlet.

---

## 🛠️ Tech Stack

*   **Core:** C++20, CMake, pybind11, spdlog
*   **Research:** Python 3.12+, Polars, DuckDB, NumPy, SciPy, scikit-learn, LightGBM
*   **Web:** FastAPI, Uvicorn, Jinja2, Tailwind CSS, Plotly.js
*   **IPC:** POSIX Shared Memory (`mmap`), WebSockets (`ixwebsocket`)

---

## 🚀 Future Roadmap

*   **Live Broker Integration:** CCXT / Alpaca API wrappers for live paper/execution routing.
*   **Vector DB RAG:** Ingesting SEC filings and earnings calls into a Vector DB for real-time NLP vetoes.
*   **Cloud Deployment:** Multi-stage Docker builds for one-click cloud deployment.

---

*Built with caffeine, market microstructure theory, and AI-assisted vibe-coding.*
