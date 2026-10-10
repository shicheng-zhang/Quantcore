"""Validated, side-effect-free system configuration."""
from pathlib import Path
import os
import yaml
from pydantic import BaseModel, Field


class SystemConfig(BaseModel):
    database_path: str = "data/analytics.db"
    runtime_dir: str = "data/runtime"


class DataConfig(BaseModel):
    parquet_views: dict[str, str] = Field(default_factory=dict)
    prefer_live_data: bool = False


class RiskConfig(BaseModel):
    max_position_pct: float = Field(default=0.05, gt=0, le=1)
    max_daily_loss_pct: float = Field(default=0.03, gt=0, le=1)
    max_drawdown_pct: float = Field(default=0.10, gt=0, le=1)


class ExecutionConfig(BaseModel):
    """Routing split for the Nexus Smart Order Router.

    The dark-pool fraction is a real setting rather than a hardcoded 0.30 so the
    lit/dark telemetry is a measurement instead of a constant that reads the
    same forever.
    """

    dark_pool_pct: float = Field(default=0.30, ge=0.0, le=1.0)


class QuantCoreConfig(BaseModel):
    config_version: int = 1
    system: SystemConfig = Field(default_factory=SystemConfig)
    data: DataConfig = Field(default_factory=DataConfig)
    risk: RiskConfig = Field(default_factory=RiskConfig)
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)


def load_config(path: str = "config/system.yaml") -> QuantCoreConfig:
    with open(path, encoding="utf-8") as file:
        config = QuantCoreConfig.model_validate(yaml.safe_load(file) or {})
    # Environment overrides are explicit, useful for local operations, and do
    # not mutate the checked-in YAML file.
    if os.getenv("QUANTCORE_RUNTIME_DIR"):
        config.system.runtime_dir = os.environ["QUANTCORE_RUNTIME_DIR"]
    if os.getenv("QUANTCORE_PREFER_LIVE_DATA"):
        config.data.prefer_live_data = os.environ["QUANTCORE_PREFER_LIVE_DATA"].lower() in {"1", "true", "yes"}
    # Environment wins over the YAML so an operator can re-route without
    # editing the checked-in file.
    if os.getenv("QUANTCORE_DARK_PCT"):
        try:
            config.execution.dark_pool_pct = float(os.environ["QUANTCORE_DARK_PCT"])
        except ValueError as e:
            raise ValueError(
                f"QUANTCORE_DARK_PCT={os.environ['QUANTCORE_DARK_PCT']!r} is not a number"
            ) from e
    return config


def runtime_path(config: QuantCoreConfig, name: str) -> Path:
    path = Path(config.system.runtime_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path / name
