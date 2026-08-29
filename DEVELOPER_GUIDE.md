# Developer Guide

## Repository layout

```
cpp/            C++ analytics core compiled into quantcore_cpp.so
nexus/          Standalone C++ HFT engine (nexus_core)
python/         The quantcore Python package
  quantcore/
    broker/     Paper + Alpaca brokers, DuckDB ledger
    data/       Provider fallback, seed guard
    portfolio/  HRP optimizer
    research/   Backtester, DSR, StatArb, alpha hunter
    risk/       Risk Committee gauntlet
    vol/        Black-Scholes, vol surface
    strategy/   Strategy base classes
    hivemind/   Python side of the IPC daemon
web/
  backend/      FastAPI app + routers
  templates/    Jinja2 pages
  static/       CSS/JS
config/         system.yaml
tests/          pytest suite
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
