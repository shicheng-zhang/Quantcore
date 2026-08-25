# QuantCore Stability Plan

## Objective

No feature work until local operation is reproducible, data remains available
during provider failures, and child processes can be started and stopped
predictably.

## Delivery order

1. Validate configuration and isolate runtime state.
2. Use a single local supervisor for web/Nexus/optional daemons.
3. Make provider, cache, telemetry, and database failures explicit and safe.
4. Add an offline integration gate and run it before every release.

## Operating defaults

- Paper-only brokerage; no credential persistence.
- Local history is served before external live data.
- Automatic reseeding is off unless explicitly enabled.
- Runtime artifacts belong under `data/runtime/` and are not source inputs.
