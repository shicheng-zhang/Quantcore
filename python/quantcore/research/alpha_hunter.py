"""Alpha Hunter: Scans for Lead-Lag Information Flow anomalies."""
import yfinance as yf
import polars as pl
import numpy as np
from scipy import signal
import json
import os
from datetime import datetime
from fastapi import HTTPException

class AlphaHunter:
    def __init__(self):
        self.universe = [
            "BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "XRP-USD", 
            "ADA-USD", "DOGE-USD", "AVAX-USD", "DOT-USD", "LINK-USD"
        ]
        self.data_dir = "data/alpha_cache"
        os.makedirs(self.data_dir, exist_ok=True)

    def _normalize_date(self, df):
        """Safely strips timezone info to prevent Polars join collisions."""
        dtype = df.schema["Date"]
        if hasattr(dtype, "time_zone") and dtype.time_zone is not None:
            return df.with_columns(pl.col("Date").dt.convert_time_zone("UTC").dt.replace_time_zone(None))
        return df

    def fetch_universe(self):
        print(f"[ALPHA] Scanning universe: {len(self.universe)} assets...")
        frames = []
        
        for ticker in self.universe:
            try:
                # Use Ticker.history for guaranteed flat structure
                tk = yf.Ticker(ticker)
                df_pd = tk.history(period="1y", interval="1h")
                if df_pd.empty: continue
                
                df_pd = df_pd.reset_index()
                dt_col = 'Datetime' if 'Datetime' in df_pd.columns else 'Date'
                
                df = pl.from_pandas(df_pd).select([dt_col, "Close"]).rename({dt_col: "Date", "Close": ticker})
                df = self._normalize_date(df)
                frames.append(df)
            except Exception as e:
                print(f"Warning: Failed to fetch {ticker}: {e}")
        
        if not frames:
            return None
            
        master_df = frames[0]
        for df in frames[1:]:
            master_df = master_df.join(df, on="Date", how="outer_coalesce")
            
        master_df = master_df.sort("Date").fill_null(strategy="forward").drop_nulls()
        return master_df

    def compute_lead_lag_matrix(self, df: pl.DataFrame, max_lag: int = 24):
        returns_df = df.select(pl.all().exclude("Date").pct_change().fill_null(0))
        assets = returns_df.columns
        n_assets = len(assets)
        results = []
        
        data_np = returns_df.to_numpy()
        
        for i in range(n_assets):
            for j in range(n_assets):
                if i == j: continue
                
                x = data_np[:, i]
                y = data_np[:, j]
                
                correlation = signal.correlate(x, y, mode='full')
                norm_factor = np.sqrt(np.sum(x**2) * np.sum(y**2))
                if norm_factor > 0:
                    correlation = correlation / norm_factor
                else:
                    correlation = np.zeros_like(correlation)
                    
                zero_lag_idx = len(x) - 1
                start_idx = max(0, zero_lag_idx - max_lag)
                end_idx = min(len(correlation), zero_lag_idx + max_lag + 1)
                
                lag_window = correlation[start_idx:end_idx]
                lags = np.arange(start_idx - zero_lag_idx, end_idx - zero_lag_idx)
                
                if len(lag_window) == 0: continue
                
                best_idx = np.argmax(np.abs(lag_window))
                best_lag = lags[best_idx]
                best_corr = lag_window[best_idx]
                
                if abs(best_corr) > 0.3:
                    results.append({
                        "source": assets[i],
                        "target": assets[j],
                        "lag_hours": int(best_lag),
                        "correlation": float(round(best_corr, 3)),
                        "strength": float(round(abs(best_corr), 3))
                    })
                    
        return results

    def scan(self):
        df = self.fetch_universe()
        if df is None or df.shape[0] < 50:
            # Force a 500 error so the frontend catches it and alerts the user
            raise HTTPException(status_code=500, detail="Failed to fetch sufficient universe data from yfinance.")
            
        signals = self.compute_lead_lag_matrix(df)
        
        out_path = "data/alpha_signals.json"
        with open(out_path, "w") as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "signals": signals,
                "universe": [col for col in df.columns if col != "Date"]
            }, f)
            
        return {"status": "success", "signals_found": len(signals)}
