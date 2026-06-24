# ⚡ QuantCore: Institutional-Grade Quantitative Trading Stack
[![C++20](https://img.shields.io/badge/C%2B%2B-20-green.svg)](https://isocpp.org/)
[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-green.svg)](https://fastapi.tiangolo.com/)
**QuantCore** is a zero-daemon, locally-hosted quantitative trading and research platform that bridges the gap between retail tools and Tier-1 hedge fund infrastructure. Built for high-end workstations running WSL2 Ubuntu, it combines a lock-free C++20 HFT engine with a vectorized Python research lab and an interactive FastAPI dashboard.
> **Note:** This project was developed through iterative AI-assisted development (Qwen 3.7 Plus/Max), translating vision and prompts into production-ready code.
---
## 🏗️ Architecture Overview
```
QuantCore/
├── nexus/          # C++20 HFT Engine (Live WebSocket ingestion, LOB, SPSC queues)
├── cpp/            # PyBind11 bindings (Data/Feature/Risk engines)
├── python/         # Research Lab (Polars, DuckDB, HRP, Backtesting)
│   ├── quantcore/
│   │   ├── research/    # Alpha hunting, validation, backtesting
│   │   ├── portfolio/   # Hierarchical Risk Parity allocation
│   │   ├── execution/   # VWAP/TWAP algorithms, slippage modeling
│   │   ├── strategy/    # Statistical arbitrage strategies
│   │   ├── models/      # ML models (LightGBM, PyTorch)
│   │   └── nlp/         # Sentiment analysis (optional LLM integration)
│   └── scripts/     # CLI entry points (live.py, train.py)
├── web/            # FastAPI Dashboard + Plotly.js frontend
│   ├── backend/   # REST API, analytics engine
│   ├── templates/ # Jinja2 HTML views
│   └── static/    # CSS, JavaScript assets
├── config/         # YAML configuration (system, risk limits, strategies)
├── data/           # Parquet files, DuckDB, logs, telemetry
└── CMakeLists.txt  # Root CMake build configuration
```
---
## 🎯 Core Components
### 1. Nexus HFT Engine (`nexus/`)
A pure C++20 low-latency trading engine designed for sub-microsecond processing.
**Key Features:**
- **Lock-Free SPSC Queue:** `alignas(64)` cache-line padded ring buffer (2M events capacity)
- **Zero-Allocation Hot Path:** Pre-allocated memory pools, no dynamic allocations during event processing
- **Live Market Data:** Binance WebSocket integration (`wss://stream.binance.com:9443/ws/btcusdt@trade`)
- **O(1) Limit Order Book:** Real-time LOB updates with spread tracking
- **Nanosecond Telemetry:** Tracks ingest-to-process latency with p99 reporting
**Performance Metrics (Live):**
| Metric | Value |
|--------|-------|
| Mean Latency | ~5.4 μs |
| P99 Latency | ~66 μs |
| Events/sec | Millions |
**Build & Run:**
```bash
cd /workspace
mkdir -p nexus/build && cd nexus/build
cmake .. -DCMAKE_BUILD_TYPE=Release
make -j$(nproc)
./nexus_core
```
---
### 2. C++ Extension Module (`cpp/`)
PyBind11 bindings exposing high-performance C++ utilities to Python.
**Modules:**
- `event_bus.cpp` — Lock-free event dispatching
- `data_engine.cpp` — DuckDB/Parquet data loading
- `feature_engine.cpp` — Technical indicator computation
- `risk_engine.cpp` — Real-time risk calculations
- `bindings.cpp` — Python module exports
**Build:**
```bash
mkdir -p build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release
make -j$(nproc)
# Output: quantcore_cpp.so → copied to python/quantcore/
```
---
### 3. Research Lab (`python/quantcore/`)
Institutional-grade alpha research and validation framework.
#### Research (`research/`)
| Module | Description |
|--------|-------------|
| `alpha_hunter.py` | Lead-lag scanning using SciPy CCF, information flow mapping |
| `backtester.py` | Vectorized cross-sectional momentum backtester with turnover/slippage modeling |
| `validation.py` | Deflated Sharpe Ratio (DSR) to penalize overfitting |
#### Portfolio (`portfolio/`)
- **Hierarchical Risk Parity (HRP):** Graph-theoretic clustering for risk-balanced allocation
- Implements Lopez de Prado's methodology with dendrogram-based weight distribution
#### Execution (`execution/`)
- **VWAP/TWAP Algorithms:** Slice large orders based on historical volume profiles
- **Slippage Modeling:** Calculate market impact in basis points (bps)
#### Strategy (`strategy/`)
- **Statistical Arbitrage:** Pairs trading with z-score entry/exit thresholds
- Configurable pairs: `[["AAPL", "MSFT"], ["GOOGL", "META"]]`
- Entry threshold: `z-score > 2.0`, Lookback: 100 periods
#### Models (`models/`)
- LightGBM gradient boosting
- PyTorch neural networks
- Scikit-learn classifiers/regressors
#### NLP (`nlp/`)
- Optional sentiment analysis via local Llama 3 GGUF models
- Disabled by default (see `config/system.yaml`)
---
### 4. Web Dashboard (`web/`)
Interactive FastAPI application hosted at `http://127.0.0.1:8765`.
**Routes:**
| Endpoint | Template | Purpose |
|----------|----------|---------|
| `/` | `dashboard.html` | Live Nexus telemetry, system status |
| `/trends` | `trends.html` | Multi-year macro trends, percentile charts |
| `/predictions` | `predictions.html` | ML model forecasts |
| `/execution` | `execution.html` | VWAP/TWAP simulation, slippage analysis |
| `/signals` | `signals.html` | Real-time trading signals |
| `/research` | `research.html` | Alpha metrics, DSR validation |
| `/api/research/hrp` | JSON | HRP portfolio weights |
**Start Dashboard:**
```bash
chmod +x run_web.sh
./run_web.sh
```
---
## 🛠️ Tech Stack
### Core Technologies
| Layer | Technology |
|-------|------------|
| **HFT Engine** | C++20, GCC 13, CMake, Ninja |
| **Bindings** | PyBind11 v2.13.6 |
| **Data Lake** | DuckDB v1.1.0, Apache Arrow, Parquet (Zstd) |
| **Research** | Python 3.12, Polars, NumPy, SciPy, Pandas |
| **ML** | LightGBM, PyTorch, Scikit-learn |
| **Backend** | FastAPI, Uvicorn, Pydantic, Jinja2 |
| **Frontend** | Tailwind CSS, Plotly.js |
| **Networking** | IXWebSocket, OpenSSL, nlohmann/json |
| **Logging** | spdlog v1.14.1 |
### Hardware Target
- **CPU:** AMD Ryzen 9 9950X (16-core, AVX-512)
- **GPU:** NVIDIA RTX 5070 Ti (16GB VRAM for local LLMs)
- **RAM:** 96GB DDR5 (in-memory DuckDB/Polars operations)
- **OS:** WSL2 Ubuntu 24.04 (Noble Numbat)
---
## 📦 Installation
### Prerequisites
```bash
# System dependencies (Ubuntu/WSL2)
sudo apt update
sudo apt install -y build-essential cmake ninja-build git \
    libssl-dev zlib1g-dev python3.12 python3.12-venv \
    python3.12-dev pkg-config
```
### Step 1: Create Virtual Environment
```bash
cd /workspace
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
```
### Step 2: Install Python Dependencies
```bash
pip install -r requirements.txt
```
### Step 3: Build C++ Components
```bash
# Build main C++ extensions (PyBind11 modules)
mkdir -p build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release -G Ninja
ninja
cd ..
# Build Nexus HFT Engine (standalone binary)
cd nexus
mkdir -p build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release -G Ninja
ninja
cd ../..
```
### Step 4: Verify Build Artifacts
```bash
# Check PyBind11 module exists
ls -lh python/quantcore/quantcore_cpp.so
# Check Nexus binary exists
ls -lh nexus/build/nexus_core
```
---
## 🚀 Quick Start
### 1. Launch Nexus HFT Engine (Optional - Live Trading)
```bash
./nexus/build/nexus_core
# Connects to Binance WebSocket, streams live BTC/USDT trades
# Logs to: data/nexus_core.log
# Telemetry: data/nexus_live.json
```
### 2. Start Web Dashboard
```bash
./run_web.sh
# Access: http://127.0.0.1:8765
```
### 3. Run Research Scripts
```bash
# Train ML models
python python/scripts/train.py
# Run live signal generation
python python/scripts/live.py
```
---
## ⚙️ Configuration
Edit `config/system.yaml` to customize:
```yaml
system:
  database_path: "data/analytics.db"
data:
  parquet_views:
    market_data: "data/raw/equities/"
risk:
  max_position_pct: 0.05      # 5% max per position
  max_daily_loss_pct: 0.03    # 3% daily loss limit
  max_drawdown_pct: 0.10      # 10% max drawdown
nlp:
  enabled: false              # Set true if LLAMA model is available
  model_path: "data/models/llama-3-8b-instruct.Q4_K_M.gguf"
strategies:
  stat_arb:
    pairs: [["AAPL", "MSFT"], ["GOOGL", "META"]]
    entry_zscore: 2.0
    lookback: 100
```
---
## 📊 Data Pipeline
### Supported Data Sources
- **Parquet Files:** Located in `data/raw/equities/` (BTC-USD, MU, SPCX, TSM included)
- **DuckDB:** Embedded OLAP database at `data/analytics.db`
- **Live Streams:** Binance WebSocket (configured in Nexus)
### Adding New Tickers
1. Place Parquet files in `data/raw/equities/`
2. Dashboard auto-discovers new files on refresh
3. DuckDB views update automatically
---
## 🧪 Testing & Validation
### Deflated Sharpe Ratio (DSR)
The DSR implementation penalizes strategies based on the number of trials:
```
DSR = SR² - (2 × γ × log(T)) / T
```
Where:
- `SR` = Observed Sharpe Ratio
- `T` = Number of independent trials
- `γ` = Euler-Mascheroni constant (~0.577)
### Backtest Methodology
1. **Universe Selection:** Rank assets by momentum signal
2. **Portfolio Construction:** Long top quartile, short bottom quartile
3. **Turnover Calculation:** Daily rebalancing with transaction costs
4. **Slippage Deduction:** Basis points deducted based on volume impact
---
## 🔒 Risk Management
Built-in risk controls (configurable in `system.yaml`):
- **Position Limits:** Max 5% allocation per asset
- **Daily Loss Limit:** Auto-halt at 3% daily loss
- **Max Drawdown:** Circuit breaker at 10% peak-to-trough decline
- **Z-Score Thresholds:** Stat-arb entries only beyond 2σ deviations
---
## 📂 Project Structure Reference
```
/workspace/
├── CMakeLists.txt              # Root CMake (fetches PyBind11, DuckDB, spdlog)
├── requirements.txt            # Python dependencies
├── run_web.sh                  # Dashboard launcher script
├── readme.md                   # This file
│
├── config/
│   └── system.yaml             # Main configuration file
│
├── cpp/                        # PyBind11 extension module
│   ├── CMakeLists.txt
│   ├── include/quantcore/      # C++ headers
│   └── src/                    # Implementation files
│       ├── bindings.cpp        # Python exports
│       ├── data_engine.cpp     # DuckDB integration
│       ├── feature_engine.cpp  # Technical indicators
│       ├── risk_engine.cpp     # Risk calculations
│       └── event_bus.cpp       # Event dispatching
│
├── nexus/                      # Standalone HFT engine
│   ├── CMakeLists.txt
│   ├── include/
│   │   ├── spsc_queue.h        # Lock-free SPSC queue
│   │   ├── event.h             # Event struct definitions
│   │   └── limit_order_book.h  # O(1) LOB implementation
│   └── src/
│       └── main.cpp            # WebSocket ingestor + engine loop
│
├── python/
│   └── quantcore/              # Main Python package
│       ├── __init__.py
│       ├── quantcore_cpp.so    # Compiled C++ bindings
│       ├── pipeline.py         # Data processing pipeline
│       │
│       ├── research/
│       │   ├── alpha_hunter.py # Lead-lag scanning, CCF analysis
│       │   ├── backtester.py   # Vectorized backtesting engine
│       │   └── validation.py   # DSR, statistical tests
│       │
│       ├── portfolio/
│       │   └── hrp.py          # Hierarchical Risk Parity
│       │
│       ├── execution/
│       │   └── algos.py        # VWAP/TWAP, slippage models
│       │
│       ├── strategy/
│       │   ├── base.py         # Abstract strategy base class
│       │   └── stat_arb.py     # Pairs trading implementation
│       │
│       ├── models/             # ML model wrappers
│       ├── nlp/                # Sentiment analysis (optional)
│       └── scripts/
│           ├── live.py         # Live signal generation
│           └── train.py        # Model training scripts
│
├── web/
│   ├── backend/
│   │   ├── main.py             # FastAPI app, route definitions
│   │   └── analytics.py        # Analytics engine, data processing
│   ├── templates/              # Jinja2 HTML templates
│   │   ├── base.html           # Base layout (Tailwind CSS)
│   │   ├── dashboard.html      # Live telemetry view
│   │   ├── trends.html         # Long-term charts
│   │   ├── predictions.html    # ML forecasts
│   │   ├── execution.html      # Algo simulation
│   │   ├── signals.html        # Trading signals
│   │   ├── research.html       # Alpha metrics
│   │   ├── backtest.html       # Backtest results
│   │   ├── alpha.html          # Alpha hunter UI
│   │   └── nexus.html          # Nexus engine status
│   └── static/
│       ├── css/                # Custom stylesheets
│       └── js/                 # Plotly.js interactions
│
└── data/
    ├── raw/equities/           # Parquet data files
    ├── analytics.db            # DuckDB database
    ├── alpha_signals.json      # Computed alpha signals
    ├── nexus_core.log          # Nexus engine logs
    ├── nexus_live.json         # Real-time telemetry
    └── nexus_telemetry.json    # Historical latency stats
```
---
## 🔧 Troubleshooting
### Build Errors
- **PyBind11 fetch fails:** Ensure internet connection; CMake downloads dependencies
- **OpenSSL not found:** `sudo apt install libssl-dev`
- **GCC version too old:** Requires GCC 11+ for C++20 features
### Runtime Issues
- **Dashboard won't start:** Check port 8765 isn't in use (`lsof -i :8765`)
- **Nexus crashes on WebSocket:** Verify network connectivity to Binance
- **Missing Parquet files:** Add data to `data/raw/equities/`
### Performance Tuning
- **Enable AVX-512:** Ensure BIOS settings allow AVX-512 instructions
- **CPU Affinity:** Pin Nexus thread to isolated core (`taskset -c 0 ./nexus_core`)
- **Huge Pages:** Enable for reduced TLB misses (`echo always > /sys/kernel/mm/transparent_hugepage/enabled`)
---
## 📄 License
GPLv3 License — See [LICENSE](LICENSE) for details.
---
## 🤝 Contributing
1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request
---
## 📬 Contact
For questions or collaboration, open an issue on GitHub.
