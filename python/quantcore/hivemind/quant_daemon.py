import os
import sys
import time
import ctypes
import mmap
import numpy as np
import yfinance as yf
import json

class HiveMindState(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("sequence", ctypes.c_uint64),
        ("py_timestamp", ctypes.c_uint64),
        ("num_assets", ctypes.c_uint32),
        ("symbols", (ctypes.c_char * 16) * 20),
        ("target_weights", ctypes.c_double * 20),
        ("regime_vol", ctypes.c_double),
        ("cpp_timestamp", ctypes.c_uint64),
        ("portfolio_value", ctypes.c_double),
        ("total_slippage", ctypes.c_double),
        ("realized_pnl", ctypes.c_double),
        ("orders_sent", ctypes.c_uint32),
        ("orders_filled", ctypes.c_uint32),
    ]

def run_daemon():
    file_path = "data/hivemind.dat"
    state_size = ctypes.sizeof(HiveMindState)

    if not os.path.exists(file_path):
        with open(file_path, "wb") as f:
            f.write(b"\0" * state_size)

    fd = os.open(file_path, os.O_RDWR)
    mm = mmap.mmap(fd, state_size)
    bridge = HiveMindState.from_buffer(mm)

    universe = ["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD"]
    print("[QUANT DAEMON] Initialized. Bridge size:", state_size, "bytes")

    while True:
        try:
            print("[QUANT] Fetching market data & calculating risk...")
            vols = {}
            for sym in universe:
                df = yf.download(sym, period="1mo", interval="1d", progress=False)
                if not df.empty:
                    vols[sym] = df['Close'].pct_change().std()

            if len(vols) < 2:
                time.sleep(10)
                continue

            # Inverse Volatility Weighting (Fast proxy for HRP)
            inv_vol = {sym: 1.0/v for sym, v in vols.items() if v > 0}
            total_inv_vol = sum(inv_vol.values())
            weights = {sym: v/total_inv_vol for sym, v in inv_vol.items()}

            # Read C++ Feedback
            cpp_slip = bridge.total_slippage
            cpp_pnl = bridge.realized_pnl
            cpp_orders = bridge.orders_sent
            print(f"[QUANT] C++ Reality Check -> Slippage: ${cpp_slip:.2f} | Fills: {cpp_orders}")

            # Write to Bridge
            bridge.num_assets = len(weights)
            for i, (sym, w) in enumerate(weights.items()):
                bridge.symbols[i][:] = sym.encode('utf-8').ljust(16, b'\0')
                bridge.target_weights[i] = w

            bridge.regime_vol = np.mean(list(vols.values()))
            bridge.py_timestamp = int(time.time() * 1e9)
            bridge.sequence += 1

            # Write UI JSON
            ui_data = {
                "sequence": bridge.sequence,
                "assets": [sym.decode('utf-8').strip('\0') for sym in bridge.symbols[:bridge.num_assets]],
                "weights": [round(w, 4) for w in bridge.target_weights[:bridge.num_assets]],
                "regime_vol": round(bridge.regime_vol, 4),
                "cpp_slippage": round(bridge.total_slippage, 2),
                "cpp_pnl": round(bridge.realized_pnl, 2),
                "cpp_orders": bridge.orders_sent,
                "py_timestamp": bridge.py_timestamp,
                "cpp_timestamp": bridge.cpp_timestamp
            }
            with open("data/hivemind_ui.json", "w") as f:
                json.dump(ui_data, f)

            print(f"[QUANT] Weights dispatched: { {k: f'{v:.2%}' for k,v in weights.items()} }")

        except Exception as e:
            print(f"[QUANT] Error: {e}")

        time.sleep(15) # Rebalance every 15 seconds

if __name__ == "__main__":
    run_daemon()
