#!/bin/bash
# Launch QuantCore Web Dashboard

echo "=========================================="
echo " QuantCore Web Dashboard"
echo " http://127.0.0.1:8765"
echo "=========================================="

cd "$(dirname "$0")"

# Run FastAPI with uvicorn
uvicorn web.backend.main:app --host 127.0.0.1 --port 8765 --reload
