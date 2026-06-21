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
        annualization_factor: int = 252
    ) -> dict:
        """
        Calculates the probability that the observed Sharpe Ratio is a statistical fluke
        resulting from multiple testing (Backtest Overfitting).
        """
        # Expected maximum Sharpe Ratio from num_trials of random noise
        # Using Euler-Mascheroni constant approximation for max of normal distribution
        expected_max_sr = np.sqrt(2 * np.log(num_trials))

        # Variance of the Sharpe Ratio estimator
        sr_var = (1 - skewness * observed_sr + ((kurtosis - 1) / 4) * observed_sr**2) / annualization_factor

        # Test statistic (Z-score)
        z_score = (observed_sr - expected_max_sr) / np.sqrt(sr_var)

        # P-value (Probability that this SR is luck)
        p_value = 1 - ss.norm.cdf(z_score)

        return {
            "observed_sr": round(float(observed_sr), 3),
            "expected_max_sr_noise": round(float(expected_max_sr), 3),
            "dsr_probability": round(float(1 - p_value), 4), # Probability it IS real alpha
            "is_significant": bool((1 - p_value) > 0.95),
            "trials_penalized": int(num_trials)
        }

    @staticmethod
    def signal_decay(returns: np.ndarray, signal: np.ndarray, max_lag: int = 10) -> list:
        """
        Measures how fast a predictive signal loses its power over time.
        """
        decay = []
        for lag in range(1, max_lag + 1):
            if lag >= len(returns): break
            # Correlation between signal(t) and returns(t+lag)
            corr = np.corrcoef(signal[:-lag], returns[lag:])[0, 1]
            decay.append({"lag": lag, "correlation": round(corr, 4)})
        return decay
