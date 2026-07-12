import requests
import json
import os

class AlpacaBroker:
    def __init__(self):
        self.creds_file = "data/alpaca_creds.json"
        self.creds = self._load_creds()
        
    def _load_creds(self):
        if os.path.exists(self.creds_file):
            try:
                with open(self.creds_file, "r") as f:
                    return json.load(f)
            except: pass
        return None

    def save_creds(self, key_id, secret_key, base_url="https://paper-api.alpaca.markets"):
        creds = {"key_id": key_id, "secret_key": secret_key, "base_url": base_url}
        with open(self.creds_file, "w") as f:
            json.dump(creds, f)
        self.creds = creds

    def is_configured(self):
        return self.creds is not None and self.creds.get("key_id")

    def get_headers(self):
        return {
            "APCA-API-KEY-ID": self.creds["key_id"],
            "APCA-API-SECRET-KEY": self.creds["secret_key"]
        }

    def submit_order(self, symbol, side, qty, algo="MARKET"):
        if not self.is_configured():
            return {"status": "REJECTED", "reason": "ALPACA_NOT_CONFIGURED"}
            
        if "-USD" in symbol:
            return {"status": "REJECTED", "reason": "Alpaca Paper API currently configured for Equities. Crypto requires specific data vendor setup."}

        base_url = self.creds.get("base_url", "https://paper-api.alpaca.markets")
        url = f"{base_url}/v2/orders"
        
        payload = {
            "symbol": symbol,
            "qty": str(qty),
            "side": side.lower(),
            "type": "market",
            "time_in_force": "day"
        }
        
        try:
            res = requests.post(url, headers=self.get_headers(), json=payload, timeout=10)
            if res.status_code in [200, 201]:
                data = res.json()
                status = data.get("status", "pending_new")
                if status in ["filled", "pending_new", "new"]:
                    return {
                        "status": "FILLED",
                        "symbol": symbol,
                        "side": side,
                        "qty": qty,
                        "fill_price": float(data.get("filled_avg_price") or data.get("limit_price") or 0),
                        "slippage_bps": 0.0,
                        "commission": 0.0,
                        "theoretical_price": 0.0,
                        "order_id": data.get("id")
                    }
                else:
                    return {"status": "REJECTED", "reason": f"Alpaca status: {status}"}
            else:
                return {"status": "REJECTED", "reason": f"HTTP {res.status_code}: {res.text[:100]}"}
        except Exception as e:
            return {"status": "REJECTED", "reason": str(e)}

    def get_account(self):
        if not self.is_configured(): return None
        base_url = self.creds.get("base_url", "https://paper-api.alpaca.markets")
        try:
            res = requests.get(f"{base_url}/v2/account", headers=self.get_headers(), timeout=5)
            if res.status_code == 200:
                return res.json()
        except: pass
        return None
