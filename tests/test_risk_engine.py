"""End-to-end tests for the session-aware risk engine, driven through the
compiled pybind11 bindings.

These exist because the C++ engine used to be *unreachable* from Python: the
RiskConfig/PyPortfolioSnapshot bindings omitted the session fields
(flat_deadline_ns, timestamp_ns, positions), so every day-trading gate in
RiskEngine was silently stuck at its disabled default. The C++ behaviour itself
is covered by ctest (cpp/tests/test_risk_engine.cpp).
"""
import sys
from pathlib import Path

# The compiled extension ships as python/quantcore/quantcore_cpp*.so, and is
# imported as "quantcore.quantcore_cpp" (mirrors web/backend/analytics.py).
_QC_PKG = Path(__file__).resolve().parent.parent / "python"
if str(_QC_PKG) not in sys.path:
    sys.path.insert(0, str(_QC_PKG))

import pytest

quantcore_cpp = pytest.importorskip(
    "quantcore.quantcore_cpp",
    reason="quantcore_cpp not built — run setup.sh to build it",
)

NS_PER_SEC = 10**9
FLAT_DEADLINE_NS = (15 * 3600 + 55 * 60) * NS_PER_SEC  # 15:55 ET
AFTER_DEADLINE_NS = 16 * 3600 * NS_PER_SEC             # 16:00 ET
BEFORE_DEADLINE_NS = 15 * 3600 * NS_PER_SEC             # 15:00 ET


def _engine():
    cfg = quantcore_cpp.RiskConfig()
    cfg.flat_deadline_ns = FLAT_DEADLINE_NS
    return quantcore_cpp.RiskEngine(cfg, quantcore_cpp.EventBus())


def _portfolio(ts, equity=100000.0):
    pf = quantcore_cpp.PortfolioSnapshot()
    pf.timestamp_ns = ts
    pf.total_equity = equity
    pf.cash = equity
    return pf


def _order(side, qty, symbol="AAPL"):
    o = quantcore_cpp.Order()
    o.id = 1
    o.symbol = symbol
    o.side = side
    o.type = quantcore_cpp.OrderType.MARKET
    o.quantity = qty
    o.limit_price = 100.0
    return o


def _long(pf, qty, symbol="AAPL", cost=100.0):
    pos = quantcore_cpp.Position()
    pos.symbol = symbol
    pos.quantity = qty
    pos.average_cost = cost
    # def_readwrite returns a *copy* of the std::vector, so appending is a
    # no-op — the list has to be assigned back.
    pf.positions = list(pf.positions) + [pos]
    return pf


def test_session_fields_are_bound():
    """Regression guard: the session gates must be configurable from Python."""
    cfg = quantcore_cpp.RiskConfig()
    for field in ("flat_deadline_ns", "session_start_ns", "session_end_ns"):
        assert hasattr(cfg, field), f"RiskConfig.{field} not exposed to Python"
        setattr(cfg, field, FLAT_DEADLINE_NS)
        assert getattr(cfg, field) == FLAT_DEADLINE_NS

    pf = quantcore_cpp.PortfolioSnapshot()
    for field in ("timestamp_ns", "positions"):
        assert hasattr(pf, field), f"PortfolioSnapshot.{field} not exposed to Python"


def test_flat_deadline_blocks_add_after_1555():
    engine = _engine()
    pf = _long(_portfolio(AFTER_DEADLINE_NS), 20)

    res = engine.check_order(_order(quantcore_cpp.Side.BUY, 10), pf)
    assert res.decision == quantcore_cpp.RiskDecision.REJECT
    assert "reducing" in res.reason  # held a position and tried to add to it


def test_flat_deadline_blocks_new_position_after_1555():
    engine = _engine()
    pf = _portfolio(AFTER_DEADLINE_NS)

    res = engine.check_order(_order(quantcore_cpp.Side.BUY, 10), pf)
    assert res.decision == quantcore_cpp.RiskDecision.REJECT
    assert "no new positions" in res.reason


def test_flat_deadline_allows_reducing_after_1555():
    engine = _engine()
    pf = _long(_portfolio(AFTER_DEADLINE_NS), 20)

    res = engine.check_order(_order(quantcore_cpp.Side.SELL, 10), pf)
    assert res.decision == quantcore_cpp.RiskDecision.APPROVE


def test_flat_deadline_allows_new_position_before_1555():
    engine = _engine()
    pf = _portfolio(BEFORE_DEADLINE_NS)

    res = engine.check_order(_order(quantcore_cpp.Side.BUY, 10), pf)
    assert res.decision == quantcore_cpp.RiskDecision.APPROVE


def test_covering_short_counts_as_reducing():
    """The concentration gate must not treat a buy-back as new exposure."""
    engine = _engine()
    pf = _portfolio(BEFORE_DEADLINE_NS)

    pos = quantcore_cpp.Position()
    pos.symbol = "AAPL"
    pos.quantity = -20  # short 20
    pos.average_cost = 100.0
    # Assign the list (def_readwrite hands back a copy; appending is a no-op).
    pf.positions = [pos]

    # Old behaviour: existing (20 @ 100) + order (20 @ 100) = 40% of the book,
    # which blows the 5% concentration cap and rejects a plain cover.
    # Fixed: post-trade position is 0, so it must be approved.
    cfg = quantcore_cpp.RiskConfig()
    cfg.max_position_pct = 0.05
    engine = quantcore_cpp.RiskEngine(cfg, quantcore_cpp.EventBus())

    res = engine.check_order(_order(quantcore_cpp.Side.BUY, 20), pf)
    assert res.decision == quantcore_cpp.RiskDecision.APPROVE


def test_consecutive_losses_halts_trading():
    cfg = quantcore_cpp.RiskConfig()
    cfg.max_consecutive_losses = 5
    engine = quantcore_cpp.RiskEngine(cfg, quantcore_cpp.EventBus())
    pf = _portfolio(BEFORE_DEADLINE_NS)

    for _ in range(5):
        engine.record_trade_result(False, "AAPL", BEFORE_DEADLINE_NS)

    assert engine.is_halted()
    assert engine.consecutive_losses() == 5
    res = engine.check_order(_order(quantcore_cpp.Side.BUY, 10), pf)
    assert res.decision == quantcore_cpp.RiskDecision.REJECT
