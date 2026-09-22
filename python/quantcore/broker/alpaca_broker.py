import requests
import json
import os
import logging

class AlpacaBroker:
    def __init__(self):
        # Never persist brokerage secrets in the working tree. Environment
        # variables are suitable for unattended local deployments; UI-provided
        # credentials remain in this process only.
        key_id = os.getenv("APCA_API_KEY_ID")
        secret_key = os.getenv("APCA_API_SECRET_KEY")
        self.creds = ({"key_id": key_id, "secret_key": secret_key,
                       "base_url": "https://paper-api.alpaca.markets"}
                      if key_id and secret_key else None)

    def save_creds(self, key_id, secret_key, base_url="https://paper-api.alpaca.markets"):
        if base_url != "https://paper-api.alpaca.markets":
            raise ValueError("Only Alpaca's paper-trading endpoint is permitted")
        creds = {"key_id": key_id, "secret_key": secret_key, "base_url": base_url}
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
                if status == "filled":
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
                if status in ["pending_new", "new", "accepted"]:
                    return {"status": "ACCEPTED", "order_id": data.get("id"), "broker_status": status}
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
        except Exception as e:
            logging.getLogger(__name__).warning("get_account failed: %s", e)
        return None
