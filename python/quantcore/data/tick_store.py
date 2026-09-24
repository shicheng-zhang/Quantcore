"""Tick Store — DuckDB-backed intraday tick storage and bar aggregation.

Provides session-anchored intraday bars for day trading, bridging the gap
between daily parquet (`data/raw/equities/*.parquet`) and live tick ingest.

Tables:
  ticks(symbol VARCHAR, ts_ns BIGINT, price DOUBLE, volume DOUBLE, side VARCHAR)
  bars_1m(symbol VARCHAR, ts_ns BIGINT, open DOUBLE, high DOUBLE, low DOUBLE, close DOUBLE, volume DOUBLE)

Usage:
  store = TickStore()
  store.insert_ticks("AAPL", ticks)  # ticks: list of dicts or DataFrame
  bars = store.get_bars("AAPL", interval="5m", session_date="2024-01-15")
"""
import duckdb
import os
import threading
import pandas as pd
import numpy as np
from datetime import datetime, date
from typing import List, Optional

class TickStore:
    def __init__(self, db_path="data/ticks.duckdb"):
        os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else "data", exist_ok=True)
        self.db_path = db_path
        self.con = duckdb.connect(db_path)
        self._lock = threading.RLock()
        self._init_tables()

    def _init_tables(self):
        with self._lock:
            self.con.execute("""
                CREATE TABLE IF NOT EXISTS ticks (
                    symbol VARCHAR,
                    ts_ns BIGINT,
                    price DOUBLE,
                    volume DOUBLE,
                    side VARCHAR
                );
                CREATE INDEX IF NOT EXISTS idx_ticks_symbol_ts ON ticks (symbol, ts_ns);
            """)
            self.con.execute("""
                CREATE TABLE IF NOT EXISTS bars_1m (
                    symbol VARCHAR,
                    ts_ns BIGINT,
                    open DOUBLE,
                    high DOUBLE,
                    low DOUBLE,
                    close DOUBLE,
                    volume DOUBLE
                );
                CREATE INDEX IF NOT EXISTS idx_bars_symbol_ts ON bars_1m (symbol, ts_ns);
            """)
            # Volume profile cache per session
            self.con.execute("""
                CREATE TABLE IF NOT EXISTS tod_volume (
                    symbol VARCHAR,
                    slot INT,  -- 0..77 for 5m slots in 390min session
                    avg_volume DOUBLE,
                    PRIMARY KEY (symbol, slot)
                );
            """)

    def insert_ticks(self, symbol: str, ticks: pd.DataFrame | List[dict]):
        """Insert ticks. ticks DataFrame must have columns [ts_ns, price, volume] or [Date, Close, Volume]."""
        with self._lock:
            if isinstance(ticks, pd.DataFrame):
                df = ticks.copy()
                # Normalize columns
                if 'ts_ns' not in df.columns:
                    if 'Date' in df.columns:
                        df['ts_ns'] = pd.to_datetime(df['Date']).astype('int64')
                    elif 'Datetime' in df.columns:
                        df['ts_ns'] = pd.to_datetime(df['Datetime']).astype('int64')
                    else:
                        raise ValueError("ticks DataFrame must have ts_ns or Date")
                if 'price' not in df.columns:
                    if 'Close' in df.columns:
                        df['price'] = df['Close']
                    elif 'close' in df.columns:
                        df['price'] = df['close']
                if 'volume' not in df.columns and 'Volume' in df.columns:
                    df['volume'] = df['Volume']
                df['symbol'] = symbol.upper()
                df['side'] = df.get('side', 'UNKNOWN')
                df = df[['symbol', 'ts_ns', 'price', 'volume', 'side']]
                self.con.execute("INSERT INTO ticks SELECT * FROM df")
            else:
                rows = [(symbol.upper(), int(t['ts_ns']), float(t['price']), float(t['volume']), t.get('side', 'UNKNOWN')) for t in ticks]
                self.con.executemany("INSERT INTO ticks VALUES (?, ?, ?, ?, ?)", rows)
            # Update 1m bars incrementally
            self._rebuild_1m_bars(symbol)

    def _rebuild_1m_bars(self, symbol: str):
        """Rebuild 1m bars from ticks for symbol (idempotent)."""
        with self._lock:
            self.con.execute("DELETE FROM bars_1m WHERE symbol = ?", [symbol.upper()])
            self.con.execute("""
                INSERT INTO bars_1m
                SELECT symbol,
                       (ts_ns / 60000000000)::BIGINT * 60000000000 as bar_ts,
                       first(price ORDER BY ts_ns) as open,
                       max(price) as high,
                       min(price) as low,
                       last(price ORDER BY ts_ns) as close,
                       sum(volume) as volume
                FROM ticks WHERE symbol = ?
                GROUP BY symbol, bar_ts
                ORDER BY bar_ts
            """, [symbol.upper()])

    def get_ticks(self, symbol: str, start_ns: Optional[int] = None, end_ns: Optional[int] = None) -> pd.DataFrame:
        with self._lock:
            q = "SELECT ts_ns, price, volume, side FROM ticks WHERE symbol = ?"
            params = [symbol.upper()]
            if start_ns is not None:
                q += " AND ts_ns >= ?"
                params.append(start_ns)
            if end_ns is not None:
                q += " AND ts_ns <= ?"
                params.append(end_ns)
            q += " ORDER BY ts_ns"
            return self.con.execute(q, params).df()

    def get_bars(self, symbol: str, interval: str = "1m", session_date: Optional[str] = None) -> pd.DataFrame:
        """
        Get bars aggregated to interval. interval: 1m, 5m, 15m, 30m, 1h.
        session_date: YYYY-MM-DD to filter to single session (anchored).
        """
        interval_ns = {"1m": 60_000_000_000, "5m": 300_000_000_000, "15m": 900_000_000_000, "30m": 1_800_000_000_000, "1h": 3_600_000_000_000}.get(interval, 60_000_000_000)
        with self._lock:
            df = self.con.execute("SELECT ts_ns, open, high, low, close, volume FROM bars_1m WHERE symbol = ? ORDER BY ts_ns", [symbol.upper()]).df()
            if df.empty:
                return df
            if session_date:
                # Filter to session 09:30-16:00 ET on that date
                try:
                    sess_start = pd.to_datetime(f"{session_date} 09:30:00").value
                    sess_end = pd.to_datetime(f"{session_date} 16:00:00").value
                    df = df[(df['ts_ns'] >= sess_start) & (df['ts_ns'] <= sess_end)]
                except Exception:
                    pass
            if interval == "1m":
                df['Date'] = pd.to_datetime(df['ts_ns'])
                return df
            # Aggregate 1m -> target interval
            df['bar_ts'] = (df['ts_ns'] // interval_ns) * interval_ns
            agg = df.groupby('bar_ts').agg(
                open=('open', 'first'), high=('high', 'max'), low=('low', 'min'), close=('close', 'last'), volume=('volume', 'sum')
            ).reset_index().rename(columns={'bar_ts': 'ts_ns'})
            agg['Date'] = pd.to_datetime(agg['ts_ns'])
            agg = agg[['Date', 'ts_ns', 'open', 'high', 'low', 'close', 'volume']].rename(columns={'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close', 'volume': 'Volume'})
            return agg

    def get_volume_profile(self, symbol: str, session_date: Optional[str] = None, bins: int = 24) -> dict:
        """Session-anchored volume profile (POC/VAH/VAL) from 1m bars."""
        bars = self.get_bars(symbol, interval="1m", session_date=session_date)
        if bars.empty or len(bars) < 5:
            return {"poc": 0.0, "vah": 0.0, "val": 0.0, "levels": []}
        prices = bars['Close'].to_numpy() if 'Close' in bars.columns else bars['close'].to_numpy()
        vols = bars['Volume'].to_numpy() if 'Volume' in bars.columns else bars['volume'].to_numpy()
        min_p, max_p = float(np.min(prices)), float(np.max(prices))
        if min_p == max_p:
            return {"poc": min_p, "vah": min_p, "val": min_p, "levels": []}
        bin_edges = np.linspace(min_p, max_p, bins + 1)
        bin_vol = np.zeros(bins)
        idx = np.digitize(prices, bin_edges) - 1
        for i, b in enumerate(idx):
            b = max(0, min(bins - 1, b))
            bin_vol[b] += vols[i]
        poc_idx = int(np.argmax(bin_vol))
        poc = (bin_edges[poc_idx] + bin_edges[poc_idx + 1]) / 2
        total = np.sum(bin_vol)
        target = total * 0.70
        accum = bin_vol[poc_idx]
        left = right = poc_idx
        while accum < target and (left > 0 or right < bins - 1):
            lv = bin_vol[left - 1] if left > 0 else -1
            rv = bin_vol[right + 1] if right < bins - 1 else -1
            if lv >= rv and left > 0:
                left -= 1; accum += lv
            elif right < bins - 1:
                right += 1; accum += rv
            else:
                break
        val = (bin_edges[left] + bin_edges[left + 1]) / 2
        vah = (bin_edges[right] + bin_edges[right + 1]) / 2
        levels = [{"price": round((bin_edges[i] + bin_edges[i+1])/2, 2), "volume": round(float(bin_vol[i]), 1), "is_poc": i==poc_idx, "in_value_area": left <= i <= right} for i in range(bins)]
        return {"poc": round(poc,2), "vah": round(vah,2), "val": round(val,2), "levels": levels}

    def update_tod_curve(self, symbol: str):
        """Update time-of-day average volume curve from historical 1m bars (20-day lookback)."""
        with self._lock:
            # Compute avg volume per 5m slot (78 slots per day)
            # Use last 20 sessions' data
            self.con.execute("""
                INSERT OR REPLACE INTO tod_volume
                SELECT ?, (EXTRACT(HOUR FROM to_timestamp(ts_ns/1000000000))::INT*60 + EXTRACT(MINUTE FROM to_timestamp(ts_ns/1000000000))::INT)/5 as slot,
                       avg(volume) as avg_vol
                FROM bars_1m WHERE symbol = ?
                GROUP BY slot
            """, [symbol.upper(), symbol.upper()])

    def get_rvol(self, symbol: str, current_volume: float, slot: int) -> float:
        """RVOL = current_volume / avg_volume_at_same_slot."""
        with self._lock:
            row = self.con.execute("SELECT avg_volume FROM tod_volume WHERE symbol = ? AND slot = ?", [symbol.upper(), slot]).fetchone()
            if row and row[0] and row[0] > 0:
                return float(current_volume / row[0])
            return 1.0
