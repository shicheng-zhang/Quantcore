#!/bin/bash
echo "=========================================="
echo " ⚡ QuantCore V1.0 Initialization"
echo "=========================================="
echo "[1/5] Installing system dependencies..."
sudo apt update
sudo apt install -y build-essential cmake python3-dev libssl-dev zlib1g-dev
echo "[2/5] Installing Python quantitative stack..."
pip install -U -r requirements.txt --break-system-packages
pip install pybind11 rich textual psutil --break-system-packages
echo "[3/5] Compiling C++ Analytics Engine..."
mkdir -p build && cd build
cmake .. && make -j$(nproc)
cp quantcore_cpp*.so ../python/quantcore/quantcore_cpp.so 2>/dev/null || true
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
echo " Run: python3 -m uvicorn web.backend.main:app --host 127.0.0.1 --port 8765 --reload"
