# Roadmap

## Version 1.2.1 — Current Stable Release
- Nexus C++ HFT engine: SPSC multi-producer concurrency hardening, zero-latency lock-free reads.
- Integrated regulatory surveillance kill-switch hook with auto-gating for pair trades & rebalances.
- Streamlined `MerkleLedger` audit logging with buffered open stream and in-memory size tracking.
- Bidirectional `GhostExchange` execution reality (BUY and SELL sides with realistic impact).
- Session-aware intraday risk engine and DuckDB tick store.
- Power UI 1.1 with command palette (`⌘K`), keyboard hotkeys, and density modes.

## Version 1.3
- RL execution: distill the trained PPO policy into the C++ execution header (replacing the hand-tuned surrogate).
- Real L2 order-book depth for the Nexus engine (currently synthetic Poisson flow + Binance trade ticks).
- CSRF protection on control-plane POST endpoints.
- Parameterized SQL throughout the DuckDB layer.
- Expanded documentation and test coverage.
- Continuous latency profiling and NUMA core affinity binding.

## Future
- Additional data providers and asset classes (fixed income, FX futures).
- Deeper broker integrations (Interactive Brokers, paper-first).
- Infrastructure and observability improvements.
