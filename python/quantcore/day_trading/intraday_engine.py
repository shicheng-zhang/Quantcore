import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import math
from ..logging_config import get_logger
from ..data.provider import fetch_ohlcv
from ..macro.synthetic_macro import MacroEngine

logger = get_logger(__name__)

def apply_macro_filter(signals, macro_regime, last_rvol=1.0, last_rsi=50.0):
    """
    Macro -> Micro conditional bias gating.
    RISK-OFF:     only shorts + longs require RVOL>2.0 & RSI>60 (high conviction)
    STAGFLATION:  suppress breakouts, only VWAP reversion + fades
    RISK-ON:      allow all (default)
    Returns filtered signals + a gate note.
    """
    if not macro_regime:
        return signals, None
    regime = macro_regime.get("regime", "RISK-ON") if isinstance(macro_regime, dict) else str(macro_regime)
    filtered = []
    gate_note = None
    for s in signals:
        t = s.get("type", "")
        is_long = any(x in t for x in ["BREAKOUT_UP", "GAP_UP", "DELTA_CONFIRM_LONG", "VWAP_CROSS_UP", "RSI_OVERSOLD"])
        is_short = any(x in t for x in ["BREAKOUT_DOWN", "GAP_DOWN", "DELTA_CONFIRM_SHORT", "VWAP_CROSS_DOWN", "RSI_OVERBOUGHT"])
        is_breakout = "BREAKOUT" in t or "GAP" in t
        if regime == "RISK-OFF":
            if is_long:
                # Require high conviction for longs in risk-off
                if last_rvol < 2.0 or last_rsi < 60:
                    continue
                # Downgrade color to yellow
                s = dict(s)
                s["msg"] = s.get("msg", "") + " [RISK-OFF gated - high conviction only]"
                s["color"] = "yellow"
            filtered.append(s)
            gate_note = "RISK-OFF: longs gated (RVOL>2.0 & RSI>60 required)"
        elif regime == "STAGFLATION":
            if is_breakout:
                continue
            filtered.append(s)
            gate_note = "STAGFLATION: breakouts suppressed, reversion only"
        else:
            filtered.append(s)
    # If all longs were filtered, ensure at least a note
    return filtered, gate_note

def _sanitize_for_json(obj):
    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_sanitize_for_json(x) for x in obj]
    elif isinstance(obj, (float, np.floating)):
        if math.isnan(obj) or math.isinf(obj): return None
        return float(obj)
    elif isinstance(obj, (int, np.integer)):
        return int(obj)
    return obj

