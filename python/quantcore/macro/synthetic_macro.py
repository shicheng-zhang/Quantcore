import random
class MacroEngine:
    def get_regime(self):
        vix = max(10, random.gauss(18, 5))
        us10y = random.gauss(4.2, 0.5)
        dxy = random.gauss(104, 2)

        if vix > 25 or us10y > 5.0: regime, color, rotation = "RISK-OFF", "red", "Rotate to Gold (GLD) & Cash"
        elif us10y < 3.5 and dxy < 102: regime, color, rotation = "STAGFLATION", "yellow", "Rotate to Commodities"
        else: regime, color, rotation = "RISK-ON", "green", "Maximize Equities & Crypto"

        return {"vix": round(vix, 2), "us10y": round(us10y, 2), "dxy": round(dxy, 2), "regime": regime, "color": color, "rotation": rotation}
