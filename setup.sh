#!/bin/bash
echo "=========================================="
echo " ⚡ QuantCore V1.0 Initialization"
echo "=========================================="
echo "[1/5] Installing system dependencies..."
sudo apt update
sudo apt install -y build-essential cmake python3-dev libssl-dev zlib1g-dev python3-venv

echo "[2/5] Setting up Python Virtual Environment..."
python3 -m venv .venv
source .venv/bin/activate
pip install -U -r requirements.txt
pip install pybind11

echo "[3/5] Compiling C++ Analytics Engine..."
mkdir -p build && cd build
cmake .. && make -j$(nproc)
cp quantcore_cpp*.so ../python/quantcore/quantcore_cpp.so 2>/dev/null || true
# FIX: Copy libduckdb.so next to the python extension so $ORIGIN RPATH finds it
cp _deps/duckdb-build/src/libduckdb.so ../python/quantcore/ 2>/dev/null || true
cd ..

echo "[4/5] Compiling Nexus HFT Engine..."
cd nexus && mkdir -p build && cd build
cmake .. && make -j$(nproc)
cd ../..

echo "[5/5] Seeding Starter Universe..."
python3 python/scripts/seed_universe.py

echo ""
echo "=========================================="
echo " ✅ SETUP COMPLETE"
echo "=========================================="
echo " Activate venv: source .venv/bin/activate"
echo " Run TUI: python3 infra_tui.py"