class IntradayEngine:
    def __init__(self):
        pass

    def get_intraday_data(self, symbol, interval="5m", period="5d"):
        try:
            df = fetch_ohlcv(symbol, period=period, interval=interval)
            if not df.empty and len(df) > 10:
                if 'Datetime' in df.columns and 'Date' not in df.columns:
                    df.rename(columns={'Datetime': 'Date'}, inplace=True)
                return df
        except Exception as e:
            logger.warning(f"Provider failed for {symbol}, using synthetic: {e}")
        return self._generate_synthetic(symbol, interval, period)

    def _generate_synthetic(self, symbol, interval, period):
        np.random.seed(hash(symbol) % 2**32)
        mins_per_day = 390
        days = 5 if "5d" in period else (2 if "2d" in period else 1)
        
        if interval == "1m": step_mins = 1
        elif interval == "5m": step_mins = 5
        elif interval == "15m": step_mins = 15
        elif interval == "30m": step_mins = 30
        elif interval == "1h": step_mins = 60
        else: step_mins = 5
        
        bars_per_day = mins_per_day // step_mins
        total_bars = bars_per_day * days
        
        base = 150.0 + np.random.randint(0, 100)
        prices = [base]
        trend = np.sin(np.linspace(0, 3 * np.pi, total_bars)) * (base * 0.05)
        
        for i in range(1, total_bars):
            noise = np.random.normal(0, base * 0.002)
            prices.append(prices[-1] + noise + (trend[i] - trend[i-1]))
            
        prices = np.array(prices)
        opens = prices
        closes = prices + np.random.normal(0, base * 0.001, total_bars)
        highs = np.maximum(opens, closes) + np.abs(np.random.normal(0, base * 0.002, total_bars))
        lows = np.minimum(opens, closes) - np.abs(np.random.normal(0, base * 0.002, total_bars))
        volumes = np.random.randint(1000, 5000, total_bars) * (1 + np.abs(np.sin(np.linspace(0, 2*np.pi*days, total_bars)))) 
        
        dates = []
        current_day = datetime.now().replace(hour=9, minute=30, second=0, microsecond=0) - timedelta(days=int(days * 1.5))
        
        while len(dates) < total_bars:
            if current_day.weekday() < 5: 
                day_start = current_day.replace(hour=9, minute=30)
                for m in range(bars_per_day):
                    if len(dates) >= total_bars: break
                    dates.append(day_start + timedelta(minutes=m * step_mins))
            current_day += timedelta(days=1)
            
        df = pd.DataFrame({
            'Date': dates[:total_bars], 'Open': opens, 'High': highs,
            'Low': lows, 'Close': closes, 'Volume': volumes
        })
        return df

    def analyze(self, symbol, interval="5m", period="5d", macro_regime=None, apply_macro_gate=True):
        df = self.get_intraday_data(symbol, interval, period)
        if df is None or len(df) < 10: return {"error": "No data"}
        # Auto-fetch macro regime if not supplied and gating enabled
        if apply_macro_gate and macro_regime is None:
            try:
                macro_regime = MacroEngine().get_regime()
            except Exception:
                macro_regime = None

        # VWAP must reset at the start of each trading session (daily reset).
        # A 5-day cumulative VWAP is meaningless to day traders.
        tp = (df['High'] + df['Low'] + df['Close']) / 3
        df['_tp_vol'] = tp * df['Volume']
        df['_date'] = pd.to_datetime(df['Date']).dt.date
        df['VWAP'] = df.groupby('_date')['_tp_vol'].cumsum() / df.groupby('_date')['Volume'].cumsum()
        df.drop(columns=['_tp_vol', '_date'], inplace=True)

        delta = df['Close'].diff()
        # Wilder's RSI: uses EMA with alpha=1/period (not SMA)
        gain = delta.where(delta > 0, 0).ewm(alpha=1/14, min_periods=14).mean()
        loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, min_periods=14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))

        # RVOL: relative volume at this time-of-day vs 20-bar avg (proxy for TOD curve)
        df['VOL_MA20'] = df['Volume'].rolling(20).mean()
        df['RVOL'] = df['Volume'] / df['VOL_MA20'].replace(0, 1e-9)
        df['RVOL'] = df['RVOL'].clip(0.1, 10.0).fillna(1.0)
        # Gap % per session: (open_today - close_yesterday) / close_yesterday
        try:
            df['_date_only'] = pd.to_datetime(df['Date']).dt.date
            daily_close = df.groupby('_date_only')['Close'].last()
            daily_open = df.groupby('_date_only')['Open'].first()
            gap_map = {}
            prev_close = None
            for d in sorted(daily_close.index):
                if prev_close is not None:
                    gap_map[d] = (daily_open[d] - prev_close) / prev_close * 100.0
                else:
                    gap_map[d] = 0.0
                prev_close = daily_close[d]
            df['GAP_PCT'] = df['_date_only'].map(gap_map).fillna(0.0)
            df.drop(columns=['_date_only'], inplace=True)
        except Exception:
            df['GAP_PCT'] = 0.0
        # Cumulative delta proxy (buy vs sell volume)
        df['DELTA_IMB'] = np.where(df['Close'] >= df['Open'], 1, -1) * df['Volume']
        df['CUM_DELTA'] = df.groupby(pd.to_datetime(df['Date']).dt.date)['DELTA_IMB'].cumsum() if 'Date' in df.columns else df['DELTA_IMB'].cumsum()
        # VWAP bands
        df['VWAP_STD'] = (df['Close'] - df['VWAP']).rolling(20).std().bfill().replace(0, 1e-9)
        df['VWAP_UP1'] = df['VWAP'] + df['VWAP_STD']
        df['VWAP_DN1'] = df['VWAP'] - df['VWAP_STD']
        df['VWAP_UP2'] = df['VWAP'] + 2 * df['VWAP_STD']
        df['VWAP_DN2'] = df['VWAP'] - 2 * df['VWAP_STD']
        # Parkinson / Garman-Klass intraday vol
        try:
            hl_ratio = np.log(df['High'] / df['Low'].replace(0, 1e-9))
            df['PARKINSON'] = np.sqrt((hl_ratio ** 2).rolling(20).mean() / (4 * np.log(2)))
        except Exception:
            df['PARKINSON'] = np.nan
        # Session anchored VWAP profile: POC per session
        try:
            last_date_vp = pd.to_datetime(df['Date']).dt.date.iloc[-1]
            today_slice = df[pd.to_datetime(df['Date']).dt.date == last_date_vp]
            if len(today_slice) >= 10:
                vp_prices = today_slice['Close'].to_numpy()
                vp_vols = today_slice['Volume'].to_numpy()
                # Simple 24-bin POC
                min_p, max_p = vp_prices.min(), vp_prices.max()
                if min_p != max_p:
                    bins = np.linspace(min_p, max_p, 25)
                    bin_vol = np.zeros(24)
                    idx = np.digitize(vp_prices, bins) - 1
                    for i, b in enumerate(idx):
                        b = min(23, max(0, b))
                        bin_vol[b] += vp_vols[i]
                    poc_idx = int(np.argmax(bin_vol))
                    poc_price = (bins[poc_idx] + bins[poc_idx + 1]) / 2
                else:
                    poc_price = float(min_p)
            else:
                poc_price = float(df['Close'].iloc[-1])
        except Exception:
            poc_price = float(df['Close'].iloc[-1] if len(df) else 100.0)

        # Opening Range Breakout: first N minutes of the session, not first N bars of 5-day history.
        # Derive ORB from the last trading day's first 30 minutes (6 bars at 5m, 30 bars at 1m, etc.)
        # Falls back to first 30 bars if Date grouping unavailable.
        try:
            last_date = pd.to_datetime(df['Date']).dt.date.iloc[-1]
            today_df = df[pd.to_datetime(df['Date']).dt.date == last_date]
            # Map interval to bars for 30 minutes
            interval_to_orb_bars = {"1m": 30, "5m": 6, "15m": 2, "30m": 1, "1h": 1}
            orb_needed = interval_to_orb_bars.get(interval, 6)
            orb_needed = min(orb_needed, len(today_df))
            if orb_needed >= 2:
                orb_high = float(today_df['High'].iloc[:orb_needed].max())
                orb_low = float(today_df['Low'].iloc[:orb_needed].min())
            else:
                orb_bars = min(30, len(df))
                orb_high = float(df['High'].iloc[:orb_bars].max())
                orb_low = float(df['Low'].iloc[:orb_bars].min())
        except Exception:
            orb_bars = min(30, len(df))
            orb_high = float(df['High'].iloc[:orb_bars].max())
            orb_low = float(df['Low'].iloc[:orb_bars].min())

        signals = []
        last_close = float(df['Close'].iloc[-1])
        prev_close = float(df['Close'].iloc[-2]) if len(df) > 1 else last_close
        last_vwap = float(df['VWAP'].iloc[-1])
        last_rsi = float(df['RSI'].iloc[-1]) if not pd.isna(df['RSI'].iloc[-1]) else 50.0
        last_rvol = float(df['RVOL'].iloc[-1]) if 'RVOL' in df.columns and not pd.isna(df['RVOL'].iloc[-1]) else 1.0
        last_gap = float(df['GAP_PCT'].iloc[-1]) if 'GAP_PCT' in df.columns else 0.0
        last_delta_imb = float((df['CUM_DELTA'].iloc[-1] / max(1, df['Volume'].tail(20).sum())) if 'CUM_DELTA' in df.columns else 0.0)
        # Normalize delta imbalance: signed volume / total volume over last 20 bars
        try:
            tail_vol = float(df['Volume'].tail(20).sum())
            tail_delta = float(df['DELTA_IMB'].tail(20).sum()) if 'DELTA_IMB' in df.columns else 0.0
            last_delta_imb = float(tail_delta / tail_vol) if tail_vol > 0 else 0.0
            last_delta_imb = float(max(-1.0, min(1.0, last_delta_imb)))
        except Exception:
            last_delta_imb = 0.0

        # RVOL-gated breakouts: require volume confirmation
        if last_close > orb_high and prev_close <= orb_high:
            if last_rvol >= 1.5:
                signals.append({"type": "ORB_BREAKOUT_UP", "msg": f"Bullish ORB Breakout (RVOL {last_rvol:.1f}x)", "color": "green", "rvol": last_rvol})
            else:
                signals.append({"type": "ORB_BREAKOUT_UP_WEAK", "msg": f"ORB Breakout but weak volume (RVOL {last_rvol:.1f}x) - caution", "color": "yellow", "rvol": last_rvol})
        if last_close < orb_low and prev_close >= orb_low:
            if last_rvol >= 1.5:
                signals.append({"type": "ORB_BREAKOUT_DOWN", "msg": f"Bearish ORB Breakout (RVOL {last_rvol:.1f}x)", "color": "red", "rvol": last_rvol})
            else:
                signals.append({"type": "ORB_BREAKOUT_DOWN_WEAK", "msg": f"ORB Breakdown weak volume (RVOL {last_rvol:.1f}x)", "color": "yellow", "rvol": last_rvol})

        if last_rsi < 30: signals.append({"type": "RSI_OVERSOLD", "msg": "RSI Oversold (<30)", "color": "green"})
        if last_rsi > 70: signals.append({"type": "RSI_OVERBOUGHT", "msg": "RSI Overbought (>70)", "color": "red"})

        if last_close > last_vwap and prev_close <= last_vwap:
            signals.append({"type": "VWAP_CROSS_UP", "msg": "Bullish VWAP Cross", "color": "green"})
        if last_close < last_vwap and prev_close >= last_vwap:
            signals.append({"type": "VWAP_CROSS_DOWN", "msg": "Bearish VWAP Cross", "color": "red"})

        # Gap + Drive
        if abs(last_gap) >= 1.0 and last_rvol >= 1.5:
            if last_gap > 0 and last_close > last_vwap:
                signals.append({"type": "GAP_UP_DRIVE", "msg": f"Gap Up {last_gap:.1f}% + Above VWAP (drive)", "color": "green", "gap": last_gap})
            elif last_gap < 0 and last_close < last_vwap:
                signals.append({"type": "GAP_DOWN_DRIVE", "msg": f"Gap Down {last_gap:.1f}% + Below VWAP (drive)", "color": "red", "gap": last_gap})

        # VWAP stretch / mean reversion (2σ)
        last_vwap_up2 = float(df['VWAP_UP2'].iloc[-1]) if 'VWAP_UP2' in df.columns else last_vwap * 1.02
        last_vwap_dn2 = float(df['VWAP_DN2'].iloc[-1]) if 'VWAP_DN2' in df.columns else last_vwap * 0.98
        if last_close > last_vwap_up2:
            signals.append({"type": "VWAP_STRETCH_UP", "msg": "Price > VWAP +2σ (stretched, mean-revert risk)", "color": "yellow"})
        if last_close < last_vwap_dn2:
            signals.append({"type": "VWAP_STRETCH_DOWN", "msg": "Price < VWAP -2σ (stretched)", "color": "yellow"})

        # Delta confirmation
        if last_delta_imb > 0.3 and last_close > last_vwap:
            signals.append({"type": "DELTA_CONFIRM_LONG", "msg": f"Delta confirms longs ({last_delta_imb:.2f})", "color": "green"})
        elif last_delta_imb < -0.3 and last_close < last_vwap:
            signals.append({"type": "DELTA_CONFIRM_SHORT", "msg": f"Delta confirms shorts ({last_delta_imb:.2f})", "color": "red"})

        # Macro gate: filter signals by regime
        macro_gate_note = None
        if apply_macro_gate:
            signals, macro_gate_note = apply_macro_filter(signals, macro_regime, last_rvol, last_rsi)

        dates = [d.strftime('%Y-%m-%d %H:%M') if hasattr(d, 'strftime') else str(d) for d in df['Date']]

        return _sanitize_for_json({
            "symbol": symbol, "dates": dates,
            "open": df['Open'].tolist(), "high": df['High'].tolist(),
            "low": df['Low'].tolist(), "close": df['Close'].tolist(),
            "vwap": df['VWAP'].tolist(), "rsi": df['RSI'].tolist(),
            "orb_high": orb_high, "orb_low": orb_low,
            "signals": signals, "last_rsi": last_rsi, "last_close": last_close,
            "last_rvol": last_rvol, "last_gap_pct": last_gap, "last_delta_imb": last_delta_imb,
            "poc": poc_price,
            "vwap_up1": float(df['VWAP_UP1'].iloc[-1]) if 'VWAP_UP1' in df.columns else None,
            "vwap_dn1": float(df['VWAP_DN1'].iloc[-1]) if 'VWAP_DN1' in df.columns else None,
            "vwap_up2": float(df['VWAP_UP2'].iloc[-1]) if 'VWAP_UP2' in df.columns else None,
            "vwap_dn2": float(df['VWAP_DN2'].iloc[-1]) if 'VWAP_DN2' in df.columns else None,
            "rvol_series": df['RVOL'].tolist() if 'RVOL' in df.columns else [],
            "gap_pct": last_gap,
            "macro_regime": macro_regime,
            "macro_gate_note": macro_gate_note,
        })
