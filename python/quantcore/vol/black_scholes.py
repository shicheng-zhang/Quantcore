import numpy as np
from scipy.stats import norm

class BlackScholes:
    @staticmethod
    def price(S, K, T, r, sigma, opt_type='call'):
        if T <= 0: T = 0.0001
        d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)
        if opt_type == 'call':
            return S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
        return K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)

    @staticmethod
    def greeks(S, K, T, r, sigma, opt_type='call'):
        if T <= 0: T = 0.0001
        d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)

        delta = norm.cdf(d1) if opt_type == 'call' else norm.cdf(d1) - 1
        gamma = norm.pdf(d1) / (S * sigma * np.sqrt(T))
        vega = S * norm.pdf(d1) * np.sqrt(T) / 100 # 1% vol change
        theta = -(S * norm.pdf(d1) * sigma) / (2 * np.sqrt(T))
        if opt_type == 'call':
            theta -= r * K * np.exp(-r * T) * norm.cdf(d2)
        else:
            theta += r * K * np.exp(-r * T) * norm.cdf(-d2)
        theta /= 365 # Daily theta

        return {"delta": delta, "gamma": gamma, "vega": vega, "theta": theta}

class VolSurface:
    @staticmethod
    def generate_surface(S, base_iv, r=0.05):
        # Simulate the institutional "Volatility Smile/Skew"
        strikes = np.linspace(S * 0.8, S * 1.2, 15)
        expirations = np.array([7, 14, 30, 60, 90]) / 365.0

        z_matrix = []
        for T in expirations:
            row = []
            for K in strikes:
                # Skew: OTM Puts (low K) have higher IV than OTM Calls (high K)
                moneyness = np.log(S / K)
                skew_premium = 0.05 * moneyness + 0.1 * (moneyness ** 2)
                # Term structure: short dated options have higher vol (contango/backwardation)
                term_premium = 0.02 * (1 / (T * 365))
                iv = base_iv + skew_premium + term_premium + np.random.normal(0, 0.01)
                row.append(max(0.05, iv))
            z_matrix.append(row)

        return {
            "strikes": [round(k, 2) for k in strikes],
            "expirations_days": [7, 14, 30, 60, 90],
            "iv_matrix": [[round(v, 4) for v in row] for row in z_matrix]
        }
