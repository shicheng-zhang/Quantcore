#!/bin/bash
cd "$(dirname "$0")"
echo "============================================================"
echo " FINAL SWEEP: Everything remaining for 1.0.0-RC4"
echo "============================================================"

# ============================================================
# 1. WIRE PROVIDER INTO ANALYTICS.PY + FIX LAST PRINT()
# ============================================================
echo ""
echo "--- [1/9] Wiring data provider fallback into analytics.py ---"
python3 << 'PYEOF'
import sys

path = "web/backend/analytics.py"
with open(path) as f:
    src = f.read()

changes = 0

# 1a. Replace yf.download in fetch_live_data with fetch_ohlcv (provider fallback)
old_fetch = """        df = yf.download(symbol, period=period, interval=interval, progress=False)
        if df.empty:
            # Rate-limited or transient failure: serve last good data instead of erroring
            if cached is not None:
                print(f"[WARN] yfinance empty for {symbol}; serving stale cache")
                return cached["df"].copy()
            raise ValueError(f"No live data found for {symbol} ({period} / {interval})")"""

new_fetch = """        try:
            df = fetch_ohlcv(symbol, period, interval)
        except (ValueError, Exception):
            # All providers failed: serve last good data instead of erroring
            if cached is not None:
                logger.warning(f"All providers failed for {symbol}; serving stale cache")
                return cached["df"].copy()
            raise ValueError(f"No live data found for {symbol} ({period} / {interval})")"""

if old_fetch in src:
    src = src.replace(old_fetch, new_fetch)
    changes += 1
    print("  [ok] fetch_live_data: yf.download -> fetch_ohlcv (Stooq fallback active)")
else:
    print("  [skip] fetch_live_data: already wired or pattern changed")

# 1b. Replace yf.Ticker in add_symbol with fetch_history_max
old_add = """        try:
            # Use Ticker.history() instead of download() to guarantee flat columns
            ticker = yf.Ticker(symbol)
            df = ticker.history(period="max")
        except Exception as e:
            raise ValueError(f"yfinance network error: {str(e)}")
        if df.empty:
            raise ValueError(f"No data found for {symbol}. Check if the ticker is valid.")"""

new_add = """        df = fetch_history_max(symbol)
        if df is None or df.empty:
            raise ValueError(f"No data found for {symbol} from any provider. Check if the ticker is valid.")"""

if old_add in src:
    src = src.replace(old_add, new_add)
    changes += 1
    print("  [ok] add_symbol: yf.Ticker -> fetch_history_max (Stooq fallback active)")
else:
    print("  [skip] add_symbol: already wired or pattern changed")

if changes > 0:
    try:
        compile(src, path, "exec")
    except SyntaxError as e:
        print(f"  [FAIL] Syntax error: {e} — reverting")
        sys.exit(1)
    with open(path, "w") as f:
        f.write(src)
    print(f"  [saved] analytics.py ({changes} changes)")
else:
    print("  [no-op] analytics.py unchanged")
PYEOF

# ============================================================
# 2. FIX BASE.HTML EDU DRAWER BUG (undefined drawer/overlay vars)
# ============================================================
echo ""
echo "--- [2/9] Fixing edu drawer bug in base.html ---"
python3 << 'PYEOF'
path = "web/templates/base.html"
with open(path) as f:
    src = f.read()

changes = 0
replacements = [
    ("    drawer.classList.add('open');", "    document.getElementById('edu-drawer').classList.add('open');"),
    ("    overlay.classList.add('open');", "    document.getElementById('edu-overlay').classList.add('open');"),
    ("    drawer.classList.remove('open');", "    document.getElementById('edu-drawer').classList.remove('open');"),
    ("    overlay.classList.remove('open');", "    document.getElementById('edu-overlay').classList.remove('open');"),
]

for old, new in replacements:
    if old in src:
        src = src.replace(old, new)
        changes += 1

if changes > 0:
    with open(path, "w") as f:
        f.write(src)
    print(f"  [ok] Fixed {changes} undefined variable references (drawer/overlay -> getElementById)")
else:
    print("  [skip] Already fixed or pattern changed")
PYEOF

# ============================================================
# 3. FIX NEXUS.HTML DEAD DOM REFERENCES (lat-mean/p99/max)
# ============================================================
echo ""
echo "--- [3/9] Removing dead DOM references in nexus.html ---"
python3 << 'PYEOF'
path = "web/templates/nexus.html"
with open(path) as f:
    src = f.read()

