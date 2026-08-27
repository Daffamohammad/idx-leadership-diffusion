"""Benchmark observation schema."""
from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from .enums import PriceBasis, ProviderName


class BenchmarkObservation(BaseModel):
    """Canonical daily benchmark observation."""

    model_config = ConfigDict(extra="forbid")

    benchmark_id: str = Field(..., min_length=1, description="Provider-agnostic ID, e.g. IHSG.")
    date: date
    close: float = Field(..., gt=0.0)
    adjusted_close: Optional[float] = Field(default=None, gt=0.0)
    price_basis: PriceBasis = PriceBasis.CLOSE
    source: ProviderName
