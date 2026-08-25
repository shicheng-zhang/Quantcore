"""Shared request/response models for the API routers."""
from typing import Annotated, Literal, List
from pydantic import BaseModel, Field


class BacktestRequest(BaseModel):
    universe: List[Annotated[str, Field(min_length=1, max_length=16)]]
    slippage_bps: Annotated[float, Field(ge=0, le=1_000)]
    lookback: Annotated[int, Field(ge=2, le=2_000)]


class PaperOrder(BaseModel):
    symbol: Annotated[str, Field(pattern=r"^[A-Za-z0-9._-]{1,16}$")]
    side: Literal["BUY", "SELL"]
    qty: Annotated[int, Field(gt=0, le=1_000_000)]
    algo: Literal["MARKET", "VWAP", "TWAP"]


class ExecutionRequest(BaseModel):
    symbol: Annotated[str, Field(pattern=r"^[A-Za-z0-9._-]{1,16}$")]
    shares: Annotated[int, Field(gt=0, le=10_000_000)]
    algo: Literal["MARKET", "VWAP", "TWAP"]


class SymbolRequest(BaseModel):
    symbol: Annotated[str, Field(pattern=r"^[A-Za-z0-9._-]{1,16}$")]


class GhostRequest(BaseModel):
    shares: Annotated[int, Field(gt=0, le=10_000_000)]
    volatility: Annotated[float, Field(gt=0, le=5)]


class GauntletRequest(BaseModel):
    strategy_name: str
    observed_sr: Annotated[float, Field(ge=-20, le=20)]
    num_trials: Annotated[int, Field(ge=1, le=1_000_000)]
    universe: List[str]


class AlpacaCreds(BaseModel):
    key_id: Annotated[str, Field(min_length=1, max_length=256)]
    secret_key: Annotated[str, Field(min_length=1, max_length=512)]
    base_url: Literal["https://paper-api.alpaca.markets"] = "https://paper-api.alpaca.markets"