dead_lines = [
    "            document.getElementById('lat-mean').innerText = `${(data.latency_ns_mean || 0).toFixed(1)} ns`;\n",
    "            document.getElementById('lat-p99').innerText = `${(data.latency_ns_p99 || 0).toFixed(1)} ns`;\n",
    "            document.getElementById('lat-max').innerText = `${(data.latency_ns_max || 0).toFixed(1)} ns`;\n",
]

changes = 0
for line in dead_lines:
    if line in src:
        src = src.replace(line, "")
        changes += 1

if changes > 0:
    with open(path, "w") as f:
        f.write(src)
    print(f"  [ok] Removed {changes} dead DOM references (lat-mean/p99/max don't exist in HTML)")
else:
    print("  [skip] Already removed or pattern changed")
PYEOF

# ============================================================
# 4. DELETE .BAK FILES
# ============================================================
echo ""
echo "--- [4/9] Deleting .bak files ---"
BAK_COUNT=0
for f in web/backend/main.py.bak web/backend/analytics.py.bak \
         python/quantcore/research/backtester.py.bak \
         python/quantcore/vol/black_scholes.py.bak \
         web/templates/backtest.html.bak; do
    if [ -f "$f" ]; then
        rm "$f"
        echo "  [del] $f"
        BAK_COUNT=$((BAK_COUNT + 1))
    fi
done
echo "  Removed $BAK_COUNT backup files"

# ============================================================
# 5. ADD CONFIG_VERSION TO SYSTEM.YAML
# ============================================================
echo ""
echo "--- [5/9] Adding config_version to system.yaml ---"
if ! grep -q "config_version" config/system.yaml; then
    sed -i '1i config_version: 1' config/system.yaml
    echo "  [ok] Added config_version: 1"
else
    echo "  [skip] config_version already present"
fi

# ============================================================
# 6. UPDATE README.MD VERSION
# ============================================================
echo ""
echo "--- [6/9] Updating README.md version ---"
sed -i 's/V1.0-Alpha, RC3/V1.0.0-RC4/g' README.md
sed -i 's/V1.0-AlphaRC3/V1.0.0-RC4/g' README.md
echo "  [ok] README.md -> V1.0.0-RC4"

# ============================================================
# 7. UPDATE RELEASES.MD WITH RC4 NOTES
# ============================================================
echo ""
echo "--- [7/9] Updating RELEASES.md ---"
if ! grep -q "v1.0.0-rc.4" RELEASES.md; then
    cat > /tmp/rc4_notes.md << 'NOTES'
## v1.0.0-rc.4
**Status:** Release Candidate
**Highlights:**
- Phase 1 complete: monolithic main.py split into 7 modular API routers
- Data provider fallback: yfinance -> Stooq CSV (kills single point of failure)
- Structured logging: centralized logging_config.py replaces scattered print()
- Predictions endpoint hardened: dropna + isfinite guards + JSON sanitization
- CAGR total-loss guard: prevents complex number NaN on >100% drawdown
- Vol surface determinism: seeded RNG prevents chart flicker
- DSR overfit detection: bt-trials input wired to Risk Gauntlet num_trials
- Frontend fixes: edu drawer getElementById, nexus.html dead DOM refs removed
- Stub modules labeled EXPERIMENTAL in navigation
- Versioned config: config_version field in system.yaml
- Deleted all .bak files, added .gitignore

NOTES
    sed -i '/^# QuantCore Releases/r /tmp/rc4_notes.md' RELEASES.md
    rm -f /tmp/rc4_notes.md
    echo "  [ok] Added v1.0.0-rc.4 release notes"
else
    echo "  [skip] RC4 notes already present"
fi

# ============================================================
# 8. LABEL STUB MODULES AS EXPERIMENTAL IN NAV
# ============================================================
echo ""
echo "--- [8/9] Labeling stub modules as EXPERIMENTAL in nav ---"
python3 << 'PYEOF'
path = "web/templates/base.html"
with open(path) as f:
    src = f.read()

changes = 0

# Satellite Lab -> add EXP badge
old_sat = """Satellite Lab</a>"""
new_sat = """Satellite Lab <span class="text-[9px] bg-pink-900/80 text-pink-300 px-1.5 py-0.5 rounded ml-1 align-middle">EXP</span></a>"""
if old_sat in src and "EXP</span></a>" not in src.split("Satellite Lab")[1][:120]:
    src = src.replace(old_sat, new_sat, 1)
    changes += 1
    print("  [ok] Satellite Lab -> EXP badge")

