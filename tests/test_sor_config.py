from pathlib import Path
"""SOR routing split config.

The dark-pool fraction was a compile-time 0.30 in the C++ engine, which made the
lit/dark telemetry a structural constant — it read 70.1% forever regardless of
what the engine did. It is now a config value threaded through to the engine.
"""
import pytest

from python.quantcore.config import ExecutionConfig, QuantCoreConfig


def test_default_matches_the_legacy_constant():
    """Changing the default would silently re-route every existing deployment."""
    assert ExecutionConfig().dark_pool_pct == 0.30


@pytest.mark.parametrize("value", [0.0, 0.5, 1.0, 0.30])
def test_valid_values_accepted(value):
    assert ExecutionConfig(dark_pool_pct=value).dark_pool_pct == value


@pytest.mark.parametrize("value", [-0.1, 1.1, 7])
def test_out_of_range_rejected(value):
    with pytest.raises(Exception):
        ExecutionConfig(dark_pool_pct=value)


def test_yaml_round_trip(tmp_path):
    cfg_file = tmp_path / "system.yaml"
    cfg_file.write_text("execution:\n  dark_pool_pct: 0.45\n")

    from python.quantcore.config import load_config

    cfg = load_config(str(cfg_file))
    assert cfg.execution.dark_pool_pct == 0.45


def test_env_overrides_yaml(monkeypatch, tmp_path):
    cfg_file = tmp_path / "system.yaml"
    cfg_file.write_text("execution:\n  dark_pool_pct: 0.45\n")

    from python.quantcore.config import load_config

    monkeypatch.setenv("QUANTCORE_DARK_PCT", "0.15")
    assert load_config(str(cfg_file)).execution.dark_pool_pct == 0.15


def test_bad_env_value_raises_rather_than_silently_ignoring(monkeypatch, tmp_path):
    cfg_file = tmp_path / "system.yaml"
    cfg_file.write_text("execution:\n  dark_pool_pct: 0.45\n")

    from python.quantcore.config import load_config

    monkeypatch.setenv("QUANTCORE_DARK_PCT", "nonsense")
    with pytest.raises(ValueError, match="not a number"):
        load_config(str(cfg_file))


def test_absent_execution_section_uses_default(tmp_path):
    cfg_file = tmp_path / "system.yaml"
    cfg_file.write_text("config_version: 1\n")

    from python.quantcore.config import load_config

    cfg = load_config(str(cfg_file))
    assert cfg.execution.dark_pool_pct == 0.30
    assert isinstance(cfg, QuantCoreConfig)


def test_supervisor_passes_the_split_to_the_engine(monkeypatch, tmp_path):
    """The env var only matters if the child process actually receives it."""
    import importlib.util
    import sys

    monkeypatch.chdir(tmp_path)
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "system.yaml").write_text("execution:\n  dark_pool_pct: 0.42\n")
    monkeypatch.delenv("QUANTCORE_DARK_PCT", raising=False)
    monkeypatch.syspath_prepend(str(tmp_path.parent))

    repo_root = Path(__file__).resolve().parent.parent
    spec = importlib.util.spec_from_file_location("supervisor", repo_root / "python" / "scripts" / "supervisor.py")
    supervisor = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(supervisor)

    env = supervisor.service_env()
    assert env["QUANTCORE_DARK_PCT"] == "0.42"


def test_supervisor_survives_bad_engine(monkeypatch, tmp_path):
    """A broken config must not stop the stack from starting."""
    import importlib.util

    monkeypatch.chdir(tmp_path)
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "system.yaml").write_text("execution:\n  dark_pool_pct: not-a-number\n")
    monkeypatch.delenv("QUANTCORE_DARK_PCT", raising=False)
    monkeypatch.syspath_prepend(str(tmp_path.parent))

    repo_root = Path(__file__).resolve().parent.parent
    spec = importlib.util.spec_from_file_location("supervisor_bad", repo_root / "python" / "scripts" / "supervisor.py")
    supervisor = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(supervisor)

    env = supervisor.service_env()
    assert "QUANTCORE_DARK_PCT" not in env  # engine default stands in
