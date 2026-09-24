"""Institutional Execution Algorithms."""
import numpy as np
import pandas as pd
from ..data.provider import fetch_ohlcv

class ExecutionEngine:
    """Simulates institutional order slicing (VWAP/TWAP) to minimize market impact."""

    @staticmethod
    def simulate_execution(symbol: str, total_shares: int, algo: str, interval: str = "5m") -> dict:
        # Fetch recent intraday data to build a volume profile
        df = fetch_ohlcv(symbol, period="5d", interval=interval)
        if df.empty: return {"error": "No data"}

        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.droplevel(1)
        df = df.reset_index()

        prices = df['Close'].astype(float).tolist()
        volumes = df['Volume'].astype(float).tolist()

        # Calculate Benchmark VWAP (Volume Weighted Average Price)
        benchmark_vwap = sum(p * v for p, v in zip(prices, volumes)) / sum(volumes)

        executed_shares = 0
        execution_prices = []
        simulated_slippage = 0.0

        # Unified Almgren-Chriss impact: slip_bps = eta * sigma * sqrt(Q_slice / ADV) * 10000
        # Calibrated to match paper_broker.py and nexus GhostExchange (eta=0.15).
        # sigma estimated from recent realized vol; ADV from average volumes.
        is_crypto = "-USD" in symbol
        # Estimate realized vol from returns (daily-equivalent)
        try:
            rets = pd.Series(prices).pct_change().dropna()
            sigma = float(rets.std() * np.sqrt(78 if interval in ("5m", "1m", "15m") else 6.5)) if len(rets) > 5 else 0.02
            sigma = float(np.clip(sigma, 0.005, 0.10))
        except Exception:
            sigma = 0.02
        adv = float(np.mean(volumes) * (78 if interval in ("5m", "1m", "15m") else 1)) if volumes else 50000.0
        adv = max(1_000.0, adv)
        eta = 0.15

        if algo == "MARKET":
            # Single slice: full impact
            base_slip = eta * sigma * np.sqrt(float(total_shares) / adv) * 10000.0
            base_slip = float(np.clip(base_slip * 3.0, 1.0, 50.0))
            exec_price = prices[-1] * (1 + base_slip / 10000.0)
            execution_prices = [exec_price] * total_shares
            executed_shares = total_shares
            simulated_slippage = (exec_price - benchmark_vwap) / benchmark_vwap * 10000

        elif algo == "TWAP":
            slices = 10
            shares_per_slice = total_shares // slices
            remainder = total_shares % slices
            for i in range(slices):
                idx = min(int(i * (len(prices) / slices)), len(prices) - 1)
                # Impact per slice
                q = shares_per_slice + (1 if i < remainder else 0)
                slip = eta * sigma * np.sqrt(float(q) / adv) * 10000.0
                slip = float(np.clip(slip * 1.2, 0.8, 30.0))
                exec_price = prices[idx] * (1 + slip / 10000.0)
                execution_prices.extend([exec_price] * q)
            executed_shares = len(execution_prices)
            avg_exec = float(np.mean(execution_prices)) if execution_prices else prices[-1]
            simulated_slippage = (avg_exec - benchmark_vwap) / benchmark_vwap * 10000

        elif algo == "VWAP":
            total_vol = sum(volumes)
            slices = 10
            step = len(volumes) // slices
            remainder_shares = total_shares
            for i in range(slices):
                # Handle remainder volume proportionally
                if i == slices - 1:
                    vol_chunk = sum(volumes[i * step :])
                    # Last slice gets all remaining volume
                else:
                    vol_chunk = sum(volumes[i * step : (i + 1) * step])
                participation_rate = vol_chunk / total_vol if total_vol > 0 else 1.0 / slices
                # Last slice gets remainder to ensure total fills exactly
                if i == slices - 1:
                    shares_to_buy = remainder_shares
                else:
                    shares_to_buy = int(round(total_shares * participation_rate))
                    shares_to_buy = min(shares_to_buy, remainder_shares - (slices - i - 1))
                    shares_to_buy = max(0, shares_to_buy)
                remainder_shares -= shares_to_buy

                idx = min(i * step + step // 2, len(prices) - 1)
                slip = eta * sigma * np.sqrt(float(max(1, shares_to_buy)) / adv) * 10000.0
                slip = float(np.clip(slip * 0.43, 0.5, 20.0))
                exec_price = prices[idx] * (1 + slip / 10000.0)
                execution_prices.extend([exec_price] * shares_to_buy)

            # Ensure exact fill: pad or trim due to rounding
            if len(execution_prices) < total_shares:
                execution_prices.extend([execution_prices[-1]] * (total_shares - len(execution_prices)) if execution_prices else [prices[-1]] * (total_shares - len(execution_prices)))
            elif len(execution_prices) > total_shares:
                execution_prices = execution_prices[:total_shares]

            executed_shares = len(execution_prices)
            avg_exec = float(np.mean(execution_prices)) if execution_prices else prices[-1]
            simulated_slippage = (avg_exec - benchmark_vwap) / benchmark_vwap * 10000

        return {
            "symbol": symbol,
            "algo": algo,
            "target_shares": total_shares,
            "executed_shares": executed_shares,
            "benchmark_vwap": benchmark_vwap,
            "avg_execution_price": np.mean(execution_prices) if execution_prices else 0,
            "slippage_bps": round(simulated_slippage, 2),
            "savings_vs_market": round((15 - simulated_slippage) * (total_shares * benchmark_vwap) / 10000, 2) if algo != "MARKET" else 0
        }
