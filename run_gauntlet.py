#!/usr/bin/env python3
import sys
import time
sys.path.insert(0, 'python')
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress
from quantcore.risk.gauntlet import RiskCommittee

console = Console()

def run_cli():
    console.print(Panel.fit("[bold red]⚠️  RISK COMMITTEE CONVENED  ⚠️[/bold red]\nAutomated Strategy Validation Gauntlet", border_style="red"))

    # Mocking a candidate strategy submission from the Quant Research Desk
    strategy_name = "Cross-Sectional Momentum (60d Lookback)"
    observed_sr = 1.45  # The raw backtest Sharpe
    num_trials = 45     # The quant admits they tested 45 variations
    universe = ["AAPL", "MSFT", "NVDA", "TSLA", "AMD"]

    committee = RiskCommittee()

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Test Phase", style="dim")
    table.add_column("Status")
    table.add_column("Committee Notes")

    with Progress(console=console) as progress:
        task = progress.add_task("[cyan]Running Gauntlet...", total=3)

        results = committee.evaluate_strategy(strategy_name, observed_sr, num_trials, universe)

        for test in results["tests"]:
            time.sleep(0.8) # Dramatic effect
            status_str = "[bold green]PASS ✔[/bold green]" if test["status"] == "PASS" else "[bold red]FAIL ✘[/bold red]"
            table.add_row(test["name"], status_str, test["detail"])
            progress.advance(task)

    console.print(table)
    console.print("")

    if results["verdict"] == "APPROVED":
        console.print(Panel.fit("[bold green]✓ STRATEGY APPROVED FOR DEPLOYMENT[/bold green]\nCleared for Hive-Mind Autopilot integration.", border_style="green", title="VERDICT"))
    else:
        console.print(Panel.fit(f"[bold red]✘ STRATEGY REJECTED[/bold red]\nReason: {results['rejection_reason']}\nDo not deploy to live capital.", border_style="red", title="VERDICT"))

if __name__ == "__main__":
    run_cli()
