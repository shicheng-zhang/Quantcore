"""Tests for the local-only control-plane guard."""
import os
import pytest
from fastapi import HTTPException

from web.backend.security import require_control_access


class _Client:
    def __init__(self, host):
        self.host = host


class _Request:
    def __init__(self, host):
        self.client = _Client(host)


def test_control_access_allows_loopback():
    require_control_access(_Request("127.0.0.1"), None)


def test_control_access_requires_token_for_remote(monkeypatch):
    monkeypatch.setenv("QUANTCORE_CONTROL_TOKEN", "correct-token")
    with pytest.raises(HTTPException) as exc:
        require_control_access(_Request("10.0.0.9"), "wrong-token")
    assert exc.value.status_code == 403
    require_control_access(_Request("10.0.0.9"), "correct-token")
