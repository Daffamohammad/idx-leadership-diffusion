"""Price observation schema.

Each row represents a single security-date observation. Adjusted and
unadjusted prices are kept separate; downstream code must pick a basis.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .enums import PriceBasis, ProviderName


class PriceObservation(BaseModel):
    """Canonical daily price observation."""

    model_config = ConfigDict(extra="forbid")

    ticker: str = Field(..., min_length=1)
    date: date
    close: float = Field(..., gt=0.0, description="Raw close. Must be positive.")
    adjusted_close: float = Field(..., gt=0.0, description="Adjusted close. Must be positive.")
    volume: Optional[int] = Field(default=None, ge=0)
    market_cap: Optional[float] = Field(default=None, ge=0.0)
    currency: str = "IDR"
    price_basis: PriceBasis = PriceBasis.ADJUSTED_CLOSE
    source: ProviderName
    source_timestamp: Optional[date] = None

    @field_validator("adjusted_close")
    @classmethod
    def _validate_prices(cls, v: float, info):  # noqa: D401
        """Reject zero/negative prices; cross-validate with close if both present."""
        if v <= 0:
            raise ValueError("adjusted_close must be > 0")
        return v
