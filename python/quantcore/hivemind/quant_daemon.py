import os
import sys
import time
import ctypes
import mmap
import numpy as np
import pandas as pd
import yfinance as yf
from scipy import stats
from statsmodels.tsa.stattools import coint
import itertools
import json
import warnings
import pickle
from python.quantcore.nlp.sentiment import SentimentEngine
nlp_engine = SentimentEngine()
warnings.filterwarnings('ignore')

sys.stdout.reconfigure(line_buffering=True)
print("[DAEMON] Starting Unified Hive-Mind & StatArb Daemon...")

class HiveMindState(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("sequence", ctypes.c_uint64), ("py_timestamp", ctypes.c_uint64),
        ("num_assets", ctypes.c_uint32), ("symbols", (ctypes.c_char * 16) * 20),
        ("target_weights", ctypes.c_double * 20), ("regime_vol", ctypes.c_double),
        ("statarb_signal", ctypes.c_int8), ("statarb_hedge_ratio", ctypes.c_double),
        ("statarb_spread_z", ctypes.c_double), ("statarb_pair_s1", ctypes.c_char * 16),
        ("statarb_pair_s2", ctypes.c_char * 16), ("cpp_timestamp", ctypes.c_uint64),
        ("portfolio_value", ctypes.c_double), ("total_slippage", ctypes.c_double),
        ("realized_pnl", ctypes.c_double), ("orders_sent", ctypes.c_uint32), ("orders_filled", ctypes.c_uint32),
    ]

UNIVERSE = ["SPY", "IVV", "GLD", "IAU", "BTC-USD", "ETH-USD"]
CACHE_DIR = "data_cache"
os.makedirs(CACHE_DIR, exist_ok=True)

def fetch_pair_data(sym1, sym2, period="2y"):
    cache_file = os.path.join(CACHE_DIR, f"{sym1}_{sym2}.pkl")
    if os.path.exists(cache_file) and (time.time() - os.path.getmtime(cache_file) < 3600):
        with open(cache_file, "rb") as f:
            return pickle.load(f)

    print(f"  [DATA] Fetching {sym1} and {sym2}...")
    df = yf.download([sym1, sym2], period=period, interval="1d", progress=False, timeout=15)
    if isinstance(df.columns, pd.MultiIndex):
        close_df = df['Close']
    else:
        close_df = df[['Close']]
        close_df.columns = [sym1, sym2]
    if close_df.shape[1] < 2: raise ValueError("Missing")
    close_df = close_df.dropna()
    if len(close_df) < 50: raise ValueError("Not enough")
    y = close_df.iloc[:, 0].to_numpy(dtype=float).flatten()
    x = close_df.iloc[:, 1].to_numpy(dtype=float).flatten()
    with open(cache_file, "wb") as f:
        pickle.dump((y, x), f)
    return y, x

def scan_universe():
    print("[CRUCIBLE] Scanning universe...")
    pairs = list(itertools.combinations(UNIVERSE, 2))
    results = []
    for s1, s2 in pairs:
        try:
            y, x = fetch_pair_data(s1, s2)
            score, pvalue, _ = coint(y, x)
            if pvalue > 0.90: continue
            slope, intercept, _, _, _ = stats.linregress(x, y)
            spread = y - (slope * x + intercept)
            spread_lag = spread[:-1]
            spread_ret = spread[1:] - spread[:-1]
            hl_slope, _, _, _, _ = stats.linregress(spread_lag, spread_ret)
            if hl_slope >= 0: continue
            hl = -np.log(2) / hl_slope
            if hl > 200 or hl < 1: continue
            z_scores = (spread - np.mean(spread)) / np.std(spread)
            signal = np.where(z_scores > 0.5, -1, np.where(z_scores < -0.5, 1, 0))
            signal = signal[1:]
            strat_ret = signal * spread_ret
            sharpe = (np.mean(strat_ret) / np.std(strat_ret)) * np.sqrt(252) if np.std(strat_ret) > 0 else 0
            current_z = z_scores[-1]
            sig = -1 if current_z > 0.5 else (1 if current_z < -0.5 else 0)
            results.append({"pair": f"{s1}/{s2}", "s1": s1, "s2": s2, "pvalue": pvalue, "beta": slope, "half_life": hl, "cv_sharpe": sharpe, "current_z": current_z, "signal": sig})
        except Exception:
            pass
    results.sort(key=lambda x: x['cv_sharpe'], reverse=True)
    return results

