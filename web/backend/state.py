"""Shared application state.

Singletons are created in `init_state()` (called from the FastAPI lifespan,
which runs in the worker process only — this preserves the Uvicorn-reloader
DuckDB-lock safety that paper_broker/analytics already relied on).

Routers MUST access these as attributes (`state.analytics`), NEVER via
`from .state import analytics` — the latter binds the value at import time,
when it is still None. Attribute access resolves at call time, after init.
"""
import asyncio

# --- Singletons (populated by init_state) ---
analytics = None
paper_broker = None
satellite_engine = None
time_machine = None
risk_committee = None
decay_monitor = None
macro_engine = None
day_trading_engine = None
intraday_bt = None
tactical_engine = None
alpaca_broker = None

# --- WebSocket trade tape ---
TAPE_CLIENTS = []


async def broadcast_tape(data):
    for client in list(TAPE_CLIENTS):
        try:
            await client.send_json(data)
        except Exception:
            pass


def init_state():
    """Instantiate every singleton. Called once from the lifespan."""
    global analytics, paper_broker, satellite_engine, time_machine, risk_committee
    global decay_monitor, macro_engine, day_trading_engine, intraday_bt
    global tactical_engine, alpaca_broker

    from .analytics import AnalyticsEngine
    from python.quantcore.broker.paper_broker import PaperBroker
    from python.quantcore.alt_data.satellite import SatelliteEngine
    from python.quantcore.replay.time_machine import TimeMachine
    from python.quantcore.risk.gauntlet import RiskCommittee
    from python.quantcore.mlops.decay_monitor import DecayMonitor
    from python.quantcore.macro.synthetic_macro import MacroEngine
    from python.quantcore.day_trading.intraday_engine import IntradayEngine
    from python.quantcore.research.intraday_backtester import IntradayBacktester
    from python.quantcore.day_trading.intraday_signals import IntradaySignalEngine
    from python.quantcore.broker.alpaca_broker import AlpacaBroker

    analytics = AnalyticsEngine()
    paper_broker = PaperBroker()
    satellite_engine = SatelliteEngine()
    time_machine = TimeMachine()
    risk_committee = RiskCommittee()
    decay_monitor = DecayMonitor()
    macro_engine = MacroEngine()
    day_trading_engine = IntradayEngine()
    intraday_bt = IntradayBacktester()
    tactical_engine = IntradaySignalEngine()
    alpaca_broker = AlpacaBroker()
