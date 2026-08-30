"""Snapshot manifest and entry schemas."""
from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from .enums import DataQualityStatus, PriceBasis, ProviderMode, ProviderName


class ManifestEntry(BaseModel):
    """One row per snapshot stored in data/snapshots/."""

    model_config = ConfigDict(extra="forbid")

    snapshot_id: str
    snapshot_date: date
    as_of: date
    provider: ProviderName
    provider_mode: Optional[ProviderMode] = None
    # None remains valid for legacy readability; strict compatibility rejects
    # manifests that do not carry the effective calculation basis.
    price_basis: Optional[PriceBasis] = None
    market_date: Optional[date] = None
    benchmark_date: Optional[date] = None
    universe_version: str
    taxonomy_version: str
    eligibility_version: str = "eligibility-v1"
    method_version: str
    feature_version: str
    leadership_version: str = "leadership-v1"
    diffusion_version: str = "diffusion-v1"
    concentration_version: str = "concentration-v1"
    schema_version: str = "schemas-v1"
    snapshot_version: str = "snapshot-v1"
    coverage_status: DataQualityStatus
    coverage_pct: float = Field(default=0.0, ge=0.0, le=100.0)
    created_at: date
    notes: Optional[str] = None
    # Eligible ticker set hash for membership parity checks across
    # snapshots. Two snapshots with different eligible ticker sets
    # (e.g., 500 of 962 vs the full 962) must not be treated as
    # comparable even if the version stamps match.
    eligible_ticker_set_hash: Optional[str] = None
    eligible_ticker_count: int = Field(default=0, ge=0)
    raw_ticker_count: int = Field(default=0, ge=0)


class SnapshotManifest(BaseModel):
    """Aggregated manifest of all stored snapshots."""

    model_config = ConfigDict(extra="forbid")

    snapshot_count: int = Field(default=0, ge=0)
    first_date: Optional[date] = None
    latest_date: Optional[date] = None
    provider: ProviderName
    provider_mode: Optional[ProviderMode] = None
    price_basis: Optional[PriceBasis] = None
    universe_version: str
    taxonomy_version: str
    eligibility_version: str = "eligibility-v1"
    method_version: str
    feature_version: str
    leadership_version: str = "leadership-v1"
    diffusion_version: str = "diffusion-v1"
    concentration_version: str = "concentration-v1"
    schema_version: str = "schemas-v1"
    snapshot_version: str = "snapshot-v1"
    entries: list[ManifestEntry] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
