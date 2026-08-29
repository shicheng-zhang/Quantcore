"""
Centralized input validation helpers for QuantCore.

These helpers are intentionally strict. They are meant for ticker symbols,
SQL identifiers, and internal file/path inputs that may eventually be touched
by API/UI parameters.
"""

from __future__ import annotations

import re
from pathlib import Path


_SYMBOL_RE = re.compile(r"^[A-Za-z0-9._=-]{1,32}$")
_SQL_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")


def validate_symbol(symbol: str) -> str:
    """
    Validate a market symbol/ticker.

    Allows common ticker characters:
    - letters/numbers
    - dot, underscore, dash
    - equals sign for symbols like EURUSD=X
    """
    if not isinstance(symbol, str):
        raise ValueError("symbol must be a string")

    symbol = symbol.strip().upper()

    if not _SYMBOL_RE.fullmatch(symbol):
        raise ValueError(f"unsafe symbol: {symbol!r}")

    return symbol


def quote_symbol_sql(symbol: str) -> str:
    """
    Return a safely quoted SQL string literal for a validated symbol.

    This is not a substitute for parameterized SQL where available, but it
    blocks SQL injection for the current C++ bridge query_sql interface.
    """
    symbol = validate_symbol(symbol)
    return "'" + symbol.replace("'", "''") + "'"


def validate_sql_identifier(name: str) -> str:
    """
    Validate SQL object identifiers such as temporary view names.
    """
    if not isinstance(name, str):
        raise ValueError("identifier must be a string")

    if not _SQL_IDENTIFIER_RE.fullmatch(name):
        raise ValueError(f"unsafe SQL identifier: {name!r}")

    return name


def validate_safe_relative_path(path: str) -> str:
    """
    Validate a path string for internal parquet/cache access.

    Rules:
    - no NUL bytes
    - no SQL quote characters
    - no parent traversal
    """
    if not isinstance(path, str):
        raise ValueError("path must be a string")

    if "\x00" in path or "'" in path or '"' in path:
        raise ValueError(f"unsafe path: {path!r}")

    p = Path(path)
    if any(part == ".." for part in p.parts):
        raise ValueError(f"path traversal rejected: {path!r}")

    return path
