"""Small, explicit guard for endpoints that mutate trading or process state.

The dashboard is intended to run locally.  Remote control is opt-in through a
dedicated token, rather than accidentally exposing broker and process controls
when Uvicorn is bound to a public interface.
"""
import hmac
import os

from fastapi import Header, HTTPException, Request


def require_control_access(
    request: Request,
    x_quantcore_token: str | None = Header(default=None),
) -> None:
    """Allow loopback clients, or a caller with the configured control token."""
    host = request.client.host if request.client else ""
    if host in {"127.0.0.1", "::1", "localhost", "testclient"}:
        return

    expected = os.getenv("QUANTCORE_CONTROL_TOKEN")
    if expected and x_quantcore_token and hmac.compare_digest(x_quantcore_token, expected):
        return

    raise HTTPException(
        status_code=403,
        detail="Control endpoints are local-only. Set QUANTCORE_CONTROL_TOKEN for remote access.",
    )
