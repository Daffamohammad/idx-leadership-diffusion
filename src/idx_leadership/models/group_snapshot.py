"""Group-level snapshot schema.

Groups are taxonomy-driven. In prototype runs, group_id is the coarse
sector label (e.g. 'Financials'); credentialed Sectors runs provide the
authoritative mapping through the same contract.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from .enums import DiffusionState, DiffusionStateV2, LeadershipState, MaterialityLabel


class ConcentrationMetrics(BaseModel):
    """Concentration diagnostics for a group."""

    model_config = ConfigDict(extra="forbid")

    top1_contribution_share: Optional[float] = Field(
        default=None, ge=0.0, le=1.0, description="Share of group absolute move from the top contributor."
    )
    top3_contribution_share: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    top5_contribution_share: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    top1_signed_share: Optional[float] = Field(
        default=None,
        description="Signed share of net move attributable to the largest absolute contributor (NOT the largest signed contributor; may be negative).",
    )
    top3_signed_share: Optional[float] = Field(
        default=None,
        description="Signed share of net move attributable to the three largest absolute contributors.",
    )
    hhi_contribution: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    contributor_count: int = Field(default=0, ge=0)
    convention: str = "absolute_move"
    status: str = "UNDEFINED"
    signed_attribution_status: str = "UNDEFINED"


class GroupSnapshot(BaseModel):
    """A complete analytical view of one group on one date."""

    model_config = ConfigDict(extra="ignore")

    snapshot_date: date

    taxonomy_level: str = "sector"
    taxonomy_path: list[str] = Field(default_factory=list)
    group_id: str
    group_name: Optional[str] = None

    constituent_count: int = Field(default=0, ge=0)
    eligible_count: int = Field(default=0, ge=0)
    missing_count: int = Field(default=0, ge=0)
    # Raw candidate count: all members in the raw taxonomy for this group,
    # including policy-excluded members. Tracked separately for disclosure.
    raw_candidate_count: int = Field(default=0, ge=0)
    # Policy-eligible count: members that passed all policy checks
    # (suspension, delisting, board, taxonomy, liquidity). This is the
    # denominator for the 60% coverage gate.
    policy_eligible_count: int = Field(default=0, ge=0)
    # Acquisition-failed count: members where the provider request failed
    # (429, network, etc.). These remain in the policy-eligible denominator
    # as missing data.
    acquisition_failed_count: int = Field(default=0, ge=0)

    # Group returns in percent.
    group_return_equal_weight: Optional[float] = None
    group_excess_return: Optional[float] = None
    group_excess_return_5d: Optional[float] = None
    group_excess_return_20d: Optional[float] = None
    group_excess_return_60d: Optional[float] = None
    group_return_ytd: Optional[float] = None
    group_excess_return_ytd: Optional[float] = None
    benchmark_return_ytd: Optional[float] = None
    ytd_start_date: Optional[date] = None
    ytd_eligible_count: int = Field(default=0, ge=0)

    # Internal helper for transition math. Kept in the model so callers
    # can use snapshots interchangeably; not serialized in the canonical
    # output table.
    relative_strength_level: Optional[float] = None

    # Breadth (0-100 scale).
    breadth_positive: Optional[float] = None
    breadth_outperforming: Optional[float] = None
    breadth_delta: Optional[float] = None
    breadth_total_count: int = Field(default=0, ge=0)
    breadth_eligible_count: int = Field(default=0, ge=0)
    breadth_missing_count: int = Field(default=0, ge=0)
    breadth_positive_count: int = Field(default=0, ge=0)
    breadth_outperforming_count: int = Field(default=0, ge=0)
    breadth_improving_count: int = Field(default=0, ge=0)
    # Eligible and outperforming ticker sets back the paired breadth
    # comparison: deltas use identical names at both dates. Snapshots
    # written before these sets use the legacy unpaired subtraction.
    breadth_eligible_tickers: list[str] = Field(default_factory=list)
    breadth_outperforming_tickers: list[str] = Field(default_factory=list)

    concentration: ConcentrationMetrics = Field(default_factory=ConcentrationMetrics)

    leadership_state: LeadershipState = LeadershipState.UNCONFIRMED
    diffusion_state: DiffusionState = DiffusionState.UNCONFIRMED
    # Keep the v1 projection for compatibility while exposing the richer
    # group-size-aware v2 state on new snapshots.
    diffusion_state_v2: Optional[DiffusionStateV2] = None

    leadership_rank: Optional[int] = Field(default=None, ge=1)
    change_rank: Optional[int] = Field(default=None, ge=1)

    # Counts include the current observation.  A newly observed state has
    # persistence=1, which is the human-readable convention used by the UI.
    leadership_persistence: int = Field(default=1, ge=1)
    diffusion_persistence: int = Field(default=1, ge=1)

    method_version: str = "methodology-v1"
    feature_version: str = "features-v1"
    last_materiality: MaterialityLabel = MaterialityLabel.STABLE
