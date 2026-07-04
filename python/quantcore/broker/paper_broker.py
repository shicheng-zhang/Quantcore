import yfinance as yf
import numpy as np
from .paper_ledger import PaperLedger

class PaperBroker:
    def __init__(self):
        self.ledger = PaperLedger()

    def get_market_price(self, symbol):
        try:
            # Fast fetch for current price
            tk = yf.Ticker(symbol)
            hist = tk.history(period="5d")
            if not hist.empty:
                return float(hist['Close'].iloc[-1])
        except: pass
        return 100.0 # Fallback

    def submit_order(self, symbol, side, qty, algo):
        symbol = symbol.upper()
        price = self.get_market_price(symbol)

        # Simulate Almgren-Chriss Slippage based on Algo
        if algo == "MARKET":
            slip_bps = 12.5 # Retail dump: 12.5 bps slippage
            commission = 0.0
        elif algo == "VWAP":
            slip_bps = 1.8  # Institutional slicing: 1.8 bps slippage
            commission = qty * 0.005 # $0.005 per share commission
        else:
            slip_bps = 5.0
            commission = 0.0

        # Apply slippage to fill price (adverse selection)
        if side == "BUY":
            fill_price = price * (1 + (slip_bps / 10000.0))
        else:
            fill_price = price * (1 - (slip_bps / 10000.0))

        # Pre-trade risk check (buying power)
        state = self.ledger.get_state()
        if side == "BUY" and (qty * fill_price) > state["cash"]:
            return {"status": "REJECTED", "reason": "INSUFFICIENT_BUYING_POWER"}

        # Execute
        self.ledger.execute_fill(symbol, side, qty, fill_price, slip_bps, commission)

        return {
            "status": "FILLED",
            "symbol": symbol,
            "side": side,
            "qty": qty,
            "fill_price": round(fill_price, 2),
            "slippage_bps": slip_bps,
            "commission": round(commission, 2),
            "theoretical_price": round(price, 2)
        }
