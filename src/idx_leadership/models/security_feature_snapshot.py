"""Per-security feature snapshot at a given date."""
from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from .enums import EligibilityStatus, PriceBasis


class SecurityFeatureSnapshot(BaseModel):
    """Computed features for a single security on a given snapshot date."""

    model_config = ConfigDict(extra="forbid")

    snapshot_date: date
    ticker: str

    # Returns in percent (e.g. 5.0 for +5%).
    return_5d: Optional[float] = None
    return_20d: Optional[float] = None
    return_60d: Optional[float] = None
    return_ytd: Optional[float] = None
    return_ytd_start_date: Optional[date] = None
    return_ytd_end_date: Optional[date] = None

    benchmark_return_5d: Optional[float] = None
    benchmark_return_20d: Optional[float] = None
    benchmark_return_60d: Optional[float] = None
    benchmark_return_ytd: Optional[float] = None

    # Excess returns in percent.
    excess_return_5d: Optional[float] = None
    excess_return_20d: Optional[float] = None
    excess_return_60d: Optional[float] = None
    excess_return_ytd: Optional[float] = None

    relative_strength_level: Optional[float] = None  # 20d excess return
    relative_strength_change: Optional[float] = None  # short - medium excess return (pp)

    volume_ratio: Optional[float] = None
    trend_above_ma20: Optional[bool] = None

    eligible: EligibilityStatus = EligibilityStatus.ELIGIBLE
    eligibility_reason: Optional[str] = None

    feature_version: str = "features-v1"
    price_basis: PriceBasis = PriceBasis.ADJUSTED_CLOSE
