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
