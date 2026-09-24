"""
The Alpha Crucible: Statistical Arbitrage & Purged Cross-Validation
"""
import sys
import numpy as np
import pandas as pd
import yfinance as yf
from scipy import stats
import itertools
import warnings
warnings.filterwarnings('ignore')

# Force line-buffering even if -u flag is missed
sys.stdout.reconfigure(line_buffering=True)

class StatArbCrucible:
    def __init__(self):
        self.universe = {
            "KO": "Coca-Cola",
            "PEP": "Pepsi",
            "MCD": "McDonalds",
            "WMT": "Walmart",
            "XOM": "Exxon",
            "CVX": "Chevron"
        }

    def fetch_pair_data(self, sym1, sym2, period="2y"):
        print(f"  [DATA] Fetching {sym1} and {sym2}...", flush=True)
        # CRITICAL FIX: yfinance requires a LIST for multiple tickers
        df = yf.download([sym1, sym2], period=period, interval="1d", progress=False)
        
        # Extract Close prices safely
        if isinstance(df.columns, pd.MultiIndex):
            close_df = df['Close']
        else:
            close_df = df[['Close']]
            close_df.columns = [sym1, sym2]
            
        close_df = close_df.dropna()
        if len(close_df) < 50:
            raise ValueError(f"Not enough data for {sym1}/{sym2}")
            
        return close_df[sym1], close_df[sym2]

    def calc_hedge_ratio(self, y, x):
        """
        OLS hedge ratio y = beta*x + alpha + e. Returns (beta, alpha).
        Spread must be constructed as y - beta*x - alpha, not y - beta*x.
        """
        slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)
        return slope, intercept

    def calc_half_life(self, spread):
        """
        OU half-life via regression d(spread) = lambda*spread_{t-1} + e.
        HL = -ln(2)/lambda. Returns 999 if lambda >= 0 (explosive/non-stationary).
        """
        spread_lag = spread.shift(1).dropna()
        spread_ret = spread.diff().dropna()
        # Align: spread_ret[1:] corresponds to spread_lag[1:]
        spread_lag = spread_lag.iloc[1:]
        spread_ret = spread_ret.iloc[1:]
        if len(spread_lag) < 10:
            return 999
        slope, intercept, _, _, _ = stats.linregress(spread_lag, spread_ret)
        if slope >= 0:
            return 999
        half_life = -np.log(2) / slope
        return float(np.clip(half_life, 1, 999))

    def calc_spread(self, y, x, beta=None, alpha=None):
        """Constructs the stationary spread y - beta*x - alpha."""
        if beta is None or alpha is None:
            beta, alpha = self.calc_hedge_ratio(y, x)
        return y - beta * x - alpha

    def coint_test(self, y, x, **kwargs):
        """
        Engle-Granger cointegration test wrapper.
        kwargs passed to stats.coint (e.g., trend='c', autolag=None).
        Uses no trend by default; caller can specify trend='ct' if needed.
        """
        return stats.coint(y, x, **kwargs)

    def purged_cross_validation(self, y, x, n_splits=5, embargo_pct=0.05, z_entry=2.0):
        """
        Purged Cross-Validation with embargo.

        Correctly constructs spreads as y - beta*x - alpha on both train and test.
        Beta/alpha are fit on train only to avoid look-ahead.
        Embargo window prevents leakage from overlapping formation periods.
        """
        n = len(y)
        if n < n_splits * 10:
            return 0.0
        fold_size = n // n_splits
        indices = np.arange(n)
        oos_sharpes = []

        for i in range(n_splits):
            test_start = i * fold_size
            test_end = (i + 1) * fold_size if i < n_splits - 1 else n
            test_idx = indices[test_start:test_end]
            embargo_window = int(fold_size * embargo_pct)
            train_idx = np.concatenate([
                indices[:max(0, test_start - embargo_window)],
                indices[min(n, test_end + embargo_window):]
            ])
            if len(train_idx) < 50:
                continue

            beta, alpha = self.calc_hedge_ratio(y.iloc[train_idx], x.iloc[train_idx])
            spread_train = y.iloc[train_idx] - beta * x.iloc[train_idx] - alpha
            mean_spread = spread_train.mean()
            std_spread = spread_train.std()
            if std_spread == 0 or not np.isfinite(std_spread):
                continue

            spread_test = y.iloc[test_idx] - beta * x.iloc[test_idx] - alpha
            z_score_test = (spread_test - mean_spread) / std_spread
            # Lag signal by 1 to avoid look-ahead: signal at t trades spread return at t+1
            signal = np.where(z_score_test > z_entry, -1, np.where(z_score_test < -z_entry, 1, 0))
            # Shift signal forward: yesterday's signal earns today's spread change
            signal_series = pd.Series(signal, index=spread_test.index)
            spread_ret = spread_test.diff().fillna(0)
            # Align: trade at next bar
            strat_ret = signal_series.shift(1).fillna(0) * spread_ret
            strat_ret = strat_ret.replace([np.inf, -np.inf], 0).dropna()

            if len(strat_ret) > 10 and strat_ret.std() > 1e-12:
                oos_sharpe = (strat_ret.mean() / strat_ret.std()) * np.sqrt(252)
                if np.isfinite(oos_sharpe):
                    oos_sharpes.append(oos_sharpe)

        return float(np.mean(oos_sharpes)) if oos_sharpes else 0.0

    def scan_universe(self):
        print("[CRUCIBLE] Scanning universe for cointegrated pairs...", flush=True)
        symbols = list(self.universe.keys())
        pairs = list(itertools.combinations(symbols, 2))
        results = []
        
        for s1, s2 in pairs:
            try:
                print(f"[CRUCIBLE] Testing pair: {s1} / {s2}", flush=True)
                y, x = self.fetch_pair_data(s1, s2)
                
                score, pvalue, _, _ = stats.coint(y, x)
                if pvalue > 0.05: 
                    print(f"  [REJECT] {s1}/{s2} not cointegrated (p={pvalue:.4f})", flush=True)
                    continue
                
                beta, intercept = self.calc_hedge_ratio(y, x)
                spread = y - beta * x - intercept

                hl = self.calc_half_life(spread)
                if hl > 60 or hl < 2:
                    print(f"  [REJECT] {s1}/{s2} half-life out of bounds ({hl:.1f}d)", flush=True)
                    continue

                print(f"  [CV] Running Purged Cross-Validation for {s1}/{s2}...", flush=True)
                cv_sharpe = self.purged_cross_validation(y, x)
                print(f"  [CV] Purged Sharpe: {cv_sharpe:.2f}", flush=True)

                current_z = (spread.iloc[-1] - spread.mean()) / spread.std() if spread.std() > 1e-12 else 0.0
                signal = 0
                if current_z > 2.0: signal = -1 
                elif current_z < -2.0: signal = 1 
                
                results.append({
                    "pair": f"{s1}/{s2}", "s1": s1, "s2": s2,
                    "pvalue": pvalue, "beta": beta, "alpha": intercept, "half_life": hl,
                    "cv_sharpe": cv_sharpe, "current_z": current_z, "signal": signal
                })
            except Exception as e:
                print(f"  [ERROR] {s1}/{s2} failed: {e}", flush=True)
                continue
                
        results.sort(key=lambda x: x['cv_sharpe'], reverse=True)
        return results
