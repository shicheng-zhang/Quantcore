"""
Advanced Quantitative Prediction & Prediction Review Suite for QuantCore.

Provides:
  1. AdvancedPredictor: Multi-model ensemble forecasting (Ornstein-Uhlenbeck mean-reversion,
     momentum drift, regime-conditioned weighting, Monte Carlo probability cones, Bull/Base/Bear scenarios,
     Volume Profile POC/VAH/VAL, and actionable trade blueprints).
  2. PredictionReviewer: Walk-forward prediction accuracy audit, directional hit rate,
     MAE/RMSE tracking, calibration reliability score, historical forecast overlays, and hypothetical strategy equity.
  3. PredictionScreener: Cross-asset predictive ranking based on conviction and expected progression.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from scipy import stats

from ..logging_config import get_logger

logger = get_logger(__name__)


def _sanitize(obj: Any) -> Any:
    """Recursively replaces NaN/Inf with None or safe defaults for JSON."""
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_sanitize(x) for x in obj]
    elif isinstance(obj, (float, np.floating)):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return float(obj)
    elif isinstance(obj, (int, np.integer)):
        return int(obj)
    return obj


class AdvancedPredictor:
    """
    State-of-the-art quantitative predictive model combining:
      - Regime Identification (Hurst exponent, ADX, Bollinger/Keltner squeeze)
      - Ornstein-Uhlenbeck (OU) Mean-Reversion dynamics
      - Momentum & Volume-Weighted Drift
      - Support/Resistance & Volume Profile Liquidity Gravity
      - Monte Carlo (1,000 paths) probabilistic cone of future progression
    """

    @staticmethod
    def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        close = df["Close"].astype(float)
        high = df["High"].astype(float) if "High" in df else close
        low = df["Low"].astype(float) if "Low" in df else close
        vol = df["Volume"].astype(float) if "Volume" in df else pd.Series(1.0, index=df.index)

        # EMAs
        df["EMA_9"] = close.ewm(span=9, adjust=False).mean()
        df["EMA_21"] = close.ewm(span=21, adjust=False).mean()
        df["EMA_50"] = close.ewm(span=50, adjust=False).mean()

        # MACD
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        df["MACD"] = ema12 - ema26
        df["MACD_Signal"] = df["MACD"].ewm(span=9, adjust=False).mean()
        df["MACD_Hist"] = df["MACD"] - df["MACD_Signal"]

        # Wilder's RSI
        delta = close.diff()
        gain = delta.where(delta > 0, 0.0).ewm(alpha=1 / 14, min_periods=14).mean()
        loss = (-delta.where(delta < 0, 0.0)).ewm(alpha=1 / 14, min_periods=14).mean()
        rs = gain / loss.replace(0, 1e-9)
        df["RSI"] = 100 - (100 / (1 + rs))

        # ATR (14) — Wilder's RMA (exponentially smoothed, not SMA) to match trading standards
        tr1 = high - low
        tr2 = (high - close.shift()).abs()
        tr3 = (low - close.shift()).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        df["ATR"] = tr.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean().bfill()

        # Bollinger Bands (20, 2.0)
        sma20 = close.rolling(window=20).mean()
        std20 = close.rolling(window=20).std().replace(0, 1e-9)
        df["BB_Upper"] = sma20 + 2.0 * std20
        df["BB_Lower"] = sma20 - 2.0 * std20
        df["BB_Width"] = (df["BB_Upper"] - df["BB_Lower"]) / sma20
        df["BB_PctB"] = (close - df["BB_Lower"]) / (df["BB_Upper"] - df["BB_Lower"])

        # Keltner Channels (20, 1.5 * ATR)
        df["KC_Upper"] = df["EMA_21"] + 1.5 * df["ATR"]
        df["KC_Lower"] = df["EMA_21"] - 1.5 * df["ATR"]

        # TTM Squeeze Detection: BB inside KC
        df["TTM_Squeeze"] = (df["BB_Lower"] > df["KC_Lower"]) & (df["BB_Upper"] < df["KC_Upper"])

        # Session-aware or rolling VWAP
        tp = (high + low + close) / 3.0
        if "Date" in df.columns:
            date_col = pd.to_datetime(df["Date"]).dt.date
            df["VWAP"] = (tp * vol).groupby(date_col).cumsum() / vol.groupby(date_col).cumsum().replace(0, 1e-9)
        else:
            df["VWAP"] = (tp * vol).cumsum() / vol.cumsum().replace(0, 1e-9)

        df["VWAP_Std"] = (close - df["VWAP"]).rolling(20).std().bfill().replace(0, 1e-9)
        df["VWAP_Upper_1"] = df["VWAP"] + df["VWAP_Std"]
        df["VWAP_Lower_1"] = df["VWAP"] - df["VWAP_Std"]
        df["VWAP_Upper_2"] = df["VWAP"] + 2.0 * df["VWAP_Std"]
        df["VWAP_Lower_2"] = df["VWAP"] - 2.0 * df["VWAP_Std"]

        return df

    @staticmethod
    def estimate_hurst_exponent(prices: np.ndarray, max_lags: int = 20) -> float:
        """Estimates the Hurst exponent H:
        H < 0.45: Mean-Reverting
        0.45 <= H <= 0.55: Random Walk / Geometric Brownian Motion
        H > 0.55: Persistent Trending
        """
        if len(prices) < max_lags * 2:
            return 0.50
        lags = range(2, max_lags)
        tau = []
        for lag in lags:
            diff = prices[lag:] - prices[:-lag]
            std_diff = np.std(diff)
            tau.append(std_diff if std_diff > 1e-9 else 1e-9)
        try:
            poly = np.polyfit(np.log(list(lags)), np.log(tau), 1)
            hurst = float(np.clip(poly[0], 0.05, 0.95))
            return hurst
        except Exception:
            return 0.50

    @staticmethod
    def estimate_ornstein_uhlenbeck(prices: np.ndarray) -> Tuple[float, float, float]:
        """
        Fits an Ornstein-Uhlenbeck mean-reversion process:
          dP = theta * (mu - P) dt + sigma * dW
        Returns (theta, mu, sigma).
        """
        if len(prices) < 15:
            mean_p = float(np.mean(prices)) if len(prices) > 0 else 100.0
            return 0.05, mean_p, 0.01

        y = prices[1:] - prices[:-1]
        x = prices[:-1]
        slope, intercept, _, _, _ = stats.linregress(x, y)

        if slope >= 0:  # Not mean reverting
            theta = 0.02
            mu = float(np.mean(prices))
        else:
            theta = float(min(1.5, max(0.01, -slope)))
            mu = float(intercept / -slope) if -slope > 1e-8 else float(np.mean(prices))

        residuals = y - (intercept + slope * x)
        sigma = float(max(1e-4, np.std(residuals)))
        return theta, mu, sigma

    @staticmethod
    def compute_volume_profile(prices: np.ndarray, volumes: np.ndarray, bins: int = 24) -> Dict[str, Any]:
        """Computes Volume Profile: Point of Control (POC), Value Area High (VAH), Value Area Low (VAL)."""
        if len(prices) == 0 or len(volumes) == 0:
            return {"poc": 0.0, "vah": 0.0, "val": 0.0, "profile": []}

        min_p = np.min(prices)
        max_p = np.max(prices)
        if min_p == max_p:
            return {"poc": float(min_p), "vah": float(min_p), "val": float(min_p), "profile": []}

        price_bins = np.linspace(min_p, max_p, bins + 1)
        bin_vols = np.zeros(bins)

        bin_indices = np.digitize(prices, price_bins) - 1
        for i, b_idx in enumerate(bin_indices):
            idx = min(bins - 1, max(0, b_idx))
            bin_vols[idx] += volumes[i]

        poc_idx = int(np.argmax(bin_vols))
        poc = (price_bins[poc_idx] + price_bins[poc_idx + 1]) / 2.0

        # Value Area (70% of total volume around POC)
        total_v = np.sum(bin_vols)
        target_v = total_v * 0.70
        accum_v = bin_vols[poc_idx]
        left_idx = poc_idx
        right_idx = poc_idx

        while accum_v < target_v and (left_idx > 0 or right_idx < bins - 1):
            next_left_vol = bin_vols[left_idx - 1] if left_idx > 0 else -1
            next_right_vol = bin_vols[right_idx + 1] if right_idx < bins - 1 else -1

            if next_left_vol >= next_right_vol and left_idx > 0:
                left_idx -= 1
                accum_v += next_left_vol
            elif right_idx < bins - 1:
                right_idx += 1
                accum_v += next_right_vol
            elif left_idx > 0:
                left_idx -= 1
                accum_v += next_left_vol
            else:
                break

        val = (price_bins[left_idx] + price_bins[left_idx + 1]) / 2.0
        vah = (price_bins[right_idx] + price_bins[right_idx + 1]) / 2.0

        profile = []
        for b in range(bins):
            profile.append({
                "price": round(float((price_bins[b] + price_bins[b + 1]) / 2.0), 2),
                "volume": round(float(bin_vols[b]), 1),
                "is_poc": b == poc_idx,
                "in_value_area": left_idx <= b <= right_idx,
            })

        return {
            "poc": round(float(poc), 2),
            "vah": round(float(vah), 2),
            "val": round(float(val), 2),
            "profile": profile,
        }

    @staticmethod
    def compute_barrier_hit_prob(S0: float, B: float, T: float, mu: float, sigma: float) -> float:
        """Closed-form analytical first-passage probability for Geometric Brownian Motion."""
        if S0 <= 0 or B <= 0 or T <= 0 or sigma <= 1e-6:
            return 0.0
        b = math.log(B / S0)
        mu_prime = mu - 0.5 * (sigma ** 2)
        vol_sqrt_t = sigma * math.sqrt(T)
        if vol_sqrt_t <= 1e-9:
            return 0.0

        if B > S0:
            term1 = stats.norm.cdf((-b + mu_prime * T) / vol_sqrt_t)
            power = np.clip(2.0 * b * mu_prime / (sigma ** 2), -60.0, 60.0)
            term2 = math.exp(power) * stats.norm.cdf((-b - mu_prime * T) / vol_sqrt_t)
            prob = float(term1 + term2)
        else:
            term1 = stats.norm.cdf((b - mu_prime * T) / vol_sqrt_t)
            power = np.clip(2.0 * b * mu_prime / (sigma ** 2), -60.0, 60.0)
            term2 = math.exp(power) * stats.norm.cdf((b + mu_prime * T) / vol_sqrt_t)
            prob = float(term1 + term2)

        return float(np.clip(prob, 0.0, 1.0))

    @staticmethod
    def compute_terminal_prob(S0: float, B: float, T: float, mu: float, sigma: float) -> float:
        """Closed-form terminal probability P(S_T >= B) for B > S0 or P(S_T <= B) for B < S0."""
        if S0 <= 0 or B <= 0 or T <= 0 or sigma <= 1e-6:
            return 0.0
        b = math.log(B / S0)
        mu_prime = mu - 0.5 * (sigma ** 2)
        vol_sqrt_t = sigma * math.sqrt(T)
        if vol_sqrt_t <= 1e-9:
            return 0.0
        if B > S0:
            return float(stats.norm.cdf((-b + mu_prime * T) / vol_sqrt_t))
        else:
            return float(stats.norm.cdf((b - mu_prime * T) / vol_sqrt_t))

    @staticmethod
    def simulate_jump_diffusion_paths(
        S0: float,
        T_years: float,
        steps: int,
        mu: float,
        sigma: float,
        num_paths: int = 1000,
        gravity_target: Optional[float] = None,
        theta: float = 0.0,
        seed: int = 42,
    ) -> np.ndarray:
        """Simulates paths incorporating momentum drift, OU mean reversion, diffusion, and Poisson jumps."""
        np.random.seed(seed)
        dt = T_years / float(steps)
        paths = np.zeros((num_paths, steps + 1), dtype=float)
        paths[:, 0] = S0

        lambda_jump = 2.5
        jump_std = max(0.04, sigma * 0.25)

        for t in range(1, steps + 1):
            z = np.random.normal(0, 1, num_paths)
            jumps = np.random.poisson(lambda_jump * dt, num_paths) * np.random.normal(0, jump_std, num_paths)

            # Correct OU drift for log-price: mr_drift = theta*(log(gravity) - log(P))
            # Convert to return space: d log P = theta*(log(gravity/P)) dt
            mr_drift = 0.0
            if gravity_target is not None and theta > 0 and gravity_target > 1e-6:
                # Log-distance reversion: dimensionless, no division by price level
                mr_drift = theta * np.log(np.maximum(gravity_target, 1e-6) / np.maximum(paths[:, t - 1], 1e-6))

            drift_term = (mu + mr_drift - 0.5 * (sigma ** 2)) * dt
            diffusion = sigma * math.sqrt(dt) * z
            paths[:, t] = paths[:, t - 1] * np.exp(np.clip(drift_term + diffusion + jumps, -0.7, 0.7))
            paths[:, t] = np.maximum(paths[:, t], S0 * 0.05)

        return paths

    @classmethod
    def compute_threshold_confidences(
        cls,
        current_price: float,
        volatility_daily: float,
        effective_drift: float,
        gravity_target: float,
        theta: float,
        is_crypto: bool = False,
        num_simulations: int = 1000,
    ) -> Dict[str, Any]:
        """
        Computes aggregate and multi-tier probabilities for price increases and decreases of:
        5%, 10%, 15%, 20%, 25%, 40%, and 50%.
        Evaluates both Intraday Session (15 Hours) and Extended Swing (30 Days) horizons.
        """
        thresholds = [5, 10, 15, 20, 25, 40, 50]
        S0 = current_price
        sigma = max(0.05, float(volatility_daily))
        mu = float(effective_drift)

        # 1. 15-Hour Intraday Horizon
        hours_year = 8760.0 if is_crypto else 1638.0
        T_15h = 15.0 / hours_year
        paths_15h = cls.simulate_jump_diffusion_paths(
            S0, T_15h, steps=15, mu=mu, sigma=sigma, num_paths=num_simulations,
            gravity_target=gravity_target, theta=theta * 0.5, seed=42
        )

        # 2. 30-Day Extended Horizon
        days_year = 365.0 if is_crypto else 252.0
        T_30d = 30.0 / days_year
        paths_30d = cls.simulate_jump_diffusion_paths(
            S0, T_30d, steps=30, mu=mu, sigma=sigma, num_paths=num_simulations,
            gravity_target=gravity_target, theta=theta, seed=43
        )

        def build_horizon_tiers(paths, T_years, steps, time_unit, multiplier):
            tiers = []
            tot_weight = 0.0
            weighted_up = 0.0
            weighted_dn = 0.0

            max_p = np.max(paths, axis=1)
            min_p = np.min(paths, axis=1)
            end_p = paths[:, -1]

            for pct in thresholds:
                t_up = round(S0 * (1.0 + pct / 100.0), 2)
                t_dn = round(S0 * (1.0 - pct / 100.0), 2)

                emp_touch_up = float(np.mean(max_p >= t_up) * 100.0)
                emp_touch_dn = float(np.mean(min_p <= t_dn) * 100.0)
                emp_term_up = float(np.mean(end_p >= t_up) * 100.0)
                emp_term_dn = float(np.mean(end_p <= t_dn) * 100.0)

                ana_touch_up = cls.compute_barrier_hit_prob(S0, t_up, T_years, mu, sigma) * 100.0
                ana_touch_dn = cls.compute_barrier_hit_prob(S0, t_dn, T_years, mu, sigma) * 100.0
                ana_term_up = cls.compute_terminal_prob(S0, t_up, T_years, mu, sigma) * 100.0
                ana_term_dn = cls.compute_terminal_prob(S0, t_dn, T_years, mu, sigma) * 100.0

                touch_up = round(0.60 * emp_touch_up + 0.40 * ana_touch_up, 2)
                touch_dn = round(0.60 * emp_touch_dn + 0.40 * ana_touch_dn, 2)
                term_up = round(0.60 * emp_term_up + 0.40 * ana_term_up, 2)
                term_dn = round(0.60 * emp_term_dn + 0.40 * ana_term_dn, 2)

                # Velocity
                hit_up = np.where(paths >= t_up)
                if len(hit_up[0]) > 0:
                    first_steps = [hit_up[1][hit_up[0] == p][0] for p in np.unique(hit_up[0])]
                    med_up = float(np.median(first_steps)) * (multiplier / steps)
                    vel_up = f"{max(0.5, med_up):.1f} {time_unit}"
                else:
                    vel_up = "Rare / Tail"

                hit_dn = np.where(paths <= t_dn)
                if len(hit_dn[0]) > 0:
                    first_steps_dn = [hit_dn[1][hit_dn[0] == p][0] for p in np.unique(hit_dn[0])]
                    med_dn = float(np.median(first_steps_dn)) * (multiplier / steps)
                    vel_dn = f"{max(0.5, med_dn):.1f} {time_unit}"
                else:
                    vel_dn = "Rare / Tail"

                odds_up = f"1 in {round(100.0 / max(0.01, touch_up), 1)}" if touch_up >= 0.05 else "> 1 in 2000"
                odds_dn = f"1 in {round(100.0 / max(0.01, touch_dn), 1)}" if touch_dn >= 0.05 else "> 1 in 2000"

                skew = round(touch_up / max(0.05, touch_dn), 2)
                if skew >= 1.25:
                    adv = "BULLISH_EDGE"
                elif skew <= 0.80:
                    adv = "BEARISH_EDGE"
                else:
                    adv = "BALANCED"

                w = 1.0 / (1.0 + pct * 0.05)
                tot_weight += w
                weighted_up += touch_up * w
                weighted_dn += touch_dn * w

                tiers.append({
                    "threshold_pct": pct,
                    "target_price_up": t_up,
                    "target_price_down": t_dn,
                    "prob_touch_up": touch_up,
                    "prob_touch_down": touch_dn,
                    "prob_terminal_up": term_up,
                    "prob_terminal_down": term_dn,
                    "velocity_up": vel_up,
                    "velocity_down": vel_dn,
                    "odds_up": odds_up,
                    "odds_down": odds_dn,
                    "skew_ratio": skew,
                    "directional_advantage": adv,
                })

            agg_up = round(weighted_up / max(1e-6, tot_weight), 1)
            agg_dn = round(weighted_dn / max(1e-6, tot_weight), 1)
            net_ratio = round(agg_up / max(0.1, agg_dn), 2)

            return {
                "aggregate_upside_prob": agg_up,
                "aggregate_downside_prob": agg_dn,
                "net_skew_ratio": net_ratio,
                "tiers": tiers,
            }

        short_horizon = build_horizon_tiers(paths_15h, T_15h, 15, "hours", 15.0)
        short_horizon["horizon_label"] = "Intraday Session (15 Hours)"
        short_horizon["time_unit"] = "hours"

        ext_horizon = build_horizon_tiers(paths_30d, T_30d, 30, "days", 30.0)
        ext_horizon["horizon_label"] = "Extended Swing (30 Days)"
        ext_horizon["time_unit"] = "days"

        ext_up = ext_horizon["aggregate_upside_prob"]
        ext_dn = ext_horizon["aggregate_downside_prob"]
        net_ratio = ext_horizon["net_skew_ratio"]

        if net_ratio >= 1.20:
            net_bias = "BULLISH_CONVEXITY"
            edge_summary = f"Favorable {net_ratio}x upside probability dominance across key threshold tiers."
        elif net_ratio <= 0.83:
            net_bias = "BEARISH_EXPOSURE"
            edge_summary = f"Downside asymmetry dominant with {round(1.0/max(0.01, net_ratio), 2)}x downside risk exposure."
        else:
            net_bias = "SYMMETRIC_DISTRIBUTION"
            edge_summary = "Two-sided balanced probability distribution between upside and downside moves."

        best_tier_pct = 5
        max_divergence = -1.0
        for t in ext_horizon["tiers"]:
            div = abs(t["prob_touch_up"] - t["prob_touch_down"])
            if div > max_divergence:
                max_divergence = div
                best_tier_pct = t["threshold_pct"]

        best_tier_str = f"+{best_tier_pct}%" if net_ratio >= 1.0 else f"-{best_tier_pct}%"

        return {
            "summary": {
                "net_bias": net_bias,
                "net_skew_ratio": net_ratio,
                "aggregate_upside_score": ext_up,
                "aggregate_downside_score": ext_dn,
                "highest_conviction_tier": best_tier_str,
                "edge_summary": edge_summary,
            },
            "horizons": {
                "short_term_15h": short_horizon,
                "extended_30d": ext_horizon,
            }
        }

    @classmethod
    def compute_timeframe_snapshots(
        cls,
        current_price: float,
        volatility_daily: float,
        effective_drift: float,
        gravity_target: float,
        theta: float,
        vprofile: Dict[str, Any],
        key_levels: Dict[str, Any],
        hurst: float,
        is_squeeze: bool,
        is_crypto: bool = False,
        num_simulations: int = 1000,
    ) -> Dict[str, Any]:
        """
        Computes dynamic snapshots across 5 distinct session timeframes:
          - 0-5 hrs (Opening Surge / Initial Momentum)
          - 5-10 hrs (Mid-Session / Progression)
          - 10-15 hrs (Late Session / Overnight Carry)
          - 0-10 hrs (Primary Expansion Wave)
          - 5-15 hrs (Secondary / Carry Wave)
        """
        S0 = current_price
        sigma = max(0.05, float(volatility_daily))
        mu = float(effective_drift)
        hours_year = 8760.0 if is_crypto else 1638.0
        T_15h = 15.0 / hours_year
        steps = 15

        paths = cls.simulate_jump_diffusion_paths(
            S0, T_15h, steps=steps, mu=mu, sigma=sigma, num_paths=num_simulations,
            gravity_target=gravity_target, theta=theta * 0.6, seed=44
        )

        windows_config = [
            ("0-5 hrs", 0, 5, "0 - 5 Hours (Opening Surge / Impulse)"),
            ("5-10 hrs", 5, 10, "5 - 10 Hours (Mid-Session / Continuation)"),
            ("10-15 hrs", 10, 15, "10 - 15 Hours (Late Session / Overnight Carry)"),
            ("0-10 hrs", 0, 10, "0 - 10 Hours (Primary Expansion Wave)"),
            ("5-15 hrs", 5, 15, "5 - 15 Hours (Secondary / Carry Wave)"),
        ]

        test_levels = [
            ("POC Gravity", vprofile.get("poc", S0)),
            ("Value Area High (VAH)", vprofile.get("vah", S0 * 1.02)),
            ("Value Area Low (VAL)", vprofile.get("val", S0 * 0.98)),
            ("Resistance 1", key_levels.get("resistance_1", S0 * 1.015)),
            ("Support 1", key_levels.get("support_1", S0 * 0.985)),
        ]

        snapshots = []
        max_spread = 0.0
        high_vol_win = "0-5 hrs"

        for wid, t1, t2, label in windows_config:
            p_start_paths = paths[:, t1]
            p_end_paths = paths[:, t2]

            start_med = round(float(np.median(p_start_paths)), 2)
            end_med = round(float(np.median(p_end_paths)), 2)
            shift_pct = round((end_med - start_med) / max(0.01, start_med) * 100.0, 2)
            shift_dlr = round(end_med - start_med, 2)

            window_slice = paths[:, t1:t2 + 1]
            r_low = round(float(np.percentile(window_slice, 10)), 2)
            r_high = round(float(np.percentile(window_slice, 90)), 2)
            spread_pct = round((r_high - r_low) / max(0.01, start_med) * 100.0, 2)

            if spread_pct > max_spread:
                max_spread = spread_pct
                high_vol_win = wid

            prob_up = round(float(np.mean(p_end_paths > p_start_paths) * 100.0), 1)
            prob_dn = round(float(np.mean(p_end_paths < p_start_paths) * 100.0), 1)
            prob_exp_1 = round(float(np.mean(np.abs(p_end_paths - p_start_paths) / p_start_paths > 0.01) * 100.0), 1)

            touch_5_up = round(float(np.mean(np.max(window_slice, axis=1) >= S0 * 1.05) * 100.0), 1)
            touch_5_dn = round(float(np.mean(np.min(window_slice, axis=1) <= S0 * 0.95) * 100.0), 1)

            if shift_pct > 0.35 and prob_up >= 55.0:
                mode = "BULLISH_MOMENTUM_RUN"
                mode_lbl = "Bullish Momentum Continuation"
                mode_desc = "Upward order flow persistence driving price to test overhead liquidity."
            elif shift_pct < -0.35 and prob_dn >= 55.0:
                mode = "BEARISH_DISTRIBUTION_SLIDE"
                mode_lbl = "Bearish Liquidation Slide"
                mode_desc = "Selling pressure dominating order flow toward lower support bands."
            elif abs(end_med - gravity_target) < abs(start_med - gravity_target) and abs(start_med - gravity_target) > 0.003 * S0:
                mode = "EQUILIBRIUM_SNAP_BACK"
                mode_lbl = "Equilibrium Mean-Reversion"
                mode_desc = "Ornstein-Uhlenbeck statistical gravity pulling price toward volume POC."
            elif spread_pct < 1.0 or is_squeeze:
                mode = "TIGHT_COIL_CONSOLIDATION"
                mode_lbl = "Volatility Squeeze Compression"
                mode_desc = "Narrow range consolidation coiling kinetic energy prior to breakout."
            else:
                mode = "TWO_SIDED_AUCTION"
                mode_lbl = "Balanced Range Auction"
                mode_desc = "Two-sided liquidity absorption within standard deviation channels."

            closest_lvl = None
            min_dist = float("inf")
            for lvl_name, lvl_price in test_levels:
                dist = abs(lvl_price - end_med)
                if dist < min_dist:
                    min_dist = dist
                    test_prob = float(np.mean(
                        (np.min(window_slice, axis=1) <= lvl_price) & (np.max(window_slice, axis=1) >= lvl_price)
                    ) * 100.0)
                    closest_lvl = {
                        "level_name": lvl_name,
                        "level_price": round(float(lvl_price), 2),
                        "test_probability_pct": round(test_prob, 1),
                    }

            confidence = int(max(45, min(95, 92 - (t2 * 1.8) + (10 if hurst > 0.55 else 0))))

            snapshots.append({
                "window_id": wid,
                "window_label": label,
                "start_hour": t1,
                "end_hour": t2,
                "duration_hours": t2 - t1,
                "expected_start_price": start_med,
                "expected_end_price": end_med,
                "expected_shift_pct": shift_pct,
                "expected_shift_dollars": shift_dlr,
                "range_low": r_low,
                "range_high": r_high,
                "range_spread_pct": spread_pct,
                "prob_positive_move": prob_up,
                "prob_negative_move": prob_dn,
                "prob_expansion_gt_1pct": prob_exp_1,
                "prob_touch_5pct_up": touch_5_up,
                "prob_touch_5pct_down": touch_5_dn,
                "dominant_mode": mode,
                "mode_label": mode_lbl,
                "mode_description": mode_desc,
                "key_level_interaction": closest_lvl,
                "confidence_score": confidence,
            })

        w05 = snapshots[0]
        w1015 = snapshots[2]
        dominant_traj = f"{w05['mode_label']} in opening phase ({w05['expected_shift_pct']:+.2f}%) leading to {w1015['mode_label']} by hour 15."
        primary_bias = "BULLISH_DRIFT" if w05["expected_shift_pct"] > 0.1 else ("BEARISH_FADE" if w05["expected_shift_pct"] < -0.1 else "NEUTRAL_RANGE")

        return {
            "summary": {
                "dominant_trajectory": dominant_traj,
                "primary_phase_bias": primary_bias,
                "highest_volatility_window": high_vol_win,
            },
            "windows": snapshots,
        }

    @classmethod
    def analyze_and_predict(
        cls,
        df: pd.DataFrame,
        horizon_steps: int = 10,
        num_simulations: int = 1000,
        symbol: str = "",
        compute_extensions: bool = True,
    ) -> Dict[str, Any]:
        """
        Performs in-depth technical extraction, regime classification,
        multi-model progression synthesis, Monte Carlo simulation,
        multi-tier threshold confidence modeling, and dynamic timeframe snapshots.
        """
        if df.empty or len(df) < 20:
            raise ValueError("Insufficient data for advanced prediction suite (need at least 20 bars).")

        df = cls.calculate_indicators(df)
        prices = df["Close"].dropna().to_numpy(dtype=float)
        volumes = df["Volume"].dropna().to_numpy(dtype=float) if "Volume" in df else np.ones_like(prices)
        current_price = float(prices[-1])

        # 1. Regime Detection
        hurst = cls.estimate_hurst_exponent(prices)
        atr = float(df["ATR"].iloc[-1])
        volatility_daily = float(np.std(np.diff(np.log(prices[-30:] if len(prices) >= 30 else prices)))) * np.sqrt(252)
        if not np.isfinite(volatility_daily):
            volatility_daily = 0.25

        ema9 = float(df["EMA_9"].iloc[-1])
        ema21 = float(df["EMA_21"].iloc[-1])
        ema50 = float(df["EMA_50"].iloc[-1])
        rsi = float(df["RSI"].iloc[-1])
        macd_hist = float(df["MACD_Hist"].iloc[-1])
        is_squeeze = bool(df["TTM_Squeeze"].iloc[-1])

        # Regime classification
        if is_squeeze:
            regime = "VOLATILITY_SQUEEZE"
            regime_desc = "Price compression inside Keltner Channels. Massive directional breakout imminent."
            bias = "NEUTRAL"
        elif ema9 > ema21 > ema50 and rsi > 52 and macd_hist > 0:
            regime = "TRENDING_BULL"
            regime_desc = "Strong upward momentum with aligned multi-timeframe moving averages."
            bias = "BULLISH"
        elif ema9 < ema21 < ema50 and rsi < 48 and macd_hist < 0:
            regime = "TRENDING_BEAR"
            regime_desc = "Sustained downward momentum with bearish moving average stack."
            bias = "BEARISH"
        elif hurst < 0.45 or abs(rsi - 50) > 20:
            regime = "MEAN_REVERTING"
            regime_desc = "Anti-persistent price action. Tendency to revert back to statistical equilibrium."
            bias = "OVERSOLD_REVERSAL" if rsi < 35 else ("OVERBOUGHT_REVERSAL" if rsi > 65 else "MEAN_REVERT")
        else:
            regime = "CONSOLIDATION"
            regime_desc = "Directionless chop with balanced order flow. Range-bound execution favored."
            bias = "NEUTRAL"

        # 2. Ornstein-Uhlenbeck Mean-Reversion Parameters
        theta, mu, ou_sigma = cls.estimate_ornstein_uhlenbeck(prices)

        # 3. Volume Profile & Liquidity Footprint
        vprofile = cls.compute_volume_profile(prices, volumes, bins=20)
        poc = vprofile["poc"]
        vah = vprofile["vah"]
        val = vprofile["val"]

        # 4. Multi-Horizon Forecast Curves
        # Estimate annualized drift
        recent_log_ret = np.diff(np.log(prices[-15:])) if len(prices) >= 15 else np.array([0.0])
        momentum_drift = float(np.mean(recent_log_ret)) * 252.0 if len(recent_log_ret) > 0 else 0.0
        momentum_drift = float(np.clip(momentum_drift, -1.5, 1.5))

        # Weighting based on regime
        if regime in ("TRENDING_BULL", "TRENDING_BEAR"):
            w_mom = 0.70
            w_mr = 0.30
        elif regime == "MEAN_REVERTING":
            w_mom = 0.20
            w_mr = 0.80
        elif regime == "VOLATILITY_SQUEEZE":
            w_mom = 0.50
            w_mr = 0.50
        else:
            w_mom = 0.40
            w_mr = 0.60

        dt = 1.0 / 252.0
        base_path = [current_price]
        ou_path = [current_price]
        mom_path = [current_price]

        curr_p_base = current_price
        curr_p_ou = current_price
        curr_p_mom = current_price

        # Gravity target is a mix of OU mu and Volume POC
        gravity_target = (mu * 0.6) + (poc * 0.4)

        for step in range(1, horizon_steps + 1):
            # OU Euler without arbitrary *10 factor: dP = theta*(mu - P)*dt
            d_ou = theta * (gravity_target - curr_p_ou) * dt
            curr_p_ou += d_ou
            ou_path.append(curr_p_ou)

            decay = 0.92 ** step
            curr_p_mom *= math.exp(momentum_drift * dt * decay)
            mom_path.append(curr_p_mom)

            curr_p_base = (w_mom * curr_p_mom) + (w_mr * curr_p_ou)
            base_path.append(curr_p_base)

        # 5. Probabilistic Monte Carlo Simulation (1,000 paths)
        sim_paths = np.zeros((num_simulations, horizon_steps + 1))
        sim_paths[:, 0] = current_price

        np.random.seed(42)
        random_shocks = np.random.normal(0, 1, size=(num_simulations, horizon_steps))

        effective_drift = momentum_drift * w_mom + (theta * (gravity_target - current_price) / current_price) * w_mr

        for t in range(1, horizon_steps + 1):
            drift_term = (effective_drift - 0.5 * (volatility_daily ** 2)) * dt
            diffusion = volatility_daily * math.sqrt(dt) * random_shocks[:, t - 1]
            sim_paths[:, t] = sim_paths[:, t - 1] * np.exp(drift_term + diffusion)

        p5 = np.percentile(sim_paths, 5, axis=0)
        p25 = np.percentile(sim_paths, 25, axis=0)
        p50 = np.percentile(sim_paths, 50, axis=0)
        p75 = np.percentile(sim_paths, 75, axis=0)
        p95 = np.percentile(sim_paths, 95, axis=0)

        # 6. Scenarios: Bull, Base, Bear
        bull_target = float(np.percentile(sim_paths[:, -1], 85))
        base_target = float(p50[-1])
        bear_target = float(np.percentile(sim_paths[:, -1], 15))

        prob_bull = float(np.mean(sim_paths[:, -1] > current_price * 1.01))
        prob_bear = float(np.mean(sim_paths[:, -1] < current_price * 0.99))
        prob_base = max(0.0, 1.0 - (prob_bull + prob_bear))

        tot_prob = prob_bull + prob_base + prob_bear
        if tot_prob > 0:
            prob_bull = round(prob_bull / tot_prob * 100, 1)
            prob_base = round(prob_base / tot_prob * 100, 1)
            prob_bear = round(prob_bear / tot_prob * 100, 1)

        # 7. Actionable Trading Blueprint
        if bias in ("BULLISH", "OVERSOLD_REVERSAL") or (prob_bull > prob_bear + 10):
            action = "LONG"
            entry_low = round(current_price - (0.3 * atr), 2)
            entry_high = round(current_price + (0.1 * atr), 2)
            stop_loss = round(current_price - (1.5 * atr), 2)
            target_1 = round(current_price + (1.5 * atr), 2)
            target_2 = round(current_price + (3.0 * atr), 2)
            risk = max(0.01, current_price - stop_loss)
            reward = target_1 - current_price
            rr_ratio = round(reward / risk, 2)
            conviction = min(95, int(50 + abs(prob_bull - prob_bear) * 0.7 + (20 if not is_squeeze else 10)))
        elif bias in ("BEARISH", "OVERBOUGHT_REVERSAL") or (prob_bear > prob_bull + 10):
            action = "SHORT"
            entry_high = round(current_price + (0.3 * atr), 2)
            entry_low = round(current_price - (0.1 * atr), 2)
            stop_loss = round(current_price + (1.5 * atr), 2)
            target_1 = round(current_price - (1.5 * atr), 2)
            target_2 = round(current_price - (3.0 * atr), 2)
            risk = max(0.01, stop_loss - current_price)
            reward = current_price - target_1
            rr_ratio = round(reward / risk, 2)
            conviction = min(95, int(50 + abs(prob_bear - prob_bull) * 0.7 + (20 if not is_squeeze else 10)))
        else:
            action = "WAIT / RANGE TRADE"
            entry_low = round(val, 2)
            entry_high = round(vah, 2)
            stop_loss = round(val - atr, 2)
            target_1 = round(poc, 2)
            target_2 = round(vah, 2)
            rr_ratio = 1.5
            conviction = 45

        steps_table = []
        for s in range(1, horizon_steps + 1):
            exp_p = base_path[s]
            pct_chg = (exp_p - current_price) / current_price * 100.0
            steps_table.append({
                "step": s,
                "expected_price": round(exp_p, 2),
                "pct_change": round(pct_chg, 2),
                "lower_90_cone": round(float(p5[s]), 2),
                "lower_50_cone": round(float(p25[s]), 2),
                "upper_50_cone": round(float(p75[s]), 2),
                "upper_90_cone": round(float(p95[s]), 2),
                "confidence": round(max(0.35, 0.95 - (s * 0.04)), 2),
            })

        # Multi-tier threshold confidence ladder & dynamic timeframe snapshots
        threshold_confidences = None
        timeframe_snapshots = None
        if compute_extensions:
            is_crypto = any(x in str(symbol).upper() for x in ("-USD", "-EUR", "BTC", "ETH", "SOL", "CRYPTO"))
            key_levels_dict = {
                "resistance_2": round(current_price + 2.0 * atr, 2),
                "resistance_1": round(current_price + 1.0 * atr, 2),
                "poc": poc,
                "vah": vah,
                "val": val,
                "support_1": round(current_price - 1.0 * atr, 2),
                "support_2": round(current_price - 2.0 * atr, 2),
                "vwap": round(float(df["VWAP"].iloc[-1]), 2),
            }
            threshold_confidences = cls.compute_threshold_confidences(
                current_price=current_price,
                volatility_daily=volatility_daily,
                effective_drift=effective_drift,
                gravity_target=gravity_target,
                theta=theta,
                is_crypto=is_crypto,
                num_simulations=num_simulations,
            )
            timeframe_snapshots = cls.compute_timeframe_snapshots(
                current_price=current_price,
                volatility_daily=volatility_daily,
                effective_drift=effective_drift,
                gravity_target=gravity_target,
                theta=theta,
                vprofile=vprofile,
                key_levels=key_levels_dict,
                hurst=hurst,
                is_squeeze=is_squeeze,
                is_crypto=is_crypto,
                num_simulations=num_simulations,
            )

        return _sanitize({
            "current_price": round(current_price, 2),
            "regime": regime,
            "regime_description": regime_desc,
            "directional_bias": bias,
            "action": action,
            "conviction_score": conviction,
            "hurst_exponent": round(hurst, 3),
            "annualized_volatility": round(volatility_daily * 100.0, 1),
            "atr": round(atr, 2),
            "mean_reversion_gravity": round(gravity_target, 2),
            "volume_profile": vprofile,
            "key_levels": {
                "resistance_2": round(current_price + 2.0 * atr, 2),
                "resistance_1": round(current_price + 1.0 * atr, 2),
                "poc": poc,
                "vah": vah,
                "val": val,
                "support_1": round(current_price - 1.0 * atr, 2),
                "support_2": round(current_price - 2.0 * atr, 2),
                "vwap": round(float(df["VWAP"].iloc[-1]), 2),
            },
            "scenarios": {
                "bull": {
                    "label": "Bull Breakout / Expansion",
                    "target_price": round(bull_target, 2),
                    "expected_move_pct": round((bull_target - current_price) / current_price * 100, 2),
                    "probability_pct": prob_bull,
                },
                "base": {
                    "label": "Base Consensus Trajectory",
                    "target_price": round(base_target, 2),
                    "expected_move_pct": round((base_target - current_price) / current_price * 100, 2),
                    "probability_pct": prob_base,
                },
                "bear": {
                    "label": "Bear Breakdown / Mean-Reversion Flush",
                    "target_price": round(bear_target, 2),
                    "expected_move_pct": round((bear_target - current_price) / current_price * 100, 2),
                    "probability_pct": prob_bear,
                },
            },
            "trade_blueprint": {
                "recommended_action": action,
                "entry_zone": f"${entry_low:.2f} - ${entry_high:.2f}",
                "stop_loss": stop_loss,
                "target_1": target_1,
                "target_2": target_2,
                "risk_reward_ratio": rr_ratio,
                "conviction_pct": conviction,
            },
            "forecast_steps": steps_table,
            "monte_carlo_cone": {
                "steps": list(range(horizon_steps + 1)),
                "p5": [round(float(x), 2) for x in p5],
                "p25": [round(float(x), 2) for x in p25],
                "p50": [round(float(x), 2) for x in p50],
                "p75": [round(float(x), 2) for x in p75],
                "p95": [round(float(x), 2) for x in p95],
                "base_path": [round(float(x), 2) for x in base_path],
                "ou_path": [round(float(x), 2) for x in ou_path],
                "momentum_path": [round(float(x), 2) for x in mom_path],
            },
            "threshold_confidences": threshold_confidences,
            "timeframe_snapshots": timeframe_snapshots,
            "technical_indicators": {
                "rsi": round(rsi, 1),
                "macd_hist": round(macd_hist, 3),
                "ttm_squeeze": is_squeeze,
                "ema_9": round(ema9, 2),
                "ema_21": round(ema21, 2),
                "ema_50": round(ema50, 2),
                "bb_upper": round(float(df["BB_Upper"].iloc[-1]), 2),
                "bb_lower": round(float(df["BB_Lower"].iloc[-1]), 2),
            },
        })


class PredictionReviewer:
    """
    Exhaustive walk-forward prediction audit and verification engine.

    Backtests predictive models over rolling historical windows without look-ahead bias:
      - Measures Directional Accuracy (Hit Rate %)
      - Tracks Mean Absolute Error (MAE), RMSE, and MAPE
      - Evaluates Calibration / Reliability Score
      - Provides historical overlay of past forecasts vs actual realized prices
      - Generates hypothetical cumulative trade equity curve
    """

    @classmethod
    def audit_predictions(
        cls,
        df: pd.DataFrame,
        walk_forward_bars: int = 50,
        forecast_horizon: int = 5,
    ) -> Dict[str, Any]:
        """
        Runs a rolling walk-forward audit on historical data.
        At each bar t, trains on data up to t, predicts t+1 to t+horizon,
        and logs error against actual realized outcomes.
        """
        if len(df) < walk_forward_bars + 25:
            raise ValueError(
                f"Insufficient historical bars ({len(df)}) for a {walk_forward_bars}-bar walk-forward review."
            )

        prices = df["Close"].dropna().to_numpy(dtype=float)
        n = len(prices)
        start_idx = max(25, n - walk_forward_bars - forecast_horizon)

        evaluations = []
        forecast_overlays = []
        directional_hits = 0
        total_predictions = 0
        absolute_errors = []
        squared_errors = []
        percentage_errors = []

        sim_pnl = [10000.0]

        overlay_interval = max(1, (n - forecast_horizon - start_idx) // 4)

        for t in range(start_idx, n - forecast_horizon):
            historical_slice = df.iloc[: t + 1]
            try:
                pred_result = AdvancedPredictor.analyze_and_predict(
                    historical_slice, horizon_steps=forecast_horizon, num_simulations=200, compute_extensions=False
                )
            except Exception:
                continue

            base_p = prices[t]
            pred_future_5 = pred_result["forecast_steps"][-1]["expected_price"]
            actual_future_5 = prices[t + forecast_horizon]

            pred_dir = 1 if pred_future_5 > base_p else -1
            actual_dir = 1 if actual_future_5 > base_p else -1

            is_correct_dir = pred_dir == actual_dir
            if is_correct_dir:
                directional_hits += 1
            total_predictions += 1

            abs_err = abs(pred_future_5 - actual_future_5)
            sq_err = (pred_future_5 - actual_future_5) ** 2
            pct_err = abs_err / actual_future_5 * 100.0

            absolute_errors.append(abs_err)
            squared_errors.append(sq_err)
            percentage_errors.append(pct_err)

            ret_5 = (actual_future_5 - base_p) / base_p
            trade_ret = ret_5 * pred_dir
            new_equity = sim_pnl[-1] * (1.0 + trade_ret)
            sim_pnl.append(new_equity)

            evaluations.append({
                "bar_index": t,
                "anchor_price": round(base_p, 2),
                "predicted_price": round(pred_future_5, 2),
                "actual_price": round(actual_future_5, 2),
                "predicted_dir": "UP" if pred_dir > 0 else "DOWN",
                "actual_dir": "UP" if actual_dir > 0 else "DOWN",
                "hit": is_correct_dir,
                "abs_error": round(abs_err, 2),
                "pct_error": round(pct_err, 2),
            })

            if (t - start_idx) % overlay_interval == 0 and len(forecast_overlays) < 5:
                pred_path = [base_p] + [step["expected_price"] for step in pred_result["forecast_steps"]]
                actual_path = prices[t : t + forecast_horizon + 1].tolist()
                date_labels = (
                    df["Date"].iloc[t : t + forecast_horizon + 1].astype(str).tolist()
                    if "Date" in df
                    else [f"T+{i}" for i in range(forecast_horizon + 1)]
                )

                forecast_overlays.append({
                    "anchor_idx": t,
                    "date_labels": date_labels,
                    "predicted_path": [round(float(p), 2) for p in pred_path],
                    "actual_path": [round(float(p), 2) for p in actual_path],
                    "regime_at_time": pred_result["regime"],
                    "hit": is_correct_dir,
                })

        if total_predictions == 0:
            return {"error": "Could not complete walk-forward evaluation."}

        hit_rate = (directional_hits / total_predictions) * 100.0
        mae = float(np.mean(absolute_errors))
        rmse = float(math.sqrt(np.mean(squared_errors)))
        mape = float(np.mean(percentage_errors))

        if hit_rate >= 62.0 and mape < 4.0:
            grade = "A (Institutional Alpha)"
            quality = "EXCELLENT"
        elif hit_rate >= 54.0 and mape < 6.0:
            grade = "B+ (Statistical Edge)"
            quality = "GOOD"
        elif hit_rate >= 48.0:
            grade = "B (Marginal Edge)"
            quality = "ACCEPTABLE"
        else:
            grade = "C- (Underperforming / Drift)"
            quality = "DEGRADED"

        bh_start = prices[start_idx]
        bh_end = prices[min(len(prices) - 1, start_idx + len(sim_pnl) - 1)]
        bh_return = ((bh_end - bh_start) / bh_start) * 100.0
        strategy_return = ((sim_pnl[-1] - sim_pnl[0]) / sim_pnl[0]) * 100.0

        return _sanitize({
            "total_evaluations": total_predictions,
            "directional_hit_rate_pct": round(hit_rate, 2),
            "mae": round(mae, 2),
            "rmse": round(rmse, 2),
            "mape_pct": round(mape, 2),
            "model_grade": grade,
            "quality_status": quality,
            "performance_comparison": {
                "strategy_cumulative_return_pct": round(strategy_return, 2),
                "buy_and_hold_return_pct": round(bh_return, 2),
                "alpha_over_benchmark_pct": round(strategy_return - bh_return, 2),
                "equity_curve": [round(float(e), 2) for e in sim_pnl],
            },
            "recent_audit_samples": evaluations[-10:],
            "historical_forecast_overlays": forecast_overlays,
        })


class PredictionScreener:
    """
    Scans tracked market symbols and produces a cross-asset predictive leaderboard.
    """

    @classmethod
    def scan_universe(
        cls,
        analytics_engine: Any,
        symbols: List[str],
        interval: str = "1d",
        period: str = "1y",
    ) -> List[Dict[str, Any]]:
        results = []
        for sym in symbols:
            try:
                df = analytics_engine.fetch_live_data(sym, period, interval)
                if df is None or len(df) < 25:
                    continue
                analysis = AdvancedPredictor.analyze_and_predict(df, horizon_steps=5, num_simulations=200)
                base_scenario = analysis["scenarios"]["base"]
                bull_scenario = analysis["scenarios"]["bull"]
                bear_scenario = analysis["scenarios"]["bear"]

                results.append({
                    "symbol": sym,
                    "current_price": analysis["current_price"],
                    "regime": analysis["regime"],
                    "bias": analysis["directional_bias"],
                    "action": analysis["action"],
                    "conviction": analysis["conviction_score"],
                    "expected_move_pct": base_scenario["expected_move_pct"],
                    "bull_target": bull_scenario["target_price"],
                    "bull_prob_pct": bull_scenario["probability_pct"],
                    "bear_target": bear_scenario["target_price"],
                    "bear_prob_pct": bear_scenario["probability_pct"],
                    "risk_reward": analysis["trade_blueprint"]["risk_reward_ratio"],
                    "hurst": analysis["hurst_exponent"],
                    "volatility_ann": analysis["annualized_volatility"],
                })
            except Exception as exc:
                logger.debug(f"Screener skip {sym}: {exc}")
                continue

        results.sort(key=lambda x: (x["conviction"], abs(x["expected_move_pct"])), reverse=True)
        return results
