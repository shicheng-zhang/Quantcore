"""Unified market data provider with automatic fallback.

Provider priority:
  1. yfinance (primary — supports intraday + daily, all asset classes)
  2. Stooq CSV (fallback — daily only, US equities + major crypto, no API key)

If yfinance is rate-limited, down, or returns empty data, Stooq is tried
automatically. Intraday intervals degrade gracefully (Stooq is daily-only,
so we raise a clear error rather than returning wrong data).
"""
import time
import io
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional

# In-memory TTL cache: {cache_key: (timestamp, DataFrame)}
_cache: dict = {}
_CACHE_TTL = 60  # seconds


def _cache_get(key: str) -> Optional[pd.DataFrame]:
    if key in _cache:
        ts, df = _cache[key]
        if time.time() - ts < _CACHE_TTL:
            return df.copy()
        del _cache[key]
    return None


def _cache_set(key: str, df: pd.DataFrame):
    _cache[key] = (time.time(), df.copy())


# --- Stooq symbol mapping ---
_STOOQ_CRYPTO = {
    "BTC-USD": "btcusd",
    "ETH-USD": "ethusd",
    "SOL-USD": "solusd",
    "AVAX-USD": "avaxusd",
    "XRP-USD": "xrpusd",
    "ADA-USD": "adausd",
    "DOGE-USD": "dogeusd",
    "DOT-USD": "dotusd",
    "LINK-USD": "linkusd",
    "BNB-USD": "bnbusd",
}

_PERIOD_TO_DAYS = {
    "1d": 1, "5d": 5, "7d": 7,
    "1mo": 30, "2mo": 60, "3mo": 90, "6mo": 180,
    "1y": 365, "2y": 730, "5y": 1825, "10y": 3650,
    "ytd": None, "max": None,
}


def _to_stooq_symbol(symbol: str) -> Optional[str]:
    """Map a yfinance-style symbol to Stooq format. Returns None if unsupported."""
    sym = symbol.upper().strip()
    if sym in _STOOQ_CRYPTO:
        return _STOOQ_CRYPTO[sym]
    # US equities/ETFs: append .us
    if sym.isalpha() and len(sym) <= 5:
        return sym.lower() + ".us"
    return None


def _fetch_stooq(symbol: str, period: str = "1y", interval: str = "1d") -> Optional[pd.DataFrame]:
    """Fetch daily OHLCV from Stooq. Returns None on failure."""
    import requests

    if interval not in ("1d", "1wk", "1mo"):
        return None  # Stooq is daily-only

    stooq_sym = _to_stooq_symbol(symbol)
    if stooq_sym is None:
        return None

    # Build URL with date range
    days = _PERIOD_TO_DAYS.get(period, 365)
    url = f"https://stooq.com/q/d/l/?s={stooq_sym}&i=d"
    if days is not None:
        d2 = datetime.now()
        d1 = d2 - timedelta(days=days + 10)  # small buffer
        url += f"&d1={d1.strftime('%Y%m%d')}&d2={d2.strftime('%Y%m%d')}"

    try:
        resp = requests.get(url, timeout=10, headers={"User-Agent": "QuantCore/1.0"})
        if resp.status_code != 200 or not resp.text.strip():
            return None

        df = pd.read_csv(io.StringIO(resp.text))
        if df.empty or "Close" not in df.columns:
            return None

        # Normalize to match yfinance output format
        df = df.rename(columns={"Date": "Date"})
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.sort_values("Date").reset_index(drop=True)

        # Ensure standard columns exist
        for col in ("Open", "High", "Low", "Close", "Volume"):
            if col not in df.columns:
                df[col] = df["Close"] if col != "Volume" else 0

        # Drop rows with NaN Close
        df = df.dropna(subset=["Close"])
        if df.empty:
            return None

        return df[["Date", "Open", "High", "Low", "Close", "Volume"]]
    except Exception:
        return None


def _fetch_yfinance(symbol: str, period: str = "1y", interval: str = "1d") -> Optional[pd.DataFrame]:
    """Fetch from yfinance. Returns None on failure."""
    try:
        import yfinance as yf
        df = yf.download(symbol, period=period, interval=interval, progress=False)
        if df.empty:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
        df = df.reset_index()
        if "Date" not in df.columns and "Datetime" in df.columns:
            df = df.rename(columns={"Datetime": "Date"})
        if "Close" in df.columns:
            df = df.dropna(subset=["Close"])
        if df.empty:
            return None
        return df
    except Exception:
        return None


def fetch_ohlcv(symbol: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
    """Fetch OHLCV data with automatic provider fallback.

    Tries yfinance first, then Stooq (daily intervals only).
    Raises ValueError if all providers fail.
    """
    cache_key = f"{symbol}_{period}_{interval}"

    # Check cache first
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    # Provider 1: yfinance
    df = _fetch_yfinance(symbol, period, interval)
    if df is not None and not df.empty:
        _cache_set(cache_key, df)
        return df

    # Provider 2: Stooq (daily only)
    df = _fetch_stooq(symbol, period, interval)
    if df is not None and not df.empty:
        _cache_set(cache_key, df)
        return df

    raise ValueError(
        f"All data providers failed for {symbol} ({period}/{interval}). "
        f"yfinance returned empty/error and Stooq is unavailable for this symbol/interval."
    )


def fetch_history_max(symbol: str) -> Optional[pd.DataFrame]:
    """Fetch maximum available history (for add_symbol / seeding).

    Tries yfinance Ticker.history(period='max') first, then Stooq full history.
    """
    # yfinance
    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        df = ticker.history(period="max")
        if not df.empty:
            df = df.reset_index()
            if "Date" not in df.columns and "Datetime" in df.columns:
                df = df.rename(columns={"Datetime": "Date"})
            return df
    except Exception:
        pass

    # Stooq full history
    df = _fetch_stooq(symbol, period="max", interval="1d")
    if df is not None:
        return df

    return None
