#!/usr/bin/env python3
"""
QuantCore Infrastructure TUI
DevOps & System Health Dashboard.
"""
import sys
import subprocess

def ensure_deps():
    try:
        import textual
        import psutil
    except ImportError:
        print("Installing TUI dependencies (textual, psutil)...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "textual", "psutil", "--break-system-packages", "-q"])

ensure_deps()

import os
import json
import time
import psutil
from pathlib import Path
from datetime import datetime

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Header, Footer, Static, Log, Button, Select, Rule
from textual.reactive import reactive
from textual import work

BASE_DIR = Path(__file__).parent.resolve()
DATA_DIR = BASE_DIR / "data"

def _supervisor(*args: str) -> None:
    """
    Route process control through the project supervisor instead of pkill -f.

    This avoids killing unrelated processes that merely match a command-line
    substring.
    """
    subprocess.run(
        [sys.executable, str(BASE_DIR / "python" / "scripts" / "supervisor.py"), *args],
        cwd=BASE_DIR,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )

def get_proc_status(search_term):
    for p in psutil.process_iter(['pid', 'cmdline']):
        try:
            cmdline = " ".join(p.info['cmdline'] or [])
            if search_term in cmdline:
                return "RUNNING", p.info['pid']
        except (psutil.NoSuchProcess, psutil.AccessDenied, TypeError):
            pass
    return "STOPPED", None


def _kill_matching(pattern: str) -> int:
    """Terminate processes whose cmdline contains `pattern` (matched by PID).

    Safer than `pkill -f`, and works whether the process was started by the
    TUI, the supervisor, or by hand. Returns the number terminated.
    """
    targets = []
    for proc in psutil.process_iter(["pid", "cmdline"]):
        try:
            cmdline = " ".join(proc.info["cmdline"] or [])
            if pattern in cmdline:
                targets.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied, TypeError):
            continue
    if not targets:
        return 0
    for proc in targets:
        try:
            proc.terminate()  # SIGTERM -> graceful shutdown
        except psutil.NoSuchProcess:
            pass
    _, alive = psutil.wait_procs(targets, timeout=3)
    for proc in alive:
        try:
            proc.kill()  # SIGKILL stragglers
        except psutil.NoSuchProcess:
            pass
    return len(targets)

class HealthWidget(Static):
    def on_mount(self) -> None:
        self.set_interval(2.0, self.update_health)

    def update_health(self) -> None:
        web_status, _ = get_proc_status("uvicorn web.backend.main:app")
        nexus_status, _ = get_proc_status("nexus_core")
        daemon_status, _ = get_proc_status("quant_daemon.py")
        surv_status, _ = get_proc_status("surveillance_daemon.py")

        def color(s): return "[green]RUNNING[/]" if s == "RUNNING" else "[red]STOPPED[/]"

        self.update(
            f"[b]Web UI (FastAPI):[/]  {color(web_status)}\n"
            f"[b]Nexus Core (C++):[/]  {color(nexus_status)}\n"
            f"[b]Quant Daemon:[/]     {color(daemon_status)}\n"
            f"[b]Surveillance:[/]     {color(surv_status)}"
        )

class TelemetryWidget(Static):
    def on_mount(self) -> None:
        self.set_interval(1.0, self.update_telemetry)

    def update_telemetry(self) -> None:
        nexus = {}
        hive = {}
        try:
            with open(DATA_DIR / "nexus_live.json") as f: nexus = json.load(f)
        except: pass
        try:
            with open(DATA_DIR / "hivemind_ui.json") as f: hive = json.load(f)
        except: pass

        eps = nexus.get("events_processed", 0)
        p99 = nexus.get("latency_ns_p99", 0)
        pair = f"{hive.get('assets', ['N/A'])[0]}/{hive.get('assets', ['N/A'])[1]}" if hive.get("active") else "IDLE"

        self.update(
            f"[b]Nexus Events:[/]   {eps:,}\n"
            f"[b]p99 Latency:[/]    {p99:.0f} ns\n"
            f"[b]Active Pair:[/]    {pair}\n"
            f"[b]C++ Slippage:[/]   ${hive.get('cpp_slippage', 0):.2f}"
        )

