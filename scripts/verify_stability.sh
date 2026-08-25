#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

pytest -q
python3 -m compileall -q python web tests
g++ -std=c++20 -fsyntax-only cpp/src/risk_engine.cpp -Icpp/include -Ibuild/_deps/spdlog-src/include
g++ -std=c++20 -fsyntax-only nexus/src/main.cpp -Inexus/include -Inexus/build/_deps/ixwebsocket-src -Inexus/build/_deps/json-src/include -I/usr/include
git diff --check
