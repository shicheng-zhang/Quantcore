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


def test_control_access_ignores_spoofed_forwarded_for(monkeypatch):
    """request.client.host is the peer address; a forged X-Forwarded-For header
    must not be able to pass as loopback."""
    monkeypatch.delenv("QUANTCORE_CONTROL_TOKEN", raising=False)

    class _SpoofedRequest(_Request):
        def __init__(self):
            super().__init__("203.0.113.7")
            self.headers = {"x-forwarded-for": "127.0.0.1"}

    with pytest.raises(HTTPException) as exc:
        require_control_access(_SpoofedRequest(), None)
    assert exc.value.status_code == 403


def test_restricted_unpickler_allows_the_only_written_format():
    """The cache stores exactly (y, x) tuples of floats."""
    import io
    import pickle

    from python.quantcore.hivemind.quant_daemon import _SafeUnpickler

    payload = pickle.dumps(([1.0, 2.0, 3.0], [4.0, 5.0]))
    loaded = _SafeUnpickler(io.BytesIO(payload)).load()
    assert loaded == ([1.0, 2.0, 3.0], [4.0, 5.0])


def test_restricted_unpickler_rejects_arbitrary_classes():
    """A crafted pickle must not be able to import os/posix and run code."""
    import io
    import pickle

    import pytest

    from python.quantcore.hivemind.quant_daemon import _SafeUnpickler

    class _Payload:
        def __reduce__(self):
            return (eval, ("1+1",))

    for reduce_target in ([_Payload()], eval, os.system):
        payload = pickle.dumps(reduce_target)
        with pytest.raises((pickle.UnpicklingError, AttributeError)):
            _SafeUnpickler(io.BytesIO(payload)).load()
