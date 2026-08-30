"""Canonical security-master schema.

Provider-specific metadata is optional because providers expose different
depths of listing and liquidity information. Missing live fields remain
explicitly ``None`` rather than being filled from prototype assumptions.
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
    security_id: Optional[str] = None
    company_name: Optional[str] = None
    exchange: Optional[str] = None
    country: Optional[str] = "ID"
    sector: Optional[str] = Field(default=None, description="Coarse sector label (prototype).")
    subsector: Optional[str] = Field(default=None, description="Coarse subsector label (prototype).")
    industry: Optional[str] = None
    subindustry: Optional[str] = None
    group_id: Optional[str] = Field(default=None, description="Taxonomy group key used for aggregation.")
    listing_status: Optional[str] = None
    instrument_type: Optional[str] = None
    common_equity_status: Optional[str] = None
    # Default to "Main" because the vast majority of IDX listings are on
    # the Main board; explicitly `None` is reserved for sources that
    # distinguish delisted/pending tickers.
    listing_board: Optional[str] = "Main"
    active: bool = True
    benchmark_flag: bool = False
    listing_date: Optional[date] = None
    first_trade_date: Optional[date] = None
    last_trade_date: Optional[date] = None
    market_cap: Optional[float] = None
    free_float: Optional[float] = None
    average_daily_value: Optional[float] = None
    source: ProviderName
    source_as_of: Optional[date] = None
