<div align="center">

# ⚡ QuantCore
### The Institutional-Grade, Local-First Algorithmic Trading Stack

**[The Manifesto](#-the-vibe-coded-manifesto) • [Architecture](#-system-architecture) • [The Nexus HFT Engine](#-the-nexus-hft-engine-c20) • [Research & Alpha](#-the-research--alpha-lab) • [War Stories](#-engineering-war-stories) • [Setup](#-installation--modular-build-system)**

![C++20](https://img.shields.io/badge/C++20-Lock--Free-blue?logo=cplusplus)
![Python 3.12](https://img.shields.io/badge/Python-3.12-yellow?logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-Async-green?logo=fastapi)
![DuckDB](https://img.shields.io/badge/DuckDB-Analytical-orange?logo=duckdb)
![Polars](https://img.shields.io/badge/Polars-Dataframe-purple?logo=polars)
![WSL2](https://img.shields.io/badge/WSL2-Bare--Metal-black?logo=linux)

*Built for the AMD Ryzen 9950X & RTX 5070 Ti. Designed to rival Wall Street.*

</div>

---

## 🤖 The "Vibe Coded" Manifesto

**This project is 100% Vibe Coded.**

QuantCore was not built by writing boilerplate in an IDE for six months. It was architected, compiled, debugged, and deployed entirely through continuous, high-velocity AI pair-programming in a pure flow state.

From the AVX-512 SIMD intrinsics in the C++ feature engine to the Tailwind CSS frontend, the Polars dataframe logic, and the lock-free SPSC ring buffers—every single line of code was generated, patched, and hot-reloaded via conversational prompts. There is no legacy debt. There are no unused microservices.

It stands as a proof-of-concept that a single developer, leveraging LLMs as a real-time systems architect, can build a multi-tier, multi-language, institutional-grade quantitative trading platform in a single weekend. We didn't just build a trading bot; we built a **Research Lab**, an **Execution Simulator**, and a **Bare-Metal HFT Engine**, completely locally, without a single Docker container.

---

## 📑 Table of Contents
1. [The Philosophy: Retail vs. Institutional](#-the-philosophy-retail-vs-institutional)
2. [Target Hardware & OS Tuning](#-target-hardware--os-tuning)
3. [System Architecture](#-system-architecture)
4. [The Nexus HFT Engine (C++20)](#-the-nexus-hft-engine-c20)
5. [The Research & Alpha Lab (Python)](#-the-research--alpha-lab-python)
6. [Execution & Microstructure](#-execution--microstructure)
7. [The Frontend & UX (PRO vs LEARN)](#-the-frontend--ux-pro-vs-learn)
8. [Engineering War Stories](#-engineering-war-stories)
9. [Installation & Modular Build System](#-installation--modular-build-system)
10. [The Roadmap to Bare Metal](#-the-roadmap-to-bare-metal)

---

## 🏛️ The Philosophy: Retail vs. Institutional

To challenge the NYSE, one must understand the fundamental difference between Retail and Institutional trading:
*   **Retail** asks: *"What will the price do?"* and clicks "Buy Market". They treat the market as a time-series forecasting problem.
*   **Wall Street** asks: *"How do I acquire 50,000 shares without the market noticing, and how do I hedge out the sector risk?"* They treat the market as a cross-sectional classification and optimization problem.

QuantCore is built entirely around the Institutional paradigm. We do not just look at price; we look at **Information Flow**, **Order Book Imbalance**, **Factor Neutrality**, and **Transaction Cost Analysis (TCA)**.

---

## 💻 Target Hardware & OS Tuning

This stack is explicitly optimized for modern prosumer "super-workstations". It is designed to run locally, utilizing hardware that rivals mid-tier hedge fund research clusters.

*   **CPU:** AMD Ryzen 9 9950X (16 Cores / 32 Threads). The C++ engine uses `-march=native` to emit AVX-512 ZMM instructions. Python uses all 32 threads for Polars/DuckDB parallelization.
*   **GPU:** NVIDIA RTX 5070 Ti (16GB VRAM). Used for local quantized Llama-3 (via `llama.cpp`) sentiment analysis and PyTorch time-series transformers.
*   **RAM:** 96GB DDR5. Allows massive in-memory Parquet/DuckDB joins and cross-sectional matrix calculations without swapping.
*   **OS:** WSL2 (Ubuntu 24.04).
    *   *Tuning:* `.wslconfig` is configured with `autoMemoryReclaim=dropcache` and `localhostForwarding=true`.
    *   *Storage:* Dedicated NVMe passthrough via `wsl --mount` to eliminate VHDX virtual disk I/O bottlenecks.

---

## 🏛️ System Architecture

QuantCore is divided into two distinct paradigms: **The Research Lab** (Python/Polars/DuckDB) for discovering Alpha, and **The Production Engine** (C++20/Nexus) for executing it with zero-allocation, lock-free latency.

```text
┌────────────────────────────────────────────────────────────────────┐
│                   FRONTEND (Tailwind CSS + Plotly.js)              │
│  [Dashboard] [Trends] [Predictions] [Execution] [Research]         │
│  [Alpha Lab] [Backtest] [Nexus HFT]             [ 🔄 PRO | LEARN ] │
└──────────────────────────────┬─────────────────────────────────────┘
                               │ FastAPI (Async/Uvicorn)
┌──────────────────────────────┴─────────────────────────────────────┐
│                     PYTHON ORCHESTRATION LAYER                     │
│  yfinance Live Fallback │ Polars Alpha Hunter │ Vector Backtester  │
└──────────────────────────────┬─────────────────────────────────────┘
                               │ pybind11 / Shared Memory / JSON
┌──────────────────────────────┴─────────────────────────────────────┐
│                 C++20 CORE (libquantcore.so)                       │
│  AVX-512 Feature Engine │ DuckDB Embed │ Risk Gateway │ Event Bus  │
└──────────────────────────────┬─────────────────────────────────────┘
                               │ Lock-Free SPSC Ring Buffer
┌──────────────────────────────┴─────────────────────────────────────┐
│                   NEXUS HFT ENGINE (nexus_core)                    │
│  TLS WebSocket Ingestor │ O(1) Limit Order Book │ Nano Telemetry   │
└────────────────────────────────────────────────────────────────────┘
