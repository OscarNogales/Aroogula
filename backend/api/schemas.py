"""Pydantic request models used by the API routes."""

from __future__ import annotations

from typing import Any, Dict

from pydantic import BaseModel


class UpdateSettingsRequest(BaseModel):
    new_settings_dict: Dict[str, Any]


class ToggleCommand(BaseModel):
    turn_on: bool


class BuyRequest(BaseModel):
    ticker: str
    amount: float


class SellRequest(BaseModel):
    trade_id: str


class EquityGraphRequest(BaseModel):
    time: str = "max"


class TickerGraphRequest(BaseModel):
    ticker: str
    period: str
    mean: bool
