"""Institutional Validation Metrics."""
import numpy as np
import scipy.stats as ss

class ResearchValidator:
    """
    Implements Deflated Sharpe Ratio (DSR) and Combinatorial Purged CV logic.
    """

    @staticmethod
    def deflated_sharpe_ratio(
        observed_sr: float,
        num_trials: int,
        skewness: float = 0.0,
        kurtosis: float = 3.0,
        annualization_factor: int = 252,
        num_observations: int | None = None,
    ) -> dict:
        """
        Calculates the probability that the observed Sharpe Ratio is a statistical fluke
        resulting from multiple testing (Backtest Overfitting).

        Correct variance per Lo (2002): Var(SR) = (1 - skew*SR + (kurt-1)/4 * SR^2) / T
        where T = num_observations (number of return observations).

        For backward compatibility, if num_observations is None we fall back to
        annualization_factor, but emit a note in the result. New code should pass
        num_observations explicitly (e.g., len(returns)).

        Also handles the i.i.d. N(0,1) assumption note: E[max_N] formula is for
        uncorrelated trials. If strategies are correlated, the effective N is smaller;
        see Bailey & Lopez de Prado (2014) for clustered trials.
        """
        euler_mascheroni = 0.5772156649015329
        if num_trials < 1:
            raise ValueError("num_trials must be at least 1")
        if num_trials == 1:
            expected_max_sr = 0.0
        else:
            log_n = np.log(num_trials)
            leading = np.sqrt(2 * log_n)
            correction = (np.log(np.pi) + np.log(log_n) + 2 * euler_mascheroni) / (2 * leading)
            expected_max_sr = leading - correction

        # Correct denominator: T = number of observations, not periods per year.
        # If caller did not provide T, use annualization_factor as legacy fallback
        # but flag it so callers can migrate.
        if num_observations is not None:
            if num_observations < 2:
                raise ValueError("num_observations must be >= 2")
            T = float(num_observations)
            legacy_fallback = False
        else:
            T = float(annualization_factor)
            legacy_fallback = True

        sr_var = (1 - skewness * observed_sr + ((kurtosis - 1) / 4) * observed_sr**2) / T
        sr_var = max(1e-8, sr_var)

        z_score = (observed_sr - expected_max_sr) / np.sqrt(sr_var)
        p_value = 1 - ss.norm.cdf(z_score)
        dsr_prob = float(np.clip(1 - p_value, 0.0, 1.0))

        result = {
            "observed_sr": round(float(observed_sr), 3),
            "expected_max_sr_noise": round(float(expected_max_sr), 3),
            "dsr_probability": round(dsr_prob, 4),
            "is_significant": bool(dsr_prob > 0.95),
            "trials_penalized": int(num_trials),
            "variance_denominator_T": int(T),
            "variance_formula": "Lo(2002) Var(SR) = (1 - skew*SR + (kurt-1)/4*SR^2)/T",
        }
        if legacy_fallback:
            result["warning"] = (
                "num_observations not provided; using annualization_factor as T. "
                "For correct inference, pass num_observations=len(returns)."
            )
        return result

    @staticmethod
    def signal_decay(returns: np.ndarray, signal: np.ndarray, max_lag: int = 10) -> list:
        """
        Measures how fast a predictive signal loses its power over time.
        Uses Pearson correlation; handles constant signals and NaNs gracefully.
        Returns correlation for each lag, clipped to [-1,1].
        """
        decay = []
        returns = np.asarray(returns, dtype=float)
        signal = np.asarray(signal, dtype=float)
        for lag in range(1, max_lag + 1):
            if lag >= len(returns):
                break
            x = signal[:-lag]
            y = returns[lag:]
            # Need at least 3 points and non-constant variance
            if len(x) < 3 or np.nanstd(x) < 1e-12 or np.nanstd(y) < 1e-12:
                corr = 0.0
            else:
                # Remove NaN pairs
                mask = np.isfinite(x) & np.isfinite(y)
                if np.sum(mask) < 3:
                    corr = 0.0
                else:
                    corr_mat = np.corrcoef(x[mask], y[mask])
                    corr = corr_mat[0, 1] if corr_mat.shape == (2, 2) else 0.0
                    if not np.isfinite(corr):
                        corr = 0.0
                    corr = float(np.clip(corr, -1.0, 1.0))
            decay.append({"lag": lag, "correlation": round(float(corr), 4)})
        return decay
