import yfinance as yf
import pandas as pd
import numpy as np
import time

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
            df = yf.download(symbol, period="5d", interval=timeframe, progress=False)
            if df.empty: return None
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.droplevel(1)
            df = df.tail(lookback)
            self.cache[cache_key] = {'df': df, 'ts': now}
            return df
        except Exception:
            return None

    def calculate_rsi(self, series, window=14):
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    def calculate_atr(self, df, window=14):
        high_low = df['High'] - df['Low']
        high_close = np.abs(df['High'] - df['Close'].shift())
        low_close = np.abs(df['Low'] - df['Close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = np.max(ranges, axis=1)
        return true_range.rolling(window=window).mean().iloc[-1]

    def scan_universe(self, symbols):
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
            
            if pd.isna(rsi) or pd.isna(atr) or atr == 0 or pd.isna(vol_ma) or vol_ma == 0: continue

            # 1. Breakout Buy (Price > 20bar High + Volume Spike + RSI > 55)
            if current > high_20 and cur_vol > vol_ma * 1.3 and rsi > 55:
                alerts.append({
                    "symbol": sym, "type": "BREAKOUT BUY", "price": round(float(current), 2),
                    "level": round(float(high_20), 2), "rsi": round(float(rsi), 1), 
                    "atr": round(float(atr), 2), "vol_ratio": round(float(cur_vol/vol_ma), 1), 
                    "color": "green", "action": "LONG"
                })
            # 2. Breakdown Sell (Price < 20bar Low + Volume Spike + RSI < 45)
            elif current < low_20 and cur_vol > vol_ma * 1.3 and rsi < 45:
                alerts.append({
                    "symbol": sym, "type": "BREAKDOWN SELL", "price": round(float(current), 2),
                    "level": round(float(low_20), 2), "rsi": round(float(rsi), 1), 
                    "atr": round(float(atr), 2), "vol_ratio": round(float(cur_vol/vol_ma), 1), 
                    "color": "red", "action": "SHORT"
                })
            # 3. Mean Reversion Fade (Overextended RSI + Rejection Candle)
            elif rsi > 75 and current < prev:
                alerts.append({
                    "symbol": sym, "type": "FADE (OVERBOUGHT)", "price": round(float(current), 2),
                    "level": round(float(high_20), 2), "rsi": round(float(rsi), 1), 
                    "atr": round(float(atr), 2), "vol_ratio": round(float(cur_vol/vol_ma), 1), 
                    "color": "yellow", "action": "SHORT"
                })
            elif rsi < 25 and current > prev:
                alerts.append({
                    "symbol": sym, "type": "FADE (OVERSOLD)", "price": round(float(current), 2),
                    "level": round(float(low_20), 2), "rsi": round(float(rsi), 1), 
                    "atr": round(float(atr), 2), "vol_ratio": round(float(cur_vol/vol_ma), 1), 
                    "color": "yellow", "action": "LONG"
                })
                
        return alerts
