# ⚡ QuantCore V1.0.0-RC4
### A Local Quantitative Trading Research & Execution Platform *(Work in Progress)*

> **Project Status:** 🚧 Active Development
>
> QuantCore is an experimental quantitative trading platform intended to combine high-performance C++ components with a Python research environment and a lightweight web dashboard.
>
> The long-term goal is to build a platform capable of competing with professional quantitative research workflows. **It is not there yet.** Many components are functional, others are experimental, and the project is evolving rapidly.

---

# About This Project

QuantCore started as a personal attempt to explore what a modern quantitative trading stack could look like if built from scratch for a powerful local workstation.

The project combines several areas that normally exist as separate systems:

- High-performance C++ data processing
- Python-based quantitative research
- Machine learning experimentation
- Portfolio construction
- Strategy development
- Market data analysis
- Web-based visualization

The eventual vision is to create a platform capable of handling research, simulation, analytics, and eventually live trading from a single codebase.

---

# AI Disclosure

This repository was developed almost entirely using AI-assisted ("vibe coding") workflows.

I did **not** manually write the majority of the source code.

Instead, I designed the project, decided the architecture, chose the technologies, specified the desired functionality, and iteratively guided AI (primarily Qwen) to implement those ideas.

As a result, this repository should be viewed as an experiment in AI-assisted software engineering as much as it is a quantitative finance project.

---

# Current State

This project is **not** intended to represent production-ready trading software.

Some components are well-developed.

Others are prototypes.

Some features are placeholders for future work.

The current focus is on building a coherent architecture rather than optimizing every implementation.

> **📖 [Read the Architecture & Vibe-Coding Manifesto](ARCHITECTURE.md)** to understand how this stack was built.

---

# Repository Layout

```text
QuantCore/
├── nexus/
├── cpp/
├── python/
├── web/
├── config/
├── data/
└── CMakeLists.txt
```

---

# Major Components

## Nexus

An experimental C++ engine intended for low-latency market data ingestion and processing.

Goals include lock-free queues, order book processing, WebSocket feeds, and latency measurements.

## Native C++ Extensions

Performance-sensitive components exposed to Python using pybind11 for data loading, feature generation, event dispatch, and risk calculations.

## Python Research Environment

Contains research tools for factor research, backtesting, portfolio construction, execution algorithms, statistical arbitrage, and machine learning.

## Dashboard

A FastAPI application providing visualizations for research, analytics, execution, telemetry, and strategy development.

---

# Technology Stack

- Python 3.12+
- C++20
- FastAPI
- DuckDB
- Polars
- Apache Arrow
- NumPy
- SciPy
- PyTorch
- LightGBM
- scikit-learn
- Plotly
- pybind11
- spdlog

---

# Goals

The long-term objective is to create a quantitative trading platform that can eventually approach the capabilities of professional Wall Street research infrastructure.

That remains a long-term goal rather than the current reality.

Current development focuses on:

- Robust architecture
- Fast local analytics
- Historical research
- Portfolio construction
- Machine learning
- Efficient data pipelines
- Low-latency market data processing

---

# Disclaimer

This software is intended for research and educational purposes only.

Nothing in this repository constitutes financial advice.

Use at your own risk.

---

# License

GPLv3

## ⚠️ Known Limitations (V1.0.0-RC4)
QuantCore is currently in Beta. While the architecture is sound and the core pipeline is tested, the following limitations apply:
- **Broker Integration:** Alpaca integration is credential-only and tested against paper environments. Live trading requires additional safety guards.
- **Data Sources:** `yfinance` is used for historical data. Rate limits may apply.
- **Stub Modules:** `alt_data/` (NLP/Whale flow), `rl/` (RL execution), and `nlp/` modules are currently structural stubs that fail gracefully.
- **Live Feeds:** The C++ Nexus engine uses synthetic microstructure data when disconnected from live Binance WebSocket feeds.

## Screenshots
<img width="3413" height="1243" alt="Screenshot 2026-06-27 130117" src="https://github.com/user-attachments/assets/27122353-1743-4b9c-8af8-4823be7627d1" />
<img width="3418" height="1245" alt="Screenshot 2026-06-27 130137" src="https://github.com/user-attachments/assets/abb5e1cc-69fe-43be-ad35-1211d74ea25d" />
<img width="3415" height="1246" alt="Screenshot 2026-06-27 130215" src="https://github.com/user-attachments/assets/1cb484bb-e982-4cfb-94d7-3436de12986a" />
<img width="3438" height="1252" alt="Screenshot 2026-06-27 130229" src="https://github.com/user-attachments/assets/1d8d240d-6e96-4eb9-92db-4a6bf7cca5b3" />
<img width="3438" height="1247" alt="Screenshot 2026-06-27 130255" src="https://github.com/user-attachments/assets/9de558f8-d151-478c-bec5-e28d0a63ddf3" />
<img width="3420" height="1252" alt="Screenshot 2026-06-27 130326" src="https://github.com/user-attachments/assets/020e03d3-83b0-4daa-9247-92ca563de588" />
<img width="3432" height="1252" alt="Screenshot 2026-06-27 130404" src="https://github.com/user-attachments/assets/f1913b05-035e-47eb-94f9-d1fe7aeea211" />
<img width="3413" height="1245" alt="Screenshot 2026-06-27 130512" src="https://github.com/user-attachments/assets/7040f66a-92f8-4ca6-9318-a0e0d6092771" />

