import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from web.backend.analytics import AnalyticsEngine

starter = ["SPY", "QQQ", "IWM", "GLD", "TLT", "BTC-USD", "ETH-USD"]
engine = AnalyticsEngine()
existing = engine.get_symbols()

print("[SEED] Checking Cold Start Universe...")
for sym in starter:
    if sym not in existing:
        print(f"[SEED] Downloading {sym} max history...")
        try: 
            engine.add_symbol(sym)
        except Exception as e: 
            print(f"[SEED] Failed {sym}: {e}")
    else:
        print(f"[SEED] {sym} already cached.")
        
print("[SEED] Cold Start complete. The Backtester, HRP, and Alpha Hunter are now ready.")
