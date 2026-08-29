# Architecture

QuantCore is organized into six layers. Each can evolve independently, keeping research, execution, and presentation loosely coupled.

## Layers

1. **Data providers** — yfinance (primary) with automatic Stooq CSV fallback. A local parquet cache (`data/raw/equities/`) is the durable source of truth; the dashboard serves it when providers are unavailable.
2. **Storage** — DuckDB for the analytics database and the paper-broker ledger; parquet for cached market history; memory-mapped files for inter-process state.
3. **C++ computational core** — two engines:
   - `quantcore_cpp` (pybind11): DuckDB-backed data engine, vectorized feature engine, risk engine.
   - `nexus_core`: the HFT engine — a 2M-slot lock-free SPSC ring buffer, a price-keyed limit order book, microstructure simulation, an audit hash chain, and Binance WebSocket ingest.
4. **Python research layer** — backtester, HRP optimizer, Deflated Sharpe Ratio, StatArb crucible, alpha hunter, volatility desk, RL training.
5. **FastAPI backend** — seven routers (analytics, ws, infra, ops, execution, research, broker) mounted on one app, with shared state initialized in the lifespan.
6. **Dashboard / UI** — Jinja2 templates + Plotly, with a PRO/LEARN mode and an educational wiki drawer.

## Data flow

```
Market data
  -> provider (yfinance/Stooq) with local-cache fallback
  -> parquet cache + DuckDB
  -> feature generation (C++)
  -> strategy / research (Python)
  -> risk checks (C++)
  -> paper broker / execution
  -> dashboard + REST API
```

## Inter-process communication

The Hive-Mind bridge links Python and C++ through a packed 597-byte memory-mapped struct (`data/hivemind.dat`). Both sides verify the layout at startup: Python asserts each field offset, and the C++ header carries a matching `static_assert`. This catches struct drift before it causes silent corruption.

## Process management

A single local supervisor (`python/scripts/supervisor.py`) owns child PIDs for `web`, `nexus`, `hivemind`, and `surveillance`. The Infrastructure TUI terminates processes by exact PID rather than pattern-matching, so stopping one service never touches unrelated processes.

## Key directories

```
cpp/          C++ analytics core (pybind11 module)
nexus/        C++ HFT engine
python/       quantcore package (research, broker, data, strategies)
web/          FastAPI backend + templates + static assets
config/       system.yaml
data/         runtime data, caches, logs (gitignored)
tests/        pytest suite
```
