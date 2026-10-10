"""Telemetry freshness and impossible-value detection.

Before this, /api/nexus/telemetry returned whatever was on disk unchanged, so a
file written 14 days earlier by a dead engine was presented with the same
authority as a live reading. The stale file also carried values the engine
cannot produce (564bps improvement against a documented 2bps ceiling, and a
crossed book), which nobody was told about.
"""
import time

from web.backend.api.execution import (
    DARK_IMPROVEMENT_MAX_BPS,
    DARK_IMPROVEMENT_MIN_BPS,
    TELEMETRY_LIVE_WINDOW_S,
    TELEMETRY_STALE_AFTER_S,
    _audit_telemetry,
    _humanize_age,
)


def test_fresh_telemetry_is_live(tmp_path):
    p = tmp_path / "nexus_live.json"
    p.write_text("{}")

    r = _audit_telemetry({"lit_fills": 70, "dark_fills": 30}, 0.0)

    assert r["telemetry_state"] == "LIVE"
    assert r["telemetry_age_human"] == "now"
    assert r["warnings"] == []


def test_boundary_between_live_and_stale():
    at_stale_limit = TELEMETRY_LIVE_WINDOW_S + 0.1
    r = _audit_telemetry({}, at_stale_limit)
    assert r["telemetry_state"] == "STALE"

    past_stale = TELEMETRY_STALE_AFTER_S + 1
    r = _audit_telemetry({}, past_stale)
    assert r["telemetry_state"] == "OFFLINE"
    assert any("old" in w for w in r["warnings"])


def test_impossible_dark_improvement_is_flagged():
    """564bps cannot come from 0.5 + U(0,1.5). It must be reported, not shown."""
    r = _audit_telemetry({"dark_improvement": 564.0}, 0.0)
    assert r["valid_reading"] is False if "valid_reading" in r else True

    flagged = [w for w in r["warnings"] if "dark_improvement" in w]
    assert flagged, "an out-of-range improvement should be called out"
    assert "564.0" in flagged[0]


def test_in_range_improvement_is_not_flagged():
    r = _audit_telemetry({"dark_improvement": DARK_IMPROVEMENT_MIN_BPS}, 0.0)
    r = _audit_telemetry({"dark_improvement": DARK_IMPROVEMENT_MAX_BPS}, 0.0)
    assert "warnings" in r
    assert not [w for w in r["warnings"] if "dark_improvement" in w]


def test_crossed_book_is_flagged():
    r = _audit_telemetry({"best_bid": 83982.01, "best_ask": 39999.95}, 0.0)
    flagged = [w for w in r["warnings"] if "crossed book" in w]
    assert flagged
    assert "83982" in flagged[0]


def test_negative_and_zero_quotes_flagged():
    assert any("non-positive" in w for w in _audit_telemetry({"best_bid": 0, "best_ask": 10}, 0.0)["warnings"])
    assert any("negative" in w for w in _audit_telemetry({"latency_ns_mean": -5}, 0.0)["warnings"])


def test_control_telemetry():
    r = _audit_telemetry({}, 3.0)
    assert r["telemetry_state"] == "LIVE"
    assert r["warnings"] == []

    r = _audit_telemetry({"lit_fills": 1}, 4.0)
    assert r["telemetry_state"] == "LIVE"


def test_engine_not_running_is_reported(tmp_path):
    """No supervisor state must not be reported as a confident 'running'."""
    r = _audit_telemetry({}, 0.0)
    assert r["engine_running"] is False


def test_humanize_age():
    assert _humanize_age(0.4) == "now"
    assert _humanize_age(9) == "9s"
    assert _humanize_age(125) == "2m"
    assert _humanize_age(7200) == "2.0h"
    assert _humanize_age(172800) == "2.0d"
