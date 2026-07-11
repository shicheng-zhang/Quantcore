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
