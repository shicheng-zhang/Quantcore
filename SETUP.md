# ⚡ QuantCore V1.0 Setup Guide

QuantCore is a local, institutional-grade quantitative trading research and execution platform. It combines a C++20 lock-free HFT engine, a Python statistical research brain, and a FastAPI web dashboard.

## Prerequisites
- **OS:** Windows Subsystem for Linux (WSL2) running Ubuntu 22.04/24.04, or native Ubuntu/Debian.
- **Python:** Python 3.10+ installed natively (System Python).
- **Hardware:** Multi-core CPU and at least 8GB RAM.

## 🚀 One-Click Installation

QuantCore does not use virtual environments. It relies on native system Python and compiled C++ binaries. 

To build the entire stack, compile the C++ engines, and seed the database with a starter universe, simply run:

```bash
./setup.sh

## 🛠️ Troubleshooting

**C++ Compilation Errors:**
If `make` fails with missing headers, ensure you have the build tools installed:
`sudo apt install build-essential cmake libssl-dev zlib1g-dev`

**DuckDB Lock Errors:**
If you see `Can't open a connection to same database file`, it means another process (like the CIO War Room) is holding the lock. The system is designed to share the `paper_broker` connection, but if it hangs, simply restart the Uvicorn server.

**yfinance Timeouts:**
Yahoo Finance occasionally rate-limits requests. If a backtest or data fetch fails, wait 60 seconds and try again. The system caches Parquet files locally in `data/raw/equities/` to minimize network calls.

## 📊 Performance Expectations
- **First Run:** Downloading the starter universe (SPY, QQQ, BTC, etc.) will take 1-2 minutes depending on your internet connection.
- **Backtests:** Cross-sectional backtests on 5 assets over 2 years should complete in < 2 seconds.
- **C++ Compilation:** Initial compilation of the Nexus engine and pybind11 extensions will take 2-3 minutes. Subsequent builds are incremental and take seconds.

## 🚀 Quickstart
To prove the entire pipeline works headless (Data -> Backtest -> Risk Gauntlet), run:
`python3 quickstart.py`
