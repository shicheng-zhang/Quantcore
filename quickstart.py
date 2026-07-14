#!/usr/bin/env python3
"""
QuantCore V1.0 Quickstart
Proves the entire pipeline works headless: Data -> Backtest -> Risk Gauntlet.
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__))))

from python.quantcore.research.backtester import Backtester
from python.quantcore.risk.gauntlet import RiskCommittee
from rich.console import Console
from rich.panel import Panel

console = Console()

def main():
    console.print(Panel.fit("[bold blue]⚡ QuantCore V1.0 Quickstart[/bold blue]\nRunning headless pipeline test...", border_style="blue"))
    
    # 1. Run Backtest
    console.print("\n[1/2] Running Cross-Sectional Momentum Backtest...")
    bt = Backtester()
    universe = ["SPY", "QQQ", "IWM", "GLD", "TLT"]
    results = bt.run_cross_sectional_momentum(universe, lookback=60, slippage_bps=5.0)
    
    if "error" in results:
        console.print(f"[red]❌ Backtest Failed: {results['error']}[/red]")
        return
        
    metrics = results["metrics"]
    console.print(f"[green]✅ Backtest Complete:[/green] CAGR: {metrics['cagr']}% | Sharpe: {metrics['sharpe']} | Max DD: {metrics['max_dd']}%")
    
    # 2. Run Risk Gauntlet
    console.print("\n[2/2] Submitting to Risk Committee Gauntlet...")
    committee = RiskCommittee()
    verdict = committee.evaluate_strategy(
        strategy_name="Quickstart Momentum",
        observed_sr=metrics['sharpe'],
        num_trials=10,
        universe=universe
    )
    
    if verdict["verdict"] == "APPROVED":
        console.print(Panel.fit("[bold green]✅ STRATEGY APPROVED FOR DEPLOYMENT[/bold green]", border_style="green"))
    else:
        console.print(Panel.fit(f"[bold red]❌ STRATEGY REJECTED[/bold red]\nReason: {verdict['rejection_reason']}", border_style="red"))
        
    console.print("\n[bold blue]⚡ Quickstart Complete. System is fully operational.[/bold blue]")

if __name__ == "__main__":
    main()
