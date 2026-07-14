# QuantCore Releases

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
