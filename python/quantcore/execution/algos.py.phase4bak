"""Institutional Execution Algorithms."""
import numpy as np
import yfinance as yf
import pandas as pd

class ExecutionEngine:
    """Simulates institutional order slicing (VWAP/TWAP) to minimize market impact."""

    @staticmethod
    def simulate_execution(symbol: str, total_shares: int, algo: str, interval: str = "5m") -> dict:
        # Fetch recent intraday data to build a volume profile
        df = yf.download(symbol, period="5d", interval=interval, progress=False)
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

        if algo == "MARKET":
            # Retail approach: Dump it all at once at the last price + slippage
            exec_price = prices[-1] * 1.0015 # Assume 15bps market impact
            execution_prices = [exec_price] * 10
            executed_shares = total_shares
            simulated_slippage = (exec_price - benchmark_vwap) / benchmark_vwap * 10000 # in bps

        elif algo == "TWAP":
            # Time-Weighted: Slice evenly across time
            slices = 10
            shares_per_slice = total_shares // slices
            for i in range(slices):
                idx = min(int(i * (len(prices)/slices)), len(prices)-1)
                exec_price = prices[idx] * 1.0002 # 2bps impact per slice
                execution_prices.extend([exec_price] * shares_per_slice)
            executed_shares = total_shares
            avg_exec = np.mean(execution_prices)
            simulated_slippage = (avg_exec - benchmark_vwap) / benchmark_vwap * 10000

        elif algo == "VWAP":
            # Volume-Weighted: Slice proportionally to historical volume
            total_vol = sum(volumes)
            slices = 10
            step = len(volumes) // slices
            for i in range(slices):
                vol_chunk = sum(volumes[i*step : (i+1)*step])
                participation_rate = vol_chunk / total_vol
                shares_to_buy = int(total_shares * participation_rate)

                idx = min(i*step + step//2, len(prices)-1)
                exec_price = prices[idx] * 1.0001 # 1bps impact (highly隐蔽)
                execution_prices.extend([exec_price] * shares_to_buy)

            executed_shares = len(execution_prices)
            avg_exec = np.mean(execution_prices) if execution_prices else prices[-1]
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
