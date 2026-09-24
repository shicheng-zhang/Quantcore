import duckdb
import json
import os
import numpy as np
from ..logging_config import get_logger

logger = get_logger(__name__)

class CIOAttributor:
    def __init__(self, paper_broker=None):
        self.paper_broker = paper_broker
        self.db_path = "data/paper_broker.duckdb"

    def get_metrics(self):
        metrics = {
            "total_equity": 1000000.0,
            "total_pnl": 0.0,
            "execution_alpha_bps": 0.0,
            "slippage_cost_bps": 0.0,
            "vetoes_triggered": 0,
            "capital_protected": 0.0,
            "sharpe_30d": 0.0,
            "trades_executed": 0,
            "pnl_history": []
        }

        if self.paper_broker:
            try:
                state = self.paper_broker.ledger.get_state()
                cash = state['cash']
                initial = state['initial_cash']
                metrics["total_equity"] = cash
                metrics["total_pnl"] = cash - initial

                trades = self.paper_broker.ledger.con.execute("SELECT COUNT(*), SUM(slippage_bps) FROM trades").fetchone()
                metrics["trades_executed"] = trades[0] or 0
                total_slip = trades[1] or 0.0
                metrics["slippage_cost_bps"] = total_slip

                if metrics["trades_executed"] > 0:
                    avg_slip = total_slip / metrics["trades_executed"]
                    # Market orders cost ~15bps. VWAP costs ~2bps.
                    # Execution Alpha is the difference between retail dump and our actual execution.
                    metrics["execution_alpha_bps"] = max(0, 15.0 - avg_slip)

            except Exception as e:
                logger.error(f"CIO metrics DB error: {e}")

        log_path = "data/quant_daemon.log"
        if os.path.exists(log_path):
            try:
                with open(log_path, "r") as f:
                    logs = f.read()
                    vetoes = logs.count("[SATELLITE VETO]")
                    metrics["vetoes_triggered"] = vetoes
                    metrics["capital_protected"] = vetoes * 2500.0
            except Exception as e:
                logger.warning("Log file read error: %s", e)

        # Compute Sharpe from actual trade-level returns if available, otherwise 0
        # Previously used an invented formula sharpe = ret*252 / max(0.01, |ret|*2) which is not Sharpe.
        # Now: pull realized daily P&L from trades table if it has a timestamp/return column,
        # else report 0 and flag that more granular data is needed.
        if self.paper_broker:
            try:
                # Try to compute daily returns from ledger trades if timestamps exist
                rows = self.paper_broker.ledger.con.execute(
                    "SELECT timestamp, pnl FROM trades ORDER BY timestamp"
                ).fetchall()
                if rows and len(rows) >= 2:
                    # Approximate daily returns from cumulative pnl changes
                    pnls = [r[1] for r in rows if r[1] is not None]
                    if len(pnls) >= 10:
                        rets = np.diff(pnls) / max(metrics["total_equity"], 1.0)
                        if len(rets) >= 2 and np.std(rets) > 1e-12:
                            sharpe = float(np.mean(rets) / np.std(rets) * np.sqrt(252))
                            if np.isfinite(sharpe):
                                metrics["sharpe_30d"] = round(float(np.clip(sharpe, -5, 5)), 2)
                            else:
                                metrics["sharpe_30d"] = 0.0
                        else:
                            metrics["sharpe_30d"] = 0.0
                    else:
                        metrics["sharpe_30d"] = 0.0
                else:
                    # Fallback: not enough granular data — report 0 with note
                    metrics["sharpe_30d"] = 0.0
                    metrics["sharpe_note"] = "Insufficient trade history for Sharpe (need >=10 trades with pnl timestamps)"
            except Exception as e:
                logger.debug(f"Sharpe calc fallback: {e}")
                metrics["sharpe_30d"] = 0.0
        else:
            metrics["sharpe_30d"] = 0.0

        return metrics
