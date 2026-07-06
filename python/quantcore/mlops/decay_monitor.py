import json
import os
import random
from datetime import datetime

class DecayMonitor:
    def __init__(self):
        self.state_file = "data/alpha_health.json"
        self.history_file = "data/alpha_history.json"

    def evaluate_models(self):
        models = [
            {"name": "StatArb: BTC-USD / ETH-USD", "type": "Cointegration", "base_half_life": 4.5, "base_p_value": 0.012, "base_sharpe": 1.8},
            {"name": "Cross-Sectional Momentum (60d)", "type": "Factor", "base_half_life": 12.0, "base_p_value": 0.045, "base_sharpe": 1.45},
            {"name": "Lead-Lag: SOL -> AVAX", "type": "Information Flow", "base_half_life": 2.1, "base_p_value": 0.008, "base_sharpe": 2.1}
        ]

        results = []
        history = {}
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, "r") as f: history = json.load(f)
            except: pass

        for m in models:
            # Simulate alpha decay: Half-life stretches, p-value degrades, Sharpe drops
            drift = random.uniform(0.1, 0.8)
            current_hl = m["base_half_life"] + drift + random.gauss(0, 0.5)
            current_p = m["base_p_value"] + (drift * 0.01) + random.gauss(0, 0.005)
            current_sr = m["base_sharpe"] - (drift * 0.2) + random.gauss(0, 0.1)

            status, color, quarantine = "HEALTHY", "green", False

            if m["type"] == "Cointegration":
                if current_hl > 10.0 or current_p > 0.05: status, color = "DECAYING", "yellow"
                if current_hl > 15.0 or current_p > 0.10: status, color, quarantine = "QUARANTINED", "red", True
            else:
                if current_sr < 1.0: status, color = "DECAYING", "yellow"
                if current_sr < 0.5: status, color, quarantine = "QUARANTINED", "red", True

            res = {
                "name": m["name"], "type": m["type"],
                "half_life": round(max(0.1, current_hl), 2),
                "p_value": round(max(0.001, min(1.0, current_p)), 4),
                "sharpe": round(max(-1.0, current_sr), 2),
                "status": status, "color": color, "quarantine": quarantine,
                "timestamp": datetime.now().isoformat()
            }
            results.append(res)

            if m["name"] not in history: history[m["name"]] = []
            history[m["name"]].append({"t": len(history[m["name"]]), "hl": res["half_life"], "sr": res["sharpe"]})
            history[m["name"]] = history[m["name"]][-50:]

        with open(self.state_file, "w") as f: json.dump(results, f)
        with open(self.history_file, "w") as f: json.dump(history, f)
        return results, history
