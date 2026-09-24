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
            if client in TAPE_CLIENTS:
                TAPE_CLIENTS.remove(client)


def init_state():
    """Instantiate every singleton. Called once from the lifespan.
    
    Each singleton is wrapped to avoid one failure killing the whole app.
    Web UI must start even if C++ not built, network down, or DB locked.
    """
    global analytics, paper_broker, satellite_engine, time_machine, risk_committee
    global decay_monitor, macro_engine, day_trading_engine, intraday_bt
    global tactical_engine, alpaca_broker

    import traceback
    from python.quantcore.logging_config import get_logger
    _l = get_logger(__name__)

    def _safe(name, factory):
        try:
            inst = factory()
            _l.info(f"State {name} initialized")
            return inst
        except Exception as e:
            _l.error(f"State {name} failed to init: {e}\n{traceback.format_exc()}")
            # Return a stub so routers can still respond with error JSON instead of 500 crash
            return None

    # Lazy imports so ImportError in one module doesn't kill others
    def _import(path, cls):
        try:
            mod = __import__(path, fromlist=[cls])
            return getattr(mod, cls)
        except Exception as e:
            _l.error(f"Import {path}.{cls} failed: {e}")
            return None

    AnalyticsEngine = _import("web.backend.analytics", "AnalyticsEngine")
    PaperBroker = _import("python.quantcore.broker.paper_broker", "PaperBroker")
    SatelliteEngine = _import("python.quantcore.alt_data.satellite", "SatelliteEngine")
    TimeMachine = _import("python.quantcore.replay.time_machine", "TimeMachine")
    RiskCommittee = _import("python.quantcore.risk.gauntlet", "RiskCommittee")
    DecayMonitor = _import("python.quantcore.mlops.decay_monitor", "DecayMonitor")
    MacroEngine = _import("python.quantcore.macro.synthetic_macro", "MacroEngine")
    IntradayEngine = _import("python.quantcore.day_trading.intraday_engine", "IntradayEngine")
    IntradayBacktester = _import("python.quantcore.research.intraday_backtester", "IntradayBacktester")
    IntradaySignalEngine = _import("python.quantcore.day_trading.intraday_signals", "IntradaySignalEngine")
    AlpacaBroker = _import("python.quantcore.broker.alpaca_broker", "AlpacaBroker")

    analytics = _safe("analytics", lambda: AnalyticsEngine()) if AnalyticsEngine else None
    paper_broker = _safe("paper_broker", lambda: PaperBroker()) if PaperBroker else None
    satellite_engine = _safe("satellite_engine", lambda: SatelliteEngine()) if SatelliteEngine else None
    time_machine = _safe("time_machine", lambda: TimeMachine()) if TimeMachine else None
    risk_committee = _safe("risk_committee", lambda: RiskCommittee()) if RiskCommittee else None
    decay_monitor = _safe("decay_monitor", lambda: DecayMonitor()) if DecayMonitor else None
    macro_engine = _safe("macro_engine", lambda: MacroEngine()) if MacroEngine else None
    day_trading_engine = _safe("day_trading_engine", lambda: IntradayEngine()) if IntradayEngine else None
    intraday_bt = _safe("intraday_bt", lambda: IntradayBacktester()) if IntradayBacktester else None
    tactical_engine = _safe("tactical_engine", lambda: IntradaySignalEngine()) if IntradaySignalEngine else None
    alpaca_broker = _safe("alpaca_broker", lambda: AlpacaBroker()) if AlpacaBroker else None

    # If analytics failed, create a minimal stub so /api/* don't 500
    if analytics is None:
        class _StubAnalytics:
            def get_symbols(self): return []
            def get_overview(self): return {"total_symbols":0,"latest_prices":{},"system_status":"Degraded","last_update":""}
            def fetch_live_data(self, *a, **kw): raise ValueError("Analytics engine unavailable — check logs")
            def get_trend_analysis(self, *a, **kw): return {"error":"Analytics unavailable"}
            def get_predictions(self, *a, **kw): return {"error":"Analytics unavailable"}
            def get_advanced_predictions(self, *a, **kw): return {"error":"Analytics unavailable"}
            def get_prediction_review(self, *a, **kw): return {"error":"Analytics unavailable"}
            def get_prediction_screener(self, *a, **kw): return []
            def get_recent_signals(self): return []
            def get_performance_metrics(self): return {"message":"Unavailable"}
            def add_symbol(self, s): raise ValueError("Analytics unavailable")
            def remove_symbol(self, s): raise ValueError("Analytics unavailable")
        analytics = _StubAnalytics()
        _l.warning("Analytics stub active — web UI will stay up but data endpoints return errors")


def close_state():
    """Release persistent resources during FastAPI shutdown."""
    global analytics, paper_broker
    if paper_broker and getattr(paper_broker, "ledger", None):
        try:
            paper_broker.ledger.con.close()
        except Exception:
            pass
    analytics = None
    paper_broker = None
    TAPE_CLIENTS.clear()
