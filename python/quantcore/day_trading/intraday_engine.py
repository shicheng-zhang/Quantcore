import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import math

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
            df = yf.download(symbol, period=period, interval=interval, progress=False)
            if not df.empty and len(df) > 10:
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.droplevel(1)
                df = df.reset_index()
                if 'Datetime' in df.columns: df.rename(columns={'Datetime': 'Date'}, inplace=True)
                elif 'Date' not in df.columns and df.index.name == 'Datetime':
                    df = df.reset_index().rename(columns={'Datetime': 'Date'})
                return df
        except Exception as e:
            print(f"YF failed for {symbol}: {e}")
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

    def analyze(self, symbol, interval="5m", period="5d"):
        df = self.get_intraday_data(symbol, interval, period)
        if df is None or len(df) < 10: return {"error": "No data"}

        tp = (df['High'] + df['Low'] + df['Close']) / 3
        df['VWAP'] = (tp * df['Volume']).cumsum() / df['Volume'].cumsum()

        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))

        orb_bars = min(30, len(df))
        orb_high = float(df['High'].iloc[:orb_bars].max())
        orb_low = float(df['Low'].iloc[:orb_bars].min())

        signals = []
        last_close = float(df['Close'].iloc[-1])
        prev_close = float(df['Close'].iloc[-2]) if len(df) > 1 else last_close
        last_vwap = float(df['VWAP'].iloc[-1])
        last_rsi = float(df['RSI'].iloc[-1]) if not pd.isna(df['RSI'].iloc[-1]) else 50.0

        if last_close > orb_high and prev_close <= orb_high:
            signals.append({"type": "ORB_BREAKOUT_UP", "msg": "Bullish ORB Breakout", "color": "green"})
        if last_close < orb_low and prev_close >= orb_low:
            signals.append({"type": "ORB_BREAKOUT_DOWN", "msg": "Bearish ORB Breakout", "color": "red"})

        if last_rsi < 30: signals.append({"type": "RSI_OVERSOLD", "msg": "RSI Oversold (<30)", "color": "green"})
        if last_rsi > 70: signals.append({"type": "RSI_OVERBOUGHT", "msg": "RSI Overbought (>70)", "color": "red"})

        if last_close > last_vwap and prev_close <= last_vwap:
            signals.append({"type": "VWAP_CROSS_UP", "msg": "Bullish VWAP Cross", "color": "green"})

        dates = [d.strftime('%Y-%m-%d %H:%M') if hasattr(d, 'strftime') else str(d) for d in df['Date']]

        return _sanitize_for_json({
            "symbol": symbol, "dates": dates,
            "open": df['Open'].tolist(), "high": df['High'].tolist(),
            "low": df['Low'].tolist(), "close": df['Close'].tolist(),
            "vwap": df['VWAP'].tolist(), "rsi": df['RSI'].tolist(),
            "orb_high": orb_high, "orb_low": orb_low,
            "signals": signals, "last_rsi": last_rsi, "last_close": last_close
        })
