# Developer Guide

## Repository layout

```
cpp/            C++ analytics core compiled into quantcore_cpp.so
nexus/          Standalone C++ HFT engine (nexus_core)
python/         The quantcore Python package
  quantcore/
    broker/     Paper + Alpaca brokers, DuckDB ledger (unified η=0.15)
    data/       Provider fallback, seed guard, tick_store (DuckDB ticks/bars_1m/tod_volume)
    portfolio/  HRP optimizer (inverse-variance)
    research/   Backtester (lagged), DSR (Lo T=n_obs), StatArb (β+α), alpha hunter (demeaned Pearson), prediction_suite (Wilder ATR, log OU)
    risk/       Risk Committee gauntlet (strategy-aware stress, relative friction)
    vol/        Black-Scholes (rho, vega/theta dual), vol surface
    strategy/   Strategy base classes
    hivemind/   Python side of IPC daemon (atomic double helpers)
    nlp/        VaderEngine score_with_confidence
    macro/      MacroEngine (synthetic, gated)
    day_trading/ IntradayEngine (RVOL/GAP/delta/VWAP bands/POC) + IntradaySignalEngine
 web/
  backend/      FastAPI app + routers (resilient state.init_state, Python fallback, 200 {error} not 500)
  templates/    Jinja2 pages (1.1 power UI: base, dashboard, day_trading, nexus)
  static/       CSS tokens --qc-* + JS command palette/hotkeys
 config/         system.yaml (risk intraday fields)
 tests/          pytest suite (covers DSR T, HRP inv-var, BS rho, ATR Wilder)
 scripts/        supervisor, seed, train, live entrypoints
```

## Build

The C++ components are built by `setup.sh`. To rebuild manually:

```bash
# Analytics core (pybind11 module)
mkdir -p build && cd build && cmake .. && make -j$(nproc)
cp quantcore_cpp*.so ../python/quantcore/quantcore_cpp.so

# Nexus engine
cd nexus && mkdir -p build && cd build && cmake .. && make -j$(nproc)
```

## Adding a market symbol

Use the dashboard (Add Symbol) or call `AnalyticsEngine.add_symbol()`. Data is fetched through the provider fallback and cached as parquet under `data/raw/equities/`.

## Adding an API endpoint

1. Choose the appropriate router under `web/backend/api/`.
2. Add the route. Use `state.<singleton>` for shared services, and `Depends(require_control_access)` for any endpoint that mutates trading or process state.
3. Offload blocking work with `asyncio.to_thread`.
4. Add a test under `tests/`.

## Adding a dashboard page

1. Create `web/templates/<page>.html` extending `base.html`.
2. Register a route in `web/backend/main.py` returning the template.
3. Add a nav link in `base.html`.

## Testing

```bash
pytest -q
```

Full stability gate (compile checks + syntax + tests):

```bash
bash scripts/verify_stability.sh
```

## Conventions

- Routers access shared services via `state.<name>` (never import the singleton directly).
- Keep changes modular; prefer extending routers and services over editing unrelated modules.
- Use the centralized logger (`get_logger(__name__)`), not `print()`.
- Avoid bare `except:`; catch `Exception` and log.
