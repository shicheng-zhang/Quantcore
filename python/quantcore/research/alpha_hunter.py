"""Alpha Hunter: Scans for Lead-Lag Information Flow anomalies."""
import polars as pl
import numpy as np
from scipy import signal
from ..data.provider import fetch_ohlcv
import json
import os
from datetime import datetime
from fastapi import HTTPException
from ..logging_config import get_logger

logger = get_logger(__name__)

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

        # 1. Strip timezone if present
        if hasattr(dtype, "time_zone") and dtype.time_zone is not None:
            df = df.with_columns(pl.col("Date").dt.convert_time_zone("UTC").dt.replace_time_zone(None))

        # 2. CRITICAL FIX: Cast to uniform microsecond resolution to prevent ns vs ms join mismatches
        # This prevents outer_coalesce from failing silently and creating flatline nulls
        df = df.with_columns(pl.col("Date").cast(pl.Datetime("us")))

        # 3. Fallback: If it was read as a String from a corrupted parquet, force parse it
        if df.schema["Date"] != pl.Datetime("us"):
            try:
                df = df.with_columns(pl.col("Date").str.to_datetime(time_unit="us"))
            except Exception:
                pass

        return df
    def fetch_universe(self):
        logger.info(f"Scanning universe: {len(self.universe)} assets")
        frames = []
        
        for ticker in self.universe:
            try:
                # Use Ticker.history for guaranteed flat structure
                df_pd = fetch_ohlcv(ticker, period="1y", interval="1h")
                if df_pd.empty: continue
                
                df_pd = df_pd.reset_index()
                dt_col = 'Datetime' if 'Datetime' in df_pd.columns else 'Date'
                
                df = pl.from_pandas(df_pd).select([dt_col, "Close"]).rename({dt_col: "Date", "Close": ticker})
                df = self._normalize_date(df)
                frames.append(df)
            except Exception as e:
                logger.warning(f"Failed to fetch {ticker}: {e}")
        
        if not frames:
            return None
            
        master_df = frames[0]
        for df in frames[1:]:
            master_df = master_df.join(df, on="Date", how="outer_coalesce")
            
        master_df = master_df.sort("Date").fill_null(strategy="forward").drop_nulls()
        return master_df

    def compute_lead_lag_matrix(self, df: pl.DataFrame, max_lag: int = 24):
        """
        Correct Pearson cross-correlation at each lag k:
          r(k) = sum[(x_t - mu_x)(y_{t+k} - mu_y)] / sqrt(sum(x_t-mu_x)^2 * sum(y_{t+k}-mu_y)^2)
        Demeans returns at each lag window to avoid spurious correlation from non-zero means.
        """
        returns_df = df.select(pl.all().exclude("Date").pct_change().fill_null(0))
        assets = returns_df.columns
        n_assets = len(assets)
        results = []

        data_np = returns_df.to_numpy()
        n = data_np.shape[0]

        for i in range(n_assets):
            for j in range(n_assets):
                if i == j:
                    continue

                x = data_np[:, i]
                y = data_np[:, j]

                # Quick variance check — skip constant series
                if np.nanstd(x) < 1e-12 or np.nanstd(y) < 1e-12:
                    continue

                corrs = []
                lags_range = range(-max_lag, max_lag + 1)
                for lag in lags_range:
                    if lag < 0:
                        # y leads x: correlate x[ -lag:] with y[ : lag]
                        x_seg = x[-lag:]
                        y_seg = y[:lag]
                    elif lag > 0:
                        x_seg = x[:-lag] if lag < n else np.array([])
                        y_seg = y[lag:]
                    else:
                        x_seg = x
                        y_seg = y

                    if len(x_seg) < 10:
                        corrs.append(0.0)
                        continue

                    # Demeaned Pearson
                    x_m = x_seg - np.mean(x_seg)
                    y_m = y_seg - np.mean(y_seg)
                    denom = np.sqrt(np.sum(x_m ** 2) * np.sum(y_m ** 2))
                    if denom < 1e-12:
                        corrs.append(0.0)
                    else:
                        c = float(np.sum(x_m * y_m) / denom)
                        # Clip for numerical safety
                        corrs.append(float(np.clip(c, -1.0, 1.0)))

                corrs = np.array(corrs)
                lags = np.arange(-max_lag, max_lag + 1)

                if len(corrs) == 0:
                    continue

                best_idx = int(np.argmax(np.abs(corrs)))
                best_lag = int(lags[best_idx])
                best_corr = float(corrs[best_idx])

                # Require statistically meaningful correlation with minimum sample
                if abs(best_corr) > 0.3:
                    results.append({
                        "source": assets[i],
                        "target": assets[j],
                        "lag_hours": best_lag,
                        "correlation": round(best_corr, 3),
                        "strength": round(abs(best_corr), 3),
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
