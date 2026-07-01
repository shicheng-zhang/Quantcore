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
        slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)
        return slope, intercept

    def calc_half_life(self, spread):
        spread_lag = spread.shift(1).dropna()
        spread_ret = spread.diff().dropna()
        spread_lag = spread_lag.iloc[1:]
        if len(spread_lag) < 10: return 999
        slope, intercept, _, _, _ = stats.linregress(spread_lag, spread_ret)
        if slope >= 0: return 999 
        half_life = -np.log(2) / slope
        return max(1, half_life)

    def purged_cross_validation(self, y, x, n_splits=5, embargo_pct=0.05):
        n = len(y)
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
            if len(train_idx) < 50: continue
            
            beta, _ = self.calc_hedge_ratio(y.iloc[train_idx], x.iloc[train_idx])
            spread_train = y.iloc[train_idx] - beta * x.iloc[train_idx]
            mean_spread = spread_train.mean()
            std_spread = spread_train.std()
            if std_spread == 0: continue
            
            spread_test = y.iloc[test_idx] - beta * x.iloc[test_idx]
            z_score_test = (spread_test - mean_spread) / std_spread
            signal = np.where(z_score_test > 2, -1, np.where(z_score_test < -2, 1, 0))
            spread_ret = spread_test.diff().fillna(0)
            strat_ret = signal * spread_ret
            strat_ret = strat_ret.replace([np.inf, -np.inf], 0).dropna()
            
            if len(strat_ret) > 10 and strat_ret.std() > 0:
                oos_sharpe = (strat_ret.mean() / strat_ret.std()) * np.sqrt(252)
                oos_sharpes.append(oos_sharpe)
                
        return np.mean(oos_sharpes) if oos_sharpes else 0.0

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
                spread = y - beta * x
                
                hl = self.calc_half_life(spread)
                if hl > 60 or hl < 2: 
                    print(f"  [REJECT] {s1}/{s2} half-life out of bounds ({hl:.1f}d)", flush=True)
                    continue
                
                print(f"  [CV] Running Purged Cross-Validation for {s1}/{s2}...", flush=True)
                cv_sharpe = self.purged_cross_validation(y, x)
                print(f"  [CV] Purged Sharpe: {cv_sharpe:.2f}", flush=True)
                
                current_z = (spread.iloc[-1] - spread.mean()) / spread.std()
                signal = 0
                if current_z > 2.0: signal = -1 
                elif current_z < -2.0: signal = 1 
                
                results.append({
                    "pair": f"{s1}/{s2}", "s1": s1, "s2": s2,
                    "pvalue": pvalue, "beta": beta, "half_life": hl,
                    "cv_sharpe": cv_sharpe, "current_z": current_z, "signal": signal
                })
            except Exception as e:
                print(f"  [ERROR] {s1}/{s2} failed: {e}", flush=True)
                continue
                
        results.sort(key=lambda x: x['cv_sharpe'], reverse=True)
        return results
