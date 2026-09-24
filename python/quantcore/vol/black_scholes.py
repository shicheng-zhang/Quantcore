import numpy as np
from scipy.stats import norm

class BlackScholes:
    @staticmethod
    def _validate_inputs(S, K, T, r, sigma):
        if S is None or K is None or T is None or r is None or sigma is None:
            raise ValueError("S, K, T, r, sigma must not be None")
        if S <= 0 or K <= 0:
            raise ValueError(f"S and K must be > 0 (got S={S}, K={K})")
        if sigma <= 0:
            raise ValueError(f"sigma must be > 0 (got {sigma})")
        # Clamp T to minimum 1 minute equivalent to avoid division by zero
        # but preserve original behaviour for expired options at intrinsic value.
        if T <= 0:
            T = 1.0 / (365.0 * 24.0 * 60.0)  # ~1 minute in years
        return float(T)

    @staticmethod
    def price(S, K, T, r, sigma, opt_type='call'):
        T = BlackScholes._validate_inputs(S, K, T, r, sigma)
        # Handle extremely small T via intrinsic value to avoid numerical overflow
        if T < 1e-7:
            if opt_type == 'call':
                return max(0.0, S - K * np.exp(-r * T))
            else:
                return max(0.0, K * np.exp(-r * T) - S)
        d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)
        if opt_type == 'call':
            return S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
        elif opt_type == 'put':
            return K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
        else:
            raise ValueError("opt_type must be 'call' or 'put'")

    @staticmethod
    def greeks(S, K, T, r, sigma, opt_type='call', theta_convention='calendar'):
        """
        Returns delta, gamma, vega, theta, rho.

        theta_convention: 'calendar' (365-day, market standard) or 'trading' (252-day).
        vega: returned as per 1.00 (100pt) vol; vega_1pct = vega/100 for 1% move.
        """
        T = BlackScholes._validate_inputs(S, K, T, r, sigma)
        if opt_type not in ('call', 'put'):
            raise ValueError("opt_type must be 'call' or 'put'")
        # For expired options, Greeks are discontinuous — return intrinsic deltas
        if T < 1e-7:
            if opt_type == 'call':
                delta = 1.0 if S > K else 0.0
            else:
                delta = -1.0 if S < K else 0.0
            return {"delta": delta, "gamma": 0.0, "vega": 0.0, "vega_1pct": 0.0, "theta": 0.0, "theta_trading": 0.0, "rho": 0.0}

        d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)

        delta = norm.cdf(d1) if opt_type == 'call' else norm.cdf(d1) - 1
        gamma = norm.pdf(d1) / (S * sigma * np.sqrt(T))
        # Standard market vega is per 1.00 vol (100%). Provide both conventions.
        vega_raw = S * norm.pdf(d1) * np.sqrt(T)
        vega_1pct = vega_raw / 100.0
        theta_raw = -(S * norm.pdf(d1) * sigma) / (2 * np.sqrt(T))
        if opt_type == 'call':
            theta_raw -= r * K * np.exp(-r * T) * norm.cdf(d2)
            rho_raw = K * T * np.exp(-r * T) * norm.cdf(d2)
        else:
            theta_raw += r * K * np.exp(-r * T) * norm.cdf(-d2)
            rho_raw = -K * T * np.exp(-r * T) * norm.cdf(-d2)
        # Rho per 1% rate change (market convention is per 1%)
        rho_1pct = rho_raw / 100.0

        # CONVENTION: Divide by 365 (calendar) vs 252 (trading). Provide both.
        theta_calendar = theta_raw / 365.0
        theta_trading = theta_raw / 252.0
        if theta_convention == 'trading':
            theta = theta_trading
        else:
            theta = theta_calendar

        return {
            "delta": delta,
            "gamma": gamma,
            "vega": vega_raw,
            "vega_1pct": vega_1pct,
            "theta": theta,
            "theta_calendar": theta_calendar,
            "theta_trading": theta_trading,
            "rho": rho_raw,
            "rho_1pct": rho_1pct,
        }

class VolSurface:
    @staticmethod
    def generate_surface(S, base_iv, r=0.05, seed=42):
        """
        Synthetic smile for educational visualization only.

        Model: IV = base_iv + 0.05*m + 0.10*m^2 + 0.02/days + N(0,0.01)
        where m = ln(S/K). Floor at 5%. This is NOT calibrated to market data.
        For production, replace with SVI/SSVI fitted to listed options via
        least-squares on bid-ask mid IVs.
        """
        if S <= 0 or base_iv <= 0:
            raise ValueError("S and base_iv must be > 0")
        rng = np.random.default_rng(seed)
        strikes = np.linspace(S * 0.8, S * 1.2, 15)
        expirations = np.array([7, 14, 30, 60, 90]) / 365.0

        z_matrix = []
        for T in expirations:
            row = []
            for K in strikes:
                moneyness = np.log(S / K)
                skew_premium = 0.05 * moneyness + 0.1 * (moneyness ** 2)
                term_premium = 0.02 * (1 / (T * 365))
                iv = base_iv + skew_premium + term_premium + rng.normal(0, 0.01)
                row.append(max(0.05, iv))
            z_matrix.append(row)

        return {
            "strikes": [round(k, 2) for k in strikes],
            "expirations_days": [7, 14, 30, 60, 90],
            "iv_matrix": [[round(v, 4) for v in row] for row in z_matrix],
            "model_note": "Synthetic smile (uncalibrated). Replace with SVI/SSVI for live trading.",
        }
