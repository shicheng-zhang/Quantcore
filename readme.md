# ⚡ QuantCore: The Local Institutional Trading Stack

**QuantCore** is a zero-daemon, locally hosted, institutional-grade quantitative trading and research environment. Built to run on a high-end prosumer workstation (WSL2 Ubuntu, AMD Ryzen 9950X, RTX 5070 Ti), it bridges the gap between retail charting platforms and Tier-1 hedge fund infrastructure.

It features a pure C++20 lock-free High-Frequency Trading (HFT) engine, a vectorized Polars research lab, an interactive FastAPI web dashboard, and rigorous statistical validation frameworks.

---

## Disclaimer: This project was entirely vibe coded with Qwen 3.7 Plus/Max. I only fed it prompts and ideas and my vision for what I wanted the software to become.


## 🏛️ The 4 Pillars of QuantCore

### 1. The Nexus HFT Engine (C++20)
The crown jewel of the stack. A pure C++20 execution engine designed for sub-microsecond latency.
* **Lock-Free Architecture:** Uses Single-Producer Single-Consumer (SPSC) ring buffers with `std::atomic` to pass events between the network ingestor and the trading thread without mutexes.
* **Zero-Allocation:** Pre-allocated memory pools and fixed-size structs ensure the hot path never triggers a page fault or garbage collection pause.
* **Cache-Line Padding:** Uses `alignas(64)` to prevent CPU false-sharing between cores.
* **Live Ingestion:** Connects directly to live WebSocket APIs, parses JSON on the fly, and updates an O(1) Limit Order Book (LOB) in real-time.

### 2. The Alpha & Research Lab (Python/Polars)
Where signals are hunted and validated using institutional mathematics.
* **Lead-Lag Scanner:** Uses SciPy's Cross-Correlation Function (CCF) to scan asset universes and map "Information Flow" (e.g., identifying if Asset A predicts Asset B with a measurable time lag).
* **The Backtest Crucible:** A vectorized cross-sectional momentum backtester that ranks assets, goes long the top quartile, shorts the bottom, and strictly deducts transaction costs (slippage) based on daily portfolio turnover.
* **Deflated Sharpe Ratio (DSR):** The "BS Detector." Mathematically penalizes a strategy's Sharpe Ratio based on the number of trials run to prove the Alpha isn't just statistical overfitting.
* **Hierarchical Risk Parity (HRP):** Uses graph theory and dendrogram clustering to allocate portfolio weights, ensuring risk is balanced across uncorrelated market clusters.

### 3. The Execution Simulator
* **VWAP / TWAP Algos:** Simulates slicing large parent orders into hundreds of child orders based on historical intraday volume profiles to hide market footprint from HFT predators.
* **Slippage Modeling:** Calculates the exact basis points (bps) of market impact suffered when executing a retail Market Order vs. an institutional VWAP algo.

### 4. The Interactive Dashboard (FastAPI + Plotly.js)
A sleek, dark-mode web interface hosted locally on `127.0.0.1:8765`.
* **Live Telemetry:** Watch the C++ Nexus engine process millions of events and report nanosecond p99 latency metrics live.
* **Dynamic Universe:** Add or remove tickers on the fly; the backend automatically fetches Parquet data and reloads the DuckDB data lake.
* **Intraday & Daily Analysis:** Seamlessly toggle between 1-minute tick data and 5-year macro trends with professional, percentile-scaled charting.

---

## 🛠️ Tech Stack & Hardware

**Hardware Target:**
* **CPU:** AMD Ryzen 9 9950X (16-core, AVX-512 native support)
* **GPU:** NVIDIA RTX 5070 Ti (16GB VRAM for local LLM sentiment analysis)
* **RAM:** 96GB DDR5 (For massive in-memory DuckDB/Polars operations)
* **OS:** WSL2 Ubuntu 24.04 (Noble Numbat)

**Software Stack:**
* **Core Engine:** C++20, GCC 13, CMake, Ninja
* **Data Lake:** DuckDB (Embedded OLAP), Parquet (Zstd compressed)
* **Research:** Python 3.12, Polars, NumPy, SciPy, LightGBM
* **Backend:** FastAPI, Uvicorn, Pydantic
* **Frontend:** Jinja2, Tailwind CSS, Plotly.js
* **Networking:** IXWebSocket, OpenSSL, nlohmann/json

---

## 🚀 Installation & Setup

QuantCore is designed to be built via a series of sequential, idempotent bash scripts. No Docker, no Kubernetes, no background daemons.

### 1. Base Installation
```bash
chmod +x setup_quantcore.sh
./setup_quantcore.sh