# RL Execution -> add EXP badge
old_rl = """RL Execution</a>"""
new_rl = """RL Execution <span class="text-[9px] bg-orange-900/80 text-orange-300 px-1.5 py-0.5 rounded ml-1 align-middle">EXP</span></a>"""
if old_rl in src and "EXP</span></a>" not in src.split("RL Execution")[1][:120]:
    src = src.replace(old_rl, new_rl, 1)
    changes += 1
    print("  [ok] RL Execution -> EXP badge")

if changes > 0:
    with open(path, "w") as f:
        f.write(src)
else:
    print("  [skip] Already labeled or pattern changed")
PYEOF

# ============================================================
# 9. ADD .GITIGNORE + NEW TESTS
# ============================================================
echo ""
echo "--- [9/9] Adding .gitignore and new test files ---"

# .gitignore
if [ ! -f .gitignore ]; then
    cat > .gitignore << 'GITIGNORE'
# Runtime data (regenerated by seed_universe.py)
data/
data_cache/

# Build artifacts
build/
nexus/build/
*.so

# Python
__pycache__/
*.pyc
*.pyo
.pytest_cache/

# Backups
*.bak

# IDE
.vscode/
.idea/
*.swp
GITIGNORE
    echo "  [ok] Created .gitignore"
else
    echo "  [skip] .gitignore already exists"
fi

# test_provider.py
cat > tests/test_provider.py << 'TESTPROV'
"""Tests for the unified data provider with Stooq fallback."""
import sys
import os
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from python.quantcore.data.provider import _to_stooq_symbol, _PERIOD_TO_DAYS


def test_stooq_symbol_mapping_equities():
    """US equities get .us suffix."""
    assert _to_stooq_symbol("SPY") == "spy.us"
    assert _to_stooq_symbol("AAPL") == "aapl.us"
    assert _to_stooq_symbol("NVDA") == "nvda.us"


def test_stooq_symbol_mapping_crypto():
    """Crypto symbols map to Stooq format."""
    assert _to_stooq_symbol("BTC-USD") == "btcusd"
    assert _to_stooq_symbol("ETH-USD") == "ethusd"


def test_stooq_symbol_unsupported():
    """Unsupported symbols return None."""
    assert _to_stooq_symbol("INVALID-TICKER-123") is None


def test_period_to_days_mapping():
    """Period strings map to correct day counts."""
    assert _PERIOD_TO_DAYS["1y"] == 365
    assert _PERIOD_TO_DAYS["5d"] == 5
    assert _PERIOD_TO_DAYS["max"] is None
TESTPROV
echo "  [ok] Created tests/test_provider.py"

# test_logging.py
cat > tests/test_logging.py << 'TESTLOG'
"""Tests for the centralized logging configuration."""
import sys
import os
import logging

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from python.quantcore.logging_config import get_logger, setup_logging


def test_get_logger_returns_logger():
    """get_logger returns a standard Python Logger."""
    logger = get_logger("test.module")
    assert isinstance(logger, logging.Logger)


def test_get_logger_strips_prefix():
    """get_logger strips python.quantcore prefix for cleaner output."""
    logger = get_logger("python.quantcore.research.backtester")
    assert logger.name == "research.backtester"


def test_setup_logging_idempotent():
    """Calling setup_logging twice doesn't add duplicate handlers."""
    setup_logging()
    root = logging.getLogger()
    handler_count = len(root.handlers)
    setup_logging()
    assert len(root.handlers) == handler_count
TESTLOG
echo "  [ok] Created tests/test_logging.py"

# ============================================================
# VERIFY
# ============================================================
echo ""
echo "--- Verification ---"
python3 -c "
import py_compile, sys
files = [
    'web/backend/analytics.py',
    'web/backend/main.py',
    'python/quantcore/data/provider.py',
    'python/quantcore/logging_config.py',
    'tests/test_provider.py',
    'tests/test_logging.py',
]
ok = 0
for f in files:
    try:
        py_compile.compile(f, doraise=True)
        ok += 1
    except py_compile.PyCompileError as e:
        print(f'  [FAIL] {f}: {e}')
print(f'  {ok}/{len(files)} files compile cleanly')
"

echo ""
echo "============================================================"
echo " SWEEP COMPLETE"
echo "============================================================"
echo ""
echo " Run: pytest -v && bash phase1_verify.sh"
echo "============================================================"