def run_daemon():
    file_path = "data/hivemind.dat"
    state_size = ctypes.sizeof(HiveMindState)
    if not os.path.exists(file_path) or os.path.getsize(file_path) != state_size:
        with open(file_path, "wb") as f:
            f.write(b"\0" * state_size)
    fd = os.open(file_path, os.O_RDWR)
    mm = mmap.mmap(fd, state_size)
    bridge = HiveMindState.from_buffer(mm)
    
    print("[DAEMON] Bridge mapped. Entering continuous loop...")
    
    while True:
        try:
            results = scan_universe()
            if results:
                best_pair = results[0]
                print(f"[DAEMON] Best pair: {best_pair['pair']} | Z: {best_pair['current_z']:.2f}")
                
                # 1. Update StatArb Shared Memory
                
            # --- SATELLITE VETO CHECK ---
            veto_trade = False
            try:
                import json as _json
                if os.path.exists("data/satellite_feed.json"):
                    with open("data/satellite_feed.json", "r") as _f:
                        _feed = _json.load(_f)
                        _news = [x for x in _feed[:10] if x.get("type") == "NEWS_SENTIMENT"]
                        if _news:
                            _avg_sent = sum(x["sentiment_score"] for x in _news) / len(_news)
                            if best_pair['signal'] == 1 and _avg_sent < -0.5: veto_trade = True
                            if best_pair['signal'] == -1 and _avg_sent > 0.5: veto_trade = True
                            if veto_trade: print(f"[SATELLITE VETO] Blocked trade. Signal: {best_pair['signal']}, Sentiment: {_avg_sent:.2f}")
            except: pass

            if not veto_trade:
                
            # NLP VETO: Simulate checking a news feed
            # In production, this would query a real news API
            mock_news = "Market faces unexpected regulatory headwinds and macro uncertainty."
            sentiment = nlp_engine.analyze(mock_news)['sentiment']
            if sentiment < -0.5 and best_pair['signal'] == 1:
                print(f"[NLP VETO] Blocked LONG trade due to negative sentiment ({sentiment:.2f})")
                continue

                bridge.statarb_signal = best_pair['signal']
                bridge.statarb_hedge_ratio = best_pair['beta']
                bridge.statarb_spread_z = best_pair['current_z']
                
                # BULLETPROOF MEMORY COPY: Uses struct offsets to bypass ctypes property proxies
                s1_bytes = best_pair['s1'].encode('utf-8').ljust(16, b'\0')
                s2_bytes = best_pair['s2'].encode('utf-8').ljust(16, b'\0')
                
                base_addr = ctypes.addressof(bridge)
                ctypes.memmove(base_addr + HiveMindState.statarb_pair_s1.offset, s1_bytes, 16)
                ctypes.memmove(base_addr + HiveMindState.statarb_pair_s2.offset, s2_bytes, 16)
                
                # 2. Update General Portfolio Weights (50/50 allocation to the pair)
                bridge.num_assets = 2
                ctypes.memmove(base_addr + HiveMindState.symbols.offset, s1_bytes, 16)
                ctypes.memmove(base_addr + HiveMindState.symbols.offset + 16, s2_bytes, 16)
                bridge.target_weights[0] = 0.5
                bridge.target_weights[1] = 0.5
                bridge.regime_vol = 0.02 
                
                bridge.sequence += 1
                bridge.py_timestamp = int(time.time() * 1e9)
                
                # Read C++ Feedback
                cpp_slip = bridge.total_slippage
                cpp_pnl = bridge.realized_pnl
                cpp_orders = bridge.orders_sent
                
                # 3. Write StatArb UI JSON
                with open("data/stat_arb_ui.json", "w") as f:
                    json.dump({"top_pairs": results[:5], "active_pair": best_pair}, f, default=str)
                    
                # 4. Write Hive-Mind UI JSON (This lights up the Hive-Mind page!)
                with open("data/hivemind_ui.json", "w") as f:
                    json.dump({
                        "active": True,
                        "sequence": bridge.sequence,
                        "assets": [best_pair['s1'], best_pair['s2']],
                        "weights": [0.5, 0.5],
                        "regime_vol": bridge.regime_vol,
                        "cpp_slippage": cpp_slip,
                        "cpp_pnl": cpp_pnl,
                        "cpp_orders": cpp_orders,
                        "py_timestamp": bridge.py_timestamp,
                        "cpp_timestamp": bridge.cpp_timestamp
                    }, f)
            else:
                print("[DAEMON] No valid pairs found.")
        except Exception as e:
            print(f"[DAEMON] Error: {e}")
            
        time.sleep(10)

if __name__ == "__main__":
    run_daemon()
