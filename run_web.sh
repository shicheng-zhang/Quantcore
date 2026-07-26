#!/bin/bash
# Launch QuantCore Web Dashboard

echo "=========================================="
echo " QuantCore Web Dashboard"
echo " http://127.0.0.1:8765"
echo "=========================================="

cd "$(dirname "$0")"

# Add to the top of run_web.sh (after the cd):
export LD_LIBRARY_PATH="$(pwd)/build/_deps/duckdb-build/src:$(pwd)/python/quantcore:$LD_LIBRARY_PATH"

# Run FastAPI with uvicorn
uvicorn web.backend.main:app --host 127.0.0.1 --port 8765 --reload
