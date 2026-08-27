"""Future fundamental confirmation contract (groundwork only — no implementation)."""
from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from .enums import DataQualityStatus, ProviderName


class FundamentalConfirmation(BaseModel):
    """Placeholder for future Sectors-native fundamental confirmation.

    In the groundwork pass, status is always UNCONFIRMED or UNAVAILABLE.
    """

    model_config = ConfigDict(extra="forbid")

    group_id: str
    as_of: date
    revenue_growth_breadth: Optional[float] = Field(default=None, description="% constituents with positive YoY revenue growth.")
    earnings_growth_breadth: Optional[float] = None
    profitability_signal: Optional[float] = None
    valuation_signal: Optional[float] = None
    report_freshness_days: Optional[int] = None
    status: DataQualityStatus = DataQualityStatus.FAILED
    source: ProviderName = ProviderName.SECTORS
    notes: Optional[str] = None
