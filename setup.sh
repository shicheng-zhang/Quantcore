#!/bin/bash
set -euo pipefail
echo "=========================================="
echo " ⚡ QuantCore V1.2 Initialization"
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
rm -rf build
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j"$(nproc)"
cp build/quantcore_cpp*.so python/quantcore/
# libduckdb.so must sit next to the extension so $ORIGIN RPATH resolves it.
cp build/_deps/duckdb-build/src/libduckdb.so python/quantcore/

echo "[4/5] Compiling Nexus HFT Engine..."
cmake -S nexus -B nexus/build -DCMAKE_BUILD_TYPE=Release
cmake --build nexus/build -j"$(nproc)"

echo "[5/5] Seeding Starter Universe..."
python3 python/scripts/seed_universe.py

echo ""
echo "=========================================="
echo " 🔎 Verifying build (fail loudly, not silently)"
echo "=========================================="
missing=0
[ -f python/quantcore/quantcore_cpp.so ] || { echo "MISSING: python/quantcore/quantcore_cpp.so — C++ analytics build failed"; missing=1; }
[ -f python/quantcore/libduckdb.so ]   || { echo "MISSING: python/quantcore/libduckdb.so — DuckDB was not linked statically"; missing=1; }
[ -x nexus/build/nexus_core ]          || { echo "MISSING: nexus/build/nexus_core — Nexus HFT engine build failed"; missing=1; }
[ "$missing" -eq 0 ] || { echo "SETUP INCOMPLETE — fix the items above before running the TUI."; exit 1; }

python3 - <<'PY'
import sys
sys.path.insert(0, "python")
import quantcore_cpp
print(f"[OK] quantcore_cpp {quantcore_cpp.version()} imported")
PY

echo ""
echo "=========================================="
echo " ✅ SETUP COMPLETE"
echo "=========================================="
echo " Activate venv: source .venv/bin/activate"
echo " Run TUI: python3 infra_tui.py"
echo " Optional — unit tests:"
echo "   pytest"
echo "   cmake -S cpp/tests -B build-cpptests && cmake --build build-cpptests"
echo "   ctest --test-dir build-cpptests --output-on-failure"
