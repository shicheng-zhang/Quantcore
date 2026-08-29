# Roadmap

## Version 1.0 — released

First stable public release. Stability, correctness, and transparency hardening complete. See `RELEASES.md`.

## Version 1.1

- RL execution: distill the trained PPO policy into the C++ execution header (replacing the hand-tuned surrogate).
- Real L2 order-book depth for the Nexus engine (currently synthetic flow + trade ticks).
- CSRF protection on control-plane POST endpoints.
- Parameterized SQL throughout the DuckDB layer.
- Expanded documentation and test coverage.
- Performance tuning.

## Future

- Additional data providers and asset classes.
- Deeper broker integrations (paper-first).
- Infrastructure and observability improvements.
