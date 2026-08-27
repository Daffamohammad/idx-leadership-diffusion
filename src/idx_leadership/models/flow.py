"""Future flow confirmation contract (groundwork only — no implementation)."""
from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from .enums import DataQualityStatus, ProviderName


class FlowConfirmation(BaseModel):
    """Placeholder for future Sectors-native flow / broker confirmation."""

    model_config = ConfigDict(extra="forbid")

    ticker: str
    date_window: tuple[date, date]
    foreign_net_flow: Optional[float] = None
    foreign_flow_direction: Optional[str] = None
    broker_confirmation: Optional[str] = None
    status: DataQualityStatus = DataQualityStatus.FAILED
    source: ProviderName = ProviderName.SECTORS
    notes: Optional[str] = None
