#!/bin/bash
cd "$(dirname "$0")"
BASE="http://127.0.0.1:8765"

echo "============================================================"
echo " PHASE 1 VERIFICATION: Router Migration"
echo "============================================================"

# --- Boot the server if it isn't already up ---
STARTED_BY_US=0
if ! curl -s -o /dev/null "$BASE/openapi.json" 2>/dev/null; then
    echo "[boot] Starting uvicorn..."
    uvicorn web.backend.main:app --host 127.0.0.1 --port 8765 > /tmp/qc_verify_boot.log 2>&1 &
    SERVER_PID=$!
    STARTED_BY_US=1
    READY=0
    for i in $(seq 1 30); do
        if curl -s -o /dev/null "$BASE/openapi.json" 2>/dev/null; then
            echo "[boot] Server ready after ${i}s"
            READY=1
            break
        fi
        sleep 1
    done
    if [ "$READY" = "0" ]; then
        echo "[boot] FAILED to start. Last 25 lines of boot log:"
        echo "------------------------------------------------------------"
        tail -25 /tmp/qc_verify_boot.log
        echo "------------------------------------------------------------"
        kill $SERVER_PID 2>/dev/null
        exit 1
    fi
else
    echo "[boot] Server already running — reusing it"
fi

# --- Run the verifier ---
python3 << 'PYEOF'
import json, re, sys, socket, urllib.request, urllib.error

BASE = "http://127.0.0.1:8765"

# Expected API paths per router (must match the @router decorators exactly)
EXPECTED = {
    "analytics": ["/api/overview", "/api/symbols", "/api/trend/{symbol}",
                  "/api/predictions/{symbol}", "/api/signals", "/api/performance"],
    "research":  ["/api/research/hrp", "/api/research/validation", "/api/backtest/run",
                  "/api/alpha/scan", "/api/alpha/signals"],
    "broker":    ["/api/paper/state", "/api/paper/order", "/api/paper/reset",
                  "/api/paper/autopilot/status", "/api/alpaca/config",
                  "/api/alpaca/status", "/api/alpaca/order"],
    "execution": ["/api/execution/simulate", "/api/nexus/telemetry", "/api/nexus/start",
                  "/api/nexus/logs", "/api/nexus/ghost_status",
                  "/api/day_trading/analyze/{symbol}", "/api/intraday/backtest/{symbol}",
                  "/api/day_trading/alerts", "/api/rl/train"],
    "ops":       ["/api/cio/metrics", "/api/ops/kill_switch", "/api/ops/reset",
                  "/api/ops/start_surveillance", "/api/sim/ledger_verify"],
    "infra":     ["/api/hivemind/status", "/api/hivemind/logs", "/api/statarb/status",
                  "/api/time_machine/report", "/api/macro/state", "/api/alt_data/feed",
                  "/api/vol/surface", "/api/vol/chain", "/api/mlops/health",
                  "/api/risk/gauntlet", "/api/seed/status"],
}

# Safe endpoints to actually invoke (read-only, no yfinance/subprocess)
SMOKE = [
    ("analytics", "/api/performance"),
    ("analytics", "/api/symbols"),
    ("research",  "/api/research/validation"),
    ("research",  "/api/alpha/signals"),
    ("broker",    "/api/paper/state"),
    ("broker",    "/api/alpaca/status"),
    ("broker",    "/api/paper/autopilot/status"),
    ("execution", "/api/nexus/telemetry"),
    ("execution", "/api/nexus/ghost_status"),
    ("ops",       "/api/sim/ledger_verify"),
    ("ops",       "/api/cio/metrics"),
    ("infra",     "/api/macro/state"),
    ("infra",     "/api/vol/surface"),
    ("infra",     "/api/seed/status"),
    ("infra",     "/api/statarb/status"),
]

def get(path):
    try:
        with urllib.request.urlopen(BASE + path, timeout=15) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()
    except Exception as e:
        return None, str(e)

def ws_check(host, port, path):
    try:
        s = socket.create_connection((host, port), timeout=5)
        req = (f"GET {path} HTTP/1.1\r\nHost: {host}:{port}\r\n"
               "Upgrade: websocket\r\nConnection: Upgrade\r\n"
               "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n"
               "Sec-WebSocket-Version: 13\r\n\r\n")
        s.sendall(req.encode())
        resp = s.recv(2048).decode(errors="ignore")
        s.close()
        return "101" in resp.split("\r\n")[0]
    except Exception:
        return False

failures = 0

# --- LAYER 1: static check — no /api/ routes left inline in main.py ---
print("\n--- Layer 1: main.py is slim (no inline /api/ routes) ---")
try:
    with open("web/backend/main.py") as f:
        main_src = f.read()
    leftover = re.findall(r'@app\.(?:get|post|delete|put|websocket)\(\s*["\']/api/[^"\']+', main_src)
    if leftover:
        print(f"  [FAIL] {len(leftover)} /api/ route(s) still defined inline in main.py:")
        for l in leftover[:10]:
            print(f"         {l}")
        failures += 1
    else:
        n_routers = len(re.findall(r'app\.include_router\(', main_src))
        print(f"  [ok]   0 inline /api/ routes; {n_routers} routers included via include_router()")
except FileNotFoundError:
    print("  [FAIL] web/backend/main.py not found")
    failures += 1

# --- LAYER 2: registration check — every router path is in the OpenAPI schema ---
print("\n--- Layer 2: router registration (OpenAPI schema) ---")
status, body = get("/openapi.json")
if status != 200:
    print(f"  [FAIL] /openapi.json returned HTTP {status}")
    failures += 1
    registered = set()
else:
    registered = set(json.loads(body).get("paths", {}).keys())
    print(f"  [info] {len(registered)} paths registered")
    for router, paths in EXPECTED.items():
        missing = [p for p in paths if p not in registered]
        if missing:
            print(f"  [FAIL] {router:10s} missing {len(missing)}: {missing}")
            failures += 1
        else:
            print(f"  [ok]   {router:10s} all {len(paths)} paths registered")

# --- LAYER 3: live smoke tests — endpoints actually execute & return JSON ---
print("\n--- Layer 3: live endpoint smoke tests ---")
for router, path in SMOKE:
    status, body = get(path)
    is_json = False
    if status == 200:
        try:
            json.loads(body); is_json = True
        except Exception:
            pass
    if status == 200 and is_json:
        print(f"  [ok]   {router:10s} {path:38s} HTTP 200 (valid JSON)")
    else:
        print(f"  [FAIL] {router:10s} {path:38s} HTTP {status}" + ("" if is_json else " (not JSON)"))
        failures += 1

# --- LAYER 4: WebSocket handshake ---
print("\n--- Layer 4: WebSocket /ws/tape handshake ---")
if ws_check("127.0.0.1", 8765, "/ws/tape"):
    print("  [ok]   /ws/tape returned 101 Switching Protocols")
else:
    print("  [FAIL] /ws/tape did not complete WebSocket handshake")
    failures += 1

# --- Summary ---
print("\n============================================================")
if failures == 0:
    print(" PHASE 1 VERIFIED ✓  All routers wired, registered, and serving.")
else:
    print(f" PHASE 1 INCOMPLETE ✗  {failures} check(s) failed — see [FAIL] lines above.")
print("============================================================")
sys.exit(0 if failures == 0 else 1)
PYEOF
RESULT=$?

# --- Cleanup if we started the server ---
if [ "$STARTED_BY_US" = "1" ]; then
    kill $SERVER_PID 2>/dev/null
    wait $SERVER_PID 2>/dev/null
fi

exit $RESULT
