import random
class MacroEngine:
    """
    Synthetic macro regime for dashboard illustration only.
    Distributions: VIX ~ N(18,5) floor 10, 10Y ~ N(4.2,0.5), DXY ~ N(104,2).
    Thresholds (VIX 25, 10Y 5.0/3.5, DXY 102) are illustrative, not econometric.
    For live trading, replace with FRED API (VIXCLS, DGS10, DTWEXBGS) and
    a calibrated Markov-switching model.
    """
    def get_regime(self):
        vix = max(10, random.gauss(18, 5))
        us10y = random.gauss(4.2, 0.5)
        dxy = random.gauss(104, 2)

        if vix > 25 or us10y > 5.0: regime, color, rotation = "RISK-OFF", "red", "Rotate to Gold (GLD) & Cash"
        elif us10y < 3.5 and dxy < 102: regime, color, rotation = "STAGFLATION", "yellow", "Rotate to Commodities"
        else: regime, color, rotation = "RISK-ON", "green", "Maximize Equities & Crypto"

        return {"vix": round(vix, 2), "us10y": round(us10y, 2), "dxy": round(dxy, 2), "regime": regime, "color": color, "rotation": rotation, "model_note": "Synthetic — replace with FRED + regime model for live"}
