"""Shared request/response models for the API routers."""
from pydantic import BaseModel
from typing import List


class BacktestRequest(BaseModel):
    universe: List[str]
    slippage_bps: float
    lookback: int


class PaperOrder(BaseModel):
    symbol: str
    side: str
    qty: int
    algo: str


class ExecutionRequest(BaseModel):
    symbol: str
    shares: int
    algo: str


class SymbolRequest(BaseModel):
    symbol: str


class GhostRequest(BaseModel):
    shares: int
    volatility: float


class GauntletRequest(BaseModel):
    strategy_name: str
    observed_sr: float
    num_trials: int
    universe: List[str]


class AlpacaCreds(BaseModel):
    key_id: str
    secret_key: str
    base_url: str = "https://paper-api.alpaca.markets"
