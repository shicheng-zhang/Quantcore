# QuantCore 1.0

QuantCore is an open-source quantitative research and simulation platform. It is released under the MIT License. Contributions are welcome, and the project is maintained as a community-driven portfolio piece and educational tool. **No real capital is ever at risk.**

## Overview
QuantCore is a modular quantitative research, simulation, paper trading, and execution platform combining a C++20 computation engine with Python services and a FastAPI backend.

### Goals
- Reproducible quantitative research
- Reliable backtesting
- Paper trading
- Modular architecture
- Operational transparency

## Features
- Historical data ingestion
- Technical indicators
- Portfolio analytics
- Risk management
- Paper broker
- Replay engine
- Dashboard
- REST API

## Project Status
Version 1.0 represents the first stable public release. Some advanced modules remain experimental and are clearly marked as such.

## Documentation
See the accompanying markdown files for architecture, configuration, development, and troubleshooting.


## What's Real vs. Simulated

Transparency is a core design principle. Here is exactly what is computed from real-world data versus what is synthetically generated for educational and architectural demonstration purposes:

| Component | Status |
|---|---|
| **Backtester, DSR, HRP, Black-Scholes** | Real math, real historical data (via yfinance/Stooq fallback) |
| **Satellite RSS Feed** | Real financial RSS (CNBC, MarketWatch) + VADER NLP sentiment |
| **Paper Broker Fills** | Simulated against mock prices + Almgren-Chriss slippage model |
| **Nexus LOB & Bookmap** | Simulated microstructure (synthetic Poisson order flow) |
| **Macro Desk & Time Machine** | Synthetic regimes and Monte Carlo stress tests |
| **RL Execution Policy** | Hand-tuned heuristic surrogate (PPO distillation TODO) |
| **Audit Ledger** | Polynomial hash chain (Order-verified, NOT cryptographically tamper-proof) |
