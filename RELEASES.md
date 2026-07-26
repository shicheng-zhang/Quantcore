# QuantCore Releases
## v1.0.0-rc.4
**Status:** Release Candidate
**Highlights:**
- Phase 1 complete: monolithic main.py split into 7 modular API routers
- Data provider fallback: yfinance -> Stooq CSV (kills single point of failure)
- Structured logging: centralized logging_config.py replaces scattered print()
- Predictions endpoint hardened: dropna + isfinite guards + JSON sanitization
- CAGR total-loss guard: prevents complex number NaN on >100% drawdown
- Vol surface determinism: seeded RNG prevents chart flicker
- DSR overfit detection: bt-trials input wired to Risk Gauntlet num_trials
- Frontend fixes: edu drawer, nexus.html dead DOM refs
- Stub modules labeled EXPERIMENTAL in navigation
- Versioned config: config_version field in system.yaml
- Deleted all .bak files


## v1.0.0-beta.1 (Current)
**Status:** Shippable Beta
**Codename:** "First Light"

**Highlights:**
- C++20 HFT Core with SPSC queues and Ghost Exchange microstructure simulator.
- Python Research Brain (Polars, DuckDB, StatArb, HRP).
- FastAPI Dashboard with Bookmap, Risk Gauntlet, and Mini-Wiki.
- Alpaca Paper Trading integration.
- Pytest suite covering core math, broker fills, and validation metrics.
- Headless `quickstart.py` pipeline proving end-to-end data -> backtest -> risk flow.

**Known Limitations (Beta):**
- Alpaca integration is credential-only (not yet live-trading tested).
- WebSocket tape broadcasts paper fills only.
- `yfinance` is a single point of failure for historical data (no fallback API).
- `alt_data/`, `rl/`, and `nlp/` modules are currently stubs (return empty gracefully).
- C++ Nexus engine uses synthetic microstructure data when disconnected from live Binance feeds.
