# Contributing

Contributions are welcome. QuantCore is maintained as a community-driven portfolio piece and educational tool under the MIT License.

Please:

- Keep changes modular; prefer extending routers and services over editing unrelated modules.
- Write clear commit messages.
- Add tests where appropriate (`tests/`), and run `pytest -q` before submitting.
- Use the centralized logger instead of `print()`.
- Update documentation for user-visible changes.
- Be honest about what is real versus simulated — do not relabel a simulation as live data, or a heuristic as a learned model.

## Ground rules

- No real capital, no live-broker defaults. Paper-only.
- No credential persistence in the working tree.
- Runtime artifacts belong under `data/runtime/`, not in source control.
