import numpy as np
from .paper_ledger import PaperLedger

class PaperBroker:
    def __init__(self, db_path=None):
        self.ledger = PaperLedger(db_path) if db_path else PaperLedger()
        # Deep Sim Mock Prices: Prevents yfinance network hangs and guarantees instant routing
        self.mock_prices = {
            "AAPL": 225.50, "MSFT": 420.10, "NVDA": 135.80, "TSLA": 245.00,
            "AMD": 165.20, "SPY": 555.00, "QQQ": 485.00, "IWM": 220.00,
            "GLD": 240.00, "TLT": 95.00, "BTC-USD": 65000.0, "ETH-USD": 3200.0,
            "SOL-USD": 145.00, "AVAX-USD": 35.00, "MU": 110.00, "SNDK": 45.00
        }

    def get_market_price(self, symbol):
        return self.mock_prices.get(symbol.upper(), 100.0)

    def submit_order(self, symbol, side, qty, algo, live_price=None):
        symbol = symbol.upper()
        side = side.upper()
        algo = algo.upper()
        if side not in {"BUY", "SELL"} or algo not in {"MARKET", "VWAP", "TWAP"}:
            return {"status": "REJECTED", "reason": "INVALID_ORDER"}
        if not isinstance(qty, (int, float)) or isinstance(qty, bool) or qty <= 0:
            return {"status": "REJECTED", "reason": "INVALID_QUANTITY"}
        if live_price is not None and live_price <= 0:
            return {"status": "REJECTED", "reason": "INVALID_PRICE"}
        price = live_price if live_price is not None else self.mock_prices.get(symbol.upper(), 100.0)

        # Simulate Almgren-Chriss Slippage based on Algo
        if algo == "MARKET":
            slip_bps = 12.5
            commission = 0.0
        elif algo == "VWAP":
            slip_bps = 1.8
            commission = qty * 0.005
        else:
            slip_bps = 5.0
            commission = 0.0

        if side == "BUY":
            fill_price = price * (1 + (slip_bps / 10000.0))
        else:
            fill_price = price * (1 - (slip_bps / 10000.0))

        state = self.ledger.get_state()
        if side == "BUY" and (qty * fill_price + commission) > state["cash"]:
            return {"status": "REJECTED", "reason": "INSUFFICIENT_BUYING_POWER"}
        if side == "SELL":
            held = next((position[1] for position in state["positions"] if position[0] == symbol), 0.0)
            if qty > held:
                return {"status": "REJECTED", "reason": "INSUFFICIENT_POSITION"}

        # ``fill_price`` already includes market impact.  Do not charge slippage
        # again inside the ledger or every trade is overstated by one spread.
        if not self.ledger.execute_fill(symbol, side, qty, fill_price, slip_bps, commission):
            return {"status": "REJECTED", "reason": "LEDGER_WRITE_FAILED"}

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
