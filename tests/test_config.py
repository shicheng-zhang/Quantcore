from pathlib import Path
import pytest

from python.quantcore.config import load_config


def test_load_config_uses_validated_defaults(tmp_path):
    path = tmp_path / "system.yaml"
    path.write_text("config_version: 1\nsystem: {runtime_dir: data/runtime}\n")
    config = load_config(str(path))
    assert config.system.runtime_dir == "data/runtime"
    assert config.risk.max_drawdown_pct == 0.10


def test_load_config_rejects_invalid_risk_limit(tmp_path):
    path = tmp_path / "system.yaml"
    path.write_text("risk: {max_position_pct: 2}\n")
    with pytest.raises(Exception):
        load_config(str(path))
