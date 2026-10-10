#!/usr/bin/env python3
"""Small local supervisor for the QuantCore stack.

It owns child PIDs instead of matching and killing arbitrary system processes.
"""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / os.getenv("QUANTCORE_RUNTIME_DIR", "data/runtime")
STATE = RUNTIME / "supervisor.json"

COMMANDS = {
    "web": [sys.executable, "-m", "uvicorn", "web.backend.main:app", "--host", "127.0.0.1", "--port", "8765"],
    "nexus": [str(ROOT / "nexus/build/nexus_core")],
    "hivemind": [sys.executable, "-u", "python/quantcore/hivemind/quant_daemon.py"],
    "surveillance": [sys.executable, "-u", "python/quantcore/ops/surveillance_daemon.py"],
}


def read_state():
    try:
        return json.loads(STATE.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def save(state):
    RUNTIME.mkdir(parents=True, exist_ok=True)
    temporary = STATE.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, indent=2))
    temporary.replace(STATE)


def service_env():
    """Environment for child processes.

    Passes the SOR routing split from config/system.yaml into the C++ engine so
    the dark pool share is a setting an operator can change. Falls back to the
    engine default if config is missing or malformed — never blocks startup.
    """
    env = dict(os.environ)
    try:
        # The quantcore package lives under python/, not at the repo root.
        sys.path.insert(0, str(ROOT / "python"))
        from quantcore.config import load_config

        env["QUANTCORE_DARK_PCT"] = str(load_config().execution.dark_pool_pct)
    except Exception as exc:  # noqa: BLE001 - supervisor must stay usable
        print(f"supervisor: config not applied ({exc}); engine defaults in use")
    return env


def start(names):
    state = read_state()
    for name in names:
        if name not in COMMANDS:
            raise SystemExit(f"Unknown service: {name}")
        if name in state and alive(state[name]["pid"]):
            print(f"{name}: already running ({state[name]['pid']})")
            continue
        log = RUNTIME / f"{name}.log"
        with open(log, "a", encoding="utf-8") as output:
            process = subprocess.Popen(
                COMMANDS[name], cwd=ROOT, stdout=output, stderr=subprocess.STDOUT,
                start_new_session=True, env=service_env(),
            )
        state[name] = {"pid": process.pid, "started_at": time.time(), "command": COMMANDS[name]}
        print(f"{name}: started ({process.pid})")
    save(state)


def stop(names):
    state = read_state()
    for name in names:
        service = state.get(name)
        if service and alive(service["pid"]):
            os.killpg(service["pid"], signal.SIGTERM)
            print(f"{name}: stopped ({service['pid']})")
        state.pop(name, None)
    save(state)


def status():
    state = read_state()
    print(json.dumps({name: {**service, "running": alive(service["pid"])} for name, service in state.items()}, indent=2))


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("start", "stop", "status"))
    parser.add_argument("services", nargs="*", choices=tuple(COMMANDS))
    args = parser.parse_args(argv)
    services = args.services or list(COMMANDS)
    if args.action == "start":
        start(services)
    elif args.action == "stop":
        stop(services)
    else:
        status()


# Guarded so the module can be imported (and service_env tested) without
# argparse consuming the pytest command line.
if __name__ == "__main__":
    main()
