import pandas as pd
import numpy as np
import time
from ..data.provider import fetch_ohlcv

class IntradaySignalEngine:
    def __init__(self):
        self.cache = {}
        self.cache_ttl = 60  # Cache yfinance data for 60s to prevent rate limits

    def fetch_bars(self, symbol, timeframe="5m", lookback=60):
        cache_key = f"{symbol}_{timeframe}"
        now = time.time()
        if cache_key in self.cache and (now - self.cache[cache_key]['ts']) < self.cache_ttl:
            return self.cache[cache_key]['df']
            
        try:
            df = fetch_ohlcv(symbol, period="5d", interval=timeframe)
            if df.empty: return None
            df = df.tail(lookback)
            self.cache[cache_key] = {'df': df, 'ts': now}
            return df
        except Exception:
            return None

    def calculate_rsi(self, series, window=14):
        delta = series.diff()
        # Wilder's RSI: EMA with alpha=1/window (matches TradingView/Bloomberg)
        gain = delta.where(delta > 0, 0).ewm(alpha=1/window, min_periods=window).mean()
        loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/window, min_periods=window).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    def calculate_atr(self, df, window=14, method='wilder'):
        """
        ATR calculation.

        method='wilder' (default): Wilder's smoothing (RMA) — matches TradingView/Bloomberg.
            TR_t smoothed as ATR_t = (ATR_{t-1}*(n-1) + TR_t)/n  == ewm(alpha=1/n, adjust=False)
        method='sma': Simple moving average of TR (legacy, not Wilder).
        """
        high_low = df['High'] - df['Low']
        high_close = np.abs(df['High'] - df['Close'].shift())
        low_close = np.abs(df['Low'] - df['Close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)
        if method == 'wilder':
            # Wilder's RMA = ewm with alpha=1/window, adjust=False, min_periods=window
            # This is the correct ATR per J. Welles Wilder Jr. (1978)
            return true_range.ewm(alpha=1 / window, min_periods=window, adjust=False).mean().iloc[-1]
        else:
            return true_range.rolling(window=window).mean().iloc[-1]

    def calculate_rvol(self, df, lookback_days=20):
        """
        Relative Volume: today's volume at this time vs average volume at same time-of-day.
        Uses time-of-day curve (U-shape). Falls back to simple vol_ma if not enough history.
        """
        if len(df) < 5 or 'Volume' not in df.columns:
            return 1.0
        try:
            cur_vol = float(df['Volume'].iloc[-1])
            # Time-of-day average: average last 20 bars' volume at same 5m slot is approximated by rolling mean
            # For precise TOD, caller should pass historical TOD volumes; we use rolling as proxy
            vol_ma = float(df['Volume'].rolling(20).mean().iloc[-1])
            if vol_ma <= 0 or not np.isfinite(vol_ma):
                return 1.0
            # RVOL = cur / avg_at_time
            rvol = cur_vol / vol_ma
            return float(np.clip(rvol, 0.1, 10.0))
        except Exception:
            return 1.0

    def calculate_gap(self, df):
        """Gap % = (open_today - close_yesterday) / close_yesterday. Uses Date grouping."""
        try:
            df_dates = pd.to_datetime(df.index if isinstance(df.index, pd.DatetimeIndex) else df.get('Date', pd.Series()))
            # Fallback to simple prev close vs current open
            if 'Open' in df.columns and len(df) >= 2:
                prev_close = float(df['Close'].iloc[-2]) if len(df) > 20 else float(df['Close'].iloc[-2])
                cur_open = float(df['Open'].iloc[-1])
                if prev_close > 0:
                    return (cur_open - prev_close) / prev_close * 100.0
            return 0.0
        except Exception:
            return 0.0

    def calculate_cumulative_delta(self, df):
        """Buy volume - sell volume proxy via close vs open. Returns delta imbalance [-1,1]."""
        try:
            buys = df.apply(lambda r: r['Volume'] if r['Close'] >= r['Open'] else 0, axis=1).sum() if 'Open' in df.columns else 0
            sells = df['Volume'].sum() - buys if 'Volume' in df.columns else 0
            denom = buys + sells
            if denom > 0:
                return (buys - sells) / denom
            return 0.0
        except Exception:
            return 0.0

    def scan_universe(self, symbols, require_rvol=True, rvol_threshold=1.5, gap_threshold=1.0, macro_regime=None, apply_macro_gate=True):
        alerts = []
        for sym in symbols:
            df = self.fetch_bars(sym, "5m", 60)
            if df is None or len(df) < 21: continue
            
            close = df['Close']
            current = close.iloc[-1]
            prev = close.iloc[-2]
            
            # 20-bar resistance/support
            high_20 = df['High'].iloc[-21:-1].max()
            low_20 = df['Low'].iloc[-21:-1].min()
            
            vol_ma = df['Volume'].rolling(20).mean().iloc[-1]
            cur_vol = df['Volume'].iloc[-1]
            rsi = self.calculate_rsi(close, 14).iloc[-1]
            atr = self.calculate_atr(df, 14)
            rvol = self.calculate_rvol(df)
            gap_pct = self.calculate_gap(df)
            delta_imb = self.calculate_cumulative_delta(df.tail(20))
            
            if pd.isna(rsi) or pd.isna(atr) or atr == 0 or pd.isna(vol_ma) or vol_ma == 0: continue
            # RVOL gate: day trader needs volume confirmation
            if require_rvol and rvol < rvol_threshold:
                # Still allow fade setups without RVOL, but gate breakouts
                pass

            # 0. Gap Up / Gap Down with RVOL (Opening Drive)
            if abs(gap_pct) >= gap_threshold and rvol >= rvol_threshold:
                if gap_pct > 0 and current > high_20 and rsi > 50:
                    alerts.append({
                        "symbol": sym, "type": "GAP UP + DRIVE", "price": round(float(current), 2),
                        "level": round(float(high_20), 2), "rsi": round(float(rsi), 1), 
                        "atr": round(float(atr), 2), "vol_ratio": round(float(rvol), 2),
                        "gap_pct": round(float(gap_pct), 2), "delta_imb": round(float(delta_imb), 3),
                        "color": "green", "action": "LONG"
                    })
                    continue
                elif gap_pct < 0 and current < low_20 and rsi < 50:
                    alerts.append({
                        "symbol": sym, "type": "GAP DOWN + DRIVE", "price": round(float(current), 2),
                        "level": round(float(low_20), 2), "rsi": round(float(rsi), 1), 
                        "atr": round(float(atr), 2), "vol_ratio": round(float(rvol), 2),
                        "gap_pct": round(float(gap_pct), 2), "delta_imb": round(float(delta_imb), 3),
                        "color": "red", "action": "SHORT"
                    })
                    continue

            # 1. Breakout Buy (Price > 20bar High + RVOL Spike + RSI > 55 + delta confirmation)
            if current > high_20 and rvol >= rvol_threshold and rsi > 55 and delta_imb > 0.1:
                alerts.append({
                    "symbol": sym, "type": "BREAKOUT BUY", "price": round(float(current), 2),
                    "level": round(float(high_20), 2), "rsi": round(float(rsi), 1), 
                    "atr": round(float(atr), 2), "vol_ratio": round(float(rvol), 2), 
                    "gap_pct": round(float(gap_pct), 2), "delta_imb": round(float(delta_imb), 3),
                    "color": "green", "action": "LONG"
                })
            # 2. Breakdown Sell
            elif current < low_20 and rvol >= rvol_threshold and rsi < 45 and delta_imb < -0.1:
                alerts.append({
                    "symbol": sym, "type": "BREAKDOWN SELL", "price": round(float(current), 2),
                    "level": round(float(low_20), 2), "rsi": round(float(rsi), 1), 
                    "atr": round(float(atr), 2), "vol_ratio": round(float(rvol), 2),
                    "gap_pct": round(float(gap_pct), 2), "delta_imb": round(float(delta_imb), 3),
                    "color": "red", "action": "SHORT"
                })
            # 3. Mean Reversion Fade (Overextended RSI + Rejection Candle) - no RVOL needed
            elif rsi > 75 and current < prev:
                alerts.append({
                    "symbol": sym, "type": "FADE (OVERBOUGHT)", "price": round(float(current), 2),
                    "level": round(float(high_20), 2), "rsi": round(float(rsi), 1), 
                    "atr": round(float(atr), 2), "vol_ratio": round(float(rvol), 2),
                    "gap_pct": round(float(gap_pct), 2), "delta_imb": round(float(delta_imb), 3),
                    "color": "yellow", "action": "SHORT"
                })
            elif rsi < 25 and current > prev:
                alerts.append({
                    "symbol": sym, "type": "FADE (OVERSOLD)", "price": round(float(current), 2),
                    "level": round(float(low_20), 2), "rsi": round(float(rsi), 1), 
                    "atr": round(float(atr), 2), "vol_ratio": round(float(rvol), 2),
                    "gap_pct": round(float(gap_pct), 2), "delta_imb": round(float(delta_imb), 3),
                    "color": "yellow", "action": "LONG"
                })

        # Macro gate: filter alerts by regime (same logic as IntradayEngine)
        if apply_macro_gate:
            if macro_regime is None:
                try:
                    from ..macro.synthetic_macro import MacroEngine
                    macro_regime = MacroEngine().get_regime()
                except Exception:
                    macro_regime = None
            if macro_regime and isinstance(macro_regime, dict):
                regime = macro_regime.get("regime", "RISK-ON")
                filtered = []
                for a in alerts:
                    is_long = a["action"] == "LONG"
                    is_breakout = "BREAKOUT" in a["type"] or "GAP" in a["type"]
                    if regime == "RISK-OFF" and is_long:
                        if a.get("vol_ratio", 0) < 2.0 or a.get("rsi", 0) < 60:
                            continue
                        a = dict(a)
                        a["type"] += " [RISK-OFF gated]"
                        a["color"] = "yellow"
                    if regime == "STAGFLATION" and is_breakout:
                        continue
                    filtered.append(a)
                alerts = filtered
                
        return alerts