class LogViewer(Log):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.current_file = "nexus_core.log"
        self.last_size = 0

    def on_mount(self) -> None:
        self.set_interval(1.0, self.tail_log)

    def tail_log(self) -> None:
        path = DATA_DIR / self.current_file
        if not path.exists():
            return

        current_size = path.stat().st_size
        if current_size < self.last_size:
            self.clear()
            self.last_size = 0

        if current_size > self.last_size:
            with open(path, "r") as f:
                f.seek(self.last_size)
                new_lines = f.readlines()
                for line in new_lines:
                    self.write_line(line.strip())
                self.last_size = current_size
                self.scroll_end()

class InfraTUI(App):
    CSS = """
    Screen { layout: vertical; }
    .row { layout: horizontal; height: auto; }
    .panel { border: solid $primary; margin: 1; padding: 1; }
    #health { border: solid green; height: 6; }
    #telemetry { border: solid blue; height: 6; }
    .controls-row { height: 3; align: center middle; border: solid yellow; margin: 0 1; padding: 0 1; }
    #controls-global { border: solid red; }
    #log-container { height: 2fr; border: solid magenta; }
    #log-title { width: 15; content-align: center middle; }
    #log_select { width: 30; }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("k", "kill_switch", "KILL SWITCH"),
        ("a", "start_all", "Start All"),
        ("s", "stop_all", "Stop All"),
        ("w", "start_web", "Start Web"),
        ("1", "start_nexus", "Start Nexus"),
        ("2", "stop_nexus", "Stop Nexus"),
        ("3", "start_daemon", "Start Daemon"),
        ("c", "clear_logs", "Clear Logs"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(classes="row"):
            yield HealthWidget(classes="panel", id="health")
            yield TelemetryWidget(classes="panel", id="telemetry")

        with Horizontal(id="controls-web", classes="controls-row"):
            yield Button("Start Web UI [W]", variant="success", id="btn_start_web")
            yield Button("Stop Web UI", variant="warning", id="btn_stop_web")
            yield Button("Start Surveillance", variant="success", id="btn_start_surv")
            yield Button("Stop Surveillance", variant="warning", id="btn_stop_surv")

        with Horizontal(id="controls-core", classes="controls-row"):
            yield Button("Start Nexus [1]", variant="success", id="btn_start_nexus")
            yield Button("Stop Nexus [2]", variant="warning", id="btn_stop_nexus")
            yield Button("Start Daemon [3]", variant="success", id="btn_start_daemon")
            yield Button("Stop Daemon", variant="warning", id="btn_stop_daemon")

        with Horizontal(id="controls-global", classes="controls-row"):
            yield Button("🚀 START ENTIRE STACK [A]", variant="success", id="btn_start_all")
            yield Button("🛑 STOP ALL [S]", variant="warning", id="btn_stop_all")
            yield Button("☢️ KILL SWITCH [K]", variant="error", id="btn_kill")

        with Vertical(id="log-container", classes="panel"):
            with Horizontal():
                yield Static("[b]Live Logs:[/]", id="log-title")
                yield Select([
                    ("Nexus C++ Logs", "nexus_core.log"),
                    ("Quant Daemon Logs", "quant_daemon.log"),
                    ("Surveillance Logs", "surveillance.log"),
                    ("Web UI (Uvicorn)", "uvicorn.log"),
                ], value="nexus_core.log", id="log_select")
            yield LogViewer(id="log_viewer")

        yield Footer()

    # --- GLOBAL ACTIONS ---
    def action_start_all(self) -> None:
        self.action_start_web()
        self.action_start_surv()
        self.action_start_nexus()
        self.action_start_daemon()
        self.notify("🚀 ENTIRE STACK ENGAGED", severity="information")

    def action_stop_all(self) -> None:
        _kill_matching("uvicorn web.backend.main:app")
        _kill_matching("surveillance_daemon.py")
        _kill_matching("nexus_core")
        _kill_matching("quant_daemon.py")
        self.notify("🛑 ALL PROCESSES HALTED", severity="warning")

    def action_kill_switch(self) -> None:
        self.action_stop_all()
        self.notify("🚨 KILL SWITCH TRIGGERED — all processes halted 🚨", severity="error")

    # --- WEB & SURVEILLANCE ACTIONS ---
    def action_start_web(self) -> None:
        log_file = open(DATA_DIR / "uvicorn.log", "w")
        env = os.environ.copy()
        duckdb_lib_dir = str(BASE_DIR / "build" / "_deps" / "duckdb-build" / "src")
        qc_lib_dir = str(BASE_DIR / "python" / "quantcore")
        current_ld_path = env.get("LD_LIBRARY_PATH", "")
        env["LD_LIBRARY_PATH"] = f"{duckdb_lib_dir}:{qc_lib_dir}:{current_ld_path}"
        subprocess.Popen([sys.executable, "-m", "uvicorn", "web.backend.main:app", "--host", "127.0.0.1", "--port", "8765"],
                         cwd=BASE_DIR, stdout=log_file, stderr=subprocess.STDOUT, env=env)
        self.notify("Web UI Started (http://127.0.0.1:8765)")

    def action_stop_web(self) -> None:
        _kill_matching("uvicorn web.backend.main:app")
        self.notify("Web UI Stopped")

    def action_start_surv(self) -> None:
        subprocess.Popen([sys.executable, "-u", "python/quantcore/ops/surveillance_daemon.py"],
                         cwd=BASE_DIR, stdout=open(DATA_DIR / "surveillance.log", "w"), stderr=subprocess.STDOUT)
        self.notify("Surveillance Daemon Started")

    def action_stop_surv(self) -> None:
        _kill_matching("surveillance_daemon.py")
        self.notify("Surveillance Daemon Stopped")

    # --- CORE ACTIONS ---
    def action_start_nexus(self) -> None:
        subprocess.Popen(["stdbuf", "-oL", str(BASE_DIR / "nexus/build/nexus_core")],
                         cwd=BASE_DIR, stdout=open(DATA_DIR / "nexus_core.log", "w"), stderr=subprocess.STDOUT)
        self.notify("Nexus Core Engaged")

    def action_stop_nexus(self) -> None:
        _kill_matching("nexus_core")
        self.notify("Nexus Core Halted")

    def action_start_daemon(self) -> None:
        subprocess.Popen([sys.executable, "-u", "python/quantcore/hivemind/quant_daemon.py"],
                         cwd=BASE_DIR, stdout=open(DATA_DIR / "quant_daemon.log", "w"), stderr=subprocess.STDOUT)
        self.notify("Quant Daemon Started")

    def action_stop_daemon(self) -> None:
        _kill_matching("quant_daemon.py")
        self.notify("Quant Daemon Stopped")

    def action_clear_logs(self) -> None:
        for log in ["nexus_core.log", "quant_daemon.log", "surveillance.log", "uvicorn.log"]:
            open(DATA_DIR / log, "w").close()
        self.query_one(LogViewer).last_size = 0
        self.query_one(LogViewer).clear()
        self.notify("Logs Cleared")

    # --- EVENT HANDLERS ---
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_start_all": self.action_start_all()
        elif event.button.id == "btn_stop_all": self.action_stop_all()
        elif event.button.id == "btn_kill": self.action_kill_switch()
        elif event.button.id == "btn_start_web": self.action_start_web()
        elif event.button.id == "btn_stop_web": self.action_stop_web()
        elif event.button.id == "btn_start_surv": self.action_start_surv()
        elif event.button.id == "btn_stop_surv": self.action_stop_surv()
        elif event.button.id == "btn_start_nexus": self.action_start_nexus()
        elif event.button.id == "btn_stop_nexus": self.action_stop_nexus()
        elif event.button.id == "btn_start_daemon": self.action_start_daemon()
        elif event.button.id == "btn_stop_daemon": self.action_stop_daemon()

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "log_select":
            viewer = self.query_one(LogViewer)
            viewer.current_file = event.value
            viewer.last_size = 0
            viewer.clear()

if __name__ == "__main__":
    InfraTUI().run()
