import time
from ..research.validation import ResearchValidator
from ..replay.time_machine import TimeMachine
from ..research.backtester import Backtester

class RiskCommittee:
    def __init__(self):
        self.tm = TimeMachine()
        self.bt = Backtester()

    def evaluate_strategy(self, strategy_name, observed_sr, num_trials, universe):
        results = {
            "strategy": strategy_name,
            "tests": [],
            "verdict": "APPROVED",
            "rejection_reason": None
        }

        # TEST 1: The Overfit Check (Statistical Significance)
        dsr = ResearchValidator.deflated_sharpe_ratio(observed_sr, num_trials)
        test1 = {"name": "Deflated Sharpe Ratio (Overfit Check)", "status": "PASS", "detail": f"Prob Real: {dsr['dsr_probability']*100:.1f}%"}
        if not dsr["is_significant"]:
            test1["status"] = "FAIL"
            test1["detail"] = "Alpha is statistically indistinguishable from random noise."
            results["verdict"] = "REJECTED"
            results["rejection_reason"] = "Failed DSR: Likely Overfit"
        results["tests"].append(test1)
        if results["verdict"] == "REJECTED": return results

        # TEST 2: The Black Swan Check (Tail Risk)
        tm_report = self.tm.run_stress_test("2022_crypto_winter")
        test2 = {"name": "Time Machine (2022 Crypto Winter)", "status": "PASS", "detail": f"Max DD: {tm_report['max_dd_pct']}%"}
        if tm_report["max_dd_pct"] < -20.0: # Hard limit: 20% drawdown
            test2["status"] = "FAIL"
            test2["detail"] = f"Drawdown {tm_report['max_dd_pct']}% breaches 20% risk mandate."
            results["verdict"] = "REJECTED"
            results["rejection_reason"] = "Failed Stress Test: Catastrophic Tail Risk"
        results["tests"].append(test2)
        if results["verdict"] == "REJECTED": return results

        # TEST 3: The Friction Check (Transaction Cost Reality)
        # We force the backtester to run with brutal 15bps slippage (retail market order costs)
        # A robust strategy must still be profitable even with bad execution.
        bt_report = self.bt.run_cross_sectional_momentum(universe, lookback=60, slippage_bps=15.0)
        test3 = {"name": "High-Friction Slippage (15 bps)", "status": "PASS", "detail": "Strategy survives worst-case execution costs."}
        if "error" in bt_report or bt_report["metrics"]["total_return"] < 0:
            test3["status"] = "FAIL"
            test3["detail"] = "Strategy turns negative when subjected to realistic market impact."
            results["verdict"] = "REJECTED"
            results["rejection_reason"] = "Failed Friction Test: Alpha consumed by slippage"
        results["tests"].append(test3)

        return results
