"""Security master schema.

Note: the prototype uses a locally-declared coarse taxonomy. Missing
values remain explicit (None) rather than fabricated.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from .enums import ProviderName


class SecurityMasterEntry(BaseModel):
    """Canonical security master row."""

    model_config = ConfigDict(extra="forbid", frozen=False)

    ticker: str = Field(..., min_length=1, description="Canonical ticker (e.g. BBCA.JK).")
    vendor_ticker: str = Field(..., min_length=1, description="Ticker as used by the provider.")
    company_name: Optional[str] = None
    exchange: Optional[str] = None
    country: Optional[str] = "ID"
    sector: Optional[str] = Field(default=None, description="Coarse sector label (prototype).")
    subsector: Optional[str] = Field(default=None, description="Coarse subsector label (prototype).")
    industry: Optional[str] = None
    subindustry: Optional[str] = None
    group_id: Optional[str] = Field(default=None, description="Taxonomy group key used for aggregation.")
    # Default to "Main" because the vast majority of IDX listings are on
    # the Main board; explicitly `None` is reserved for sources that
    # distinguish delisted/pending tickers.
    listing_board: Optional[str] = "Main"
    active: bool = True
    benchmark_flag: bool = False
    source: ProviderName
    source_as_of: Optional[date] = None
