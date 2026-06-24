"""Institutional Vectorized Backtester."""
import polars as pl
import numpy as np
import yfinance as yf
import os
import json
from datetime import datetime

class Backtester:
    def __init__(self):
        self.data_dir = "data/raw/equities"

    def _normalize_date(self, df):
        """Safely strips timezone info to prevent Polars join collisions."""
        dtype = df.schema["Date"]
        if hasattr(dtype, "time_zone") and dtype.time_zone is not None:
            return df.with_columns(pl.col("Date").dt.convert_time_zone("UTC").dt.replace_time_zone(None))
        return df

    def _load_universe_data(self, universe: list):
        """Loads historical data for the selected universe."""
        frames = []
        valid_symbols = []

        for sym in universe:
            path = f"{self.data_dir}/{sym}.parquet"
            if os.path.exists(path):
                df = pl.read_parquet(path).select(["Date", "Close"]).rename({"Close": sym})
                df = self._normalize_date(df)
                frames.append(df)
                valid_symbols.append(sym)
            else:
                # Fallback: try to fetch it if it's missing from local cache
                try:
                    ticker = yf.Ticker(sym)
                    df_pd = ticker.history(period="2y")
                    if not df_pd.empty:
                        df = pl.from_pandas(df_pd.reset_index()).select(["Date", "Close"]).rename({"Close": sym})
                        df = self._normalize_date(df)
                        frames.append(df)
                        valid_symbols.append(sym)
                except: pass

        if not frames: return None, []

        # Outer join and forward fill missing days
        master = frames[0]
        for df in frames[1:]:
            master = master.join(df, on="Date", how="outer_coalesce").sort("Date").fill_null(strategy="forward")

        # Drop rows with remaining nulls at the start
        master = master.drop_nulls()
        return master, valid_symbols

    def run_cross_sectional_momentum(self, universe: list, lookback: int = 60, slippage_bps: float = 5.0):
        """
        Classic Wall Street Factor: Cross-Sectional Momentum.
        Ranks assets by trailing return. Longs top quartile, Shorts bottom quartile.
        """
        master_df, valid_symbols = self._load_universe_data(universe)
        if master_df is None or len(valid_symbols) < 2:
            return {"error": "Need at least 2 valid assets in universe to run cross-sectional backtest."}

        dates = master_df["Date"].to_list()
        prices = master_df.select(pl.all().exclude("Date")).to_numpy()
        n_days, n_assets = prices.shape

        # 1. Calculate Trailing Momentum Signal
        mom = np.full_like(prices, np.nan)
        if n_days > lookback:
            mom[lookback:] = prices[lookback:] / prices[:-lookback] - 1

        # 2. Calculate Daily Asset Returns
        daily_ret = np.full_like(prices, np.nan)
        daily_ret[1:] = prices[1:] / prices[:-1] - 1

        # 3. Generate Weights (Long/Short Portfolio)
        weights = np.zeros_like(prices)
        for i in range(lookback, n_days):
            row = mom[i]
            valid_idx = np.where(~np.isnan(row))[0]

            if len(valid_idx) >= 2:
                # Sort assets by momentum
                sorted_idx = valid_idx[np.argsort(row[valid_idx])]

                # Top 25% Long, Bottom 25% Short
                n_leg = max(1, len(valid_idx) // 4)

                short_assets = sorted_idx[:n_leg]
                long_assets = sorted_idx[-n_leg:]

                # Equal weight within legs
                weights[i, short_assets] = -1.0 / n_leg
                weights[i, long_assets] = 1.0 / n_leg

        # 4. Calculate Turnover (L1 norm of weight changes / 2)
        turnover = np.zeros(n_days)
        turnover[1:] = np.sum(np.abs(weights[1:] - weights[:-1]), axis=1) / 2

        # 5. Calculate Strategy Returns
        strat_ret = np.nansum(weights * daily_ret, axis=1)
        strat_ret = np.nan_to_num(strat_ret, nan=0.0)

        # 6. Apply Transaction Costs (Slippage)
        slippage_penalty = turnover * (slippage_bps / 10000.0)
        net_ret = strat_ret - slippage_penalty

        # 7. Calculate Equity Curve & Drawdown
        equity = np.cumprod(1 + net_ret)

        running_max = np.maximum.accumulate(equity)
        drawdown = (equity - running_max) / running_max

        # 8. Calculate Metrics
        total_return = (equity[-1] / equity[0]) - 1
        ann_factor = 252 / n_days
        cagr = (1 + total_return) ** ann_factor - 1

        vol = np.std(net_ret) * np.sqrt(252)
        sharpe = (cagr / vol) if vol > 0 else 0

        max_dd = np.min(drawdown)

        # Format for UI
        dates_str = [d.strftime('%Y-%m-%d') if hasattr(d, 'strftime') else str(d)[:10] for d in dates]

        return {
            "dates": dates_str,
            "equity": equity.tolist(),
            "drawdown": drawdown.tolist(),
            "metrics": {
                "total_return": round(total_return * 100, 2),
                "cagr": round(cagr * 100, 2),
                "sharpe": round(sharpe, 2),
                "max_dd": round(max_dd * 100, 2),
                "avg_daily_turnover": round(np.mean(turnover[lookback:]) * 100, 2)
            },
            "universe": valid_symbols
        }
