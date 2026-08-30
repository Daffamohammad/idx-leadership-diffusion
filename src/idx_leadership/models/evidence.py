"""Evidence object for a group.

Designed to be consumable by future LLM narration layers and the
exploratory UI without further computation.
"""
from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from .enums import DiffusionState, DiffusionStateV2, LeadershipState, ProviderMode


class DataGapCategory(str, Enum):
    """Canonical data-gap categories shared by the brief contract and the UI.

    The set is frozen at v1. New categories require a versioned
    addition so the brief and the UI render the same labels.
    """

    FUNDAMENTALS = "FUNDAMENTALS"
    FOREIGN_FLOW = "FOREIGN_FLOW"
    BROKER_ACTIVITY = "BROKER_ACTIVITY"
    FREE_FLOAT = "FREE_FLOAT"
    TAXONOMY = "TAXONOMY"
    CORPORATE_ACTIONS = "CORPORATE_ACTIONS"
    BENCHMARK = "BENCHMARK"


class DataGapStatus(str, Enum):
    """Severity of a data gap as it appears in the brief.

    * ``DATA_GAP`` — source is not connected (live Sectors key absent).
    * ``NOT_INTEGRATED`` — known subsystem is intentionally out of scope.
    * ``NOT_APPLIED`` — methodologically excluded (e.g. equal-weight default).
    * ``PROTOTYPE`` — only non-authoritative prototype metadata is available.
    """

    DATA_GAP = "DATA_GAP"
    NOT_INTEGRATED = "NOT_INTEGRATED"
    NOT_APPLIED = "NOT_APPLIED"
    PROTOTYPE = "PROTOTYPE"
    STALE = "STALE"
    READY = "READY"


class DataGap(BaseModel):
    """One normalized data gap with a fixed category, status, and label.

    The brief contract and the UI both consume this structure.  Free-form
    strings are no longer accepted at the intelligence-contract boundary.
    """

    model_config = ConfigDict(extra="forbid")

    category: DataGapCategory
    status: DataGapStatus
    label: str
    note: Optional[str] = None

    def to_markdown_row(self) -> str:
        return f"- **{self.category.value.replace('_', ' ').title()}** — {self.label}"


class EvidenceRecord(BaseModel):
    """A single metric-anchored piece of evidence."""

    model_config = ConfigDict(extra="forbid")

    metric: str
    value: Any
    unit: str = ""
    direction: str = "neutral"  # "positive" | "negative" | "neutral"
    comment: Optional[str] = None


class LeadershipEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: LeadershipState
    previous_state: Optional[LeadershipState] = None
    persistence: int = Field(default=1, ge=1)


class DiffusionEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: str
    previous_state: Optional[str] = None
    breadth: Optional[float] = None
    breadth_delta: Optional[float] = None
    numerator: int = Field(default=0, ge=0)
    eligible_denominator: int = Field(default=0, ge=0)
    missing_count: int = Field(default=0, ge=0)
    total_count: int = Field(default=0, ge=0)


class ConcentrationEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str = "UNDEFINED"
    signed_attribution_status: str = "UNDEFINED"
    top1: Optional[float] = None
    top3: Optional[float] = None
    hhi: Optional[float] = None


class PerformanceEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    return_20d: Optional[float] = None
    excess_5d: Optional[float] = None
    excess_20d: Optional[float] = None
    excess_60d: Optional[float] = None


class ConfirmationEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fundamentals: str = "UNAVAILABLE"
    foreign_flow: str = "UNAVAILABLE"


class InvalidationCondition(BaseModel):
    """One deterministic screen-state invalidation rule.

    These are descriptive, not prescriptive.  They describe what would
    make the current screen interpretation no longer hold on the next
    refresh; they are not investment-thesis statements.
    """

    model_config = ConfigDict(extra="forbid")

    condition: str
    metric: str = ""
    threshold: Optional[str] = None
    rationale: str = ""


class ContradictionRecord(BaseModel):
    """One normalized contradiction between leadership and participation.

    The brief contract and the UI both consume this structure.  ``evidence``
    carries the human-readable screen text while ``metric`` remains the
    structured handle.
    """

    model_config = ConfigDict(extra="forbid")

    metric: str
    label: str
    severity: str = "WARNING"  # "WARNING" | "CRITICAL"
    evidence: Optional[str] = None


class GroupEvidence(BaseModel):
    """Structured evidence package for one group at one as-of date."""

    model_config = ConfigDict(extra="forbid")

    group_id: str
    group: Optional[str] = None
    taxonomy_path: list[str] = Field(default_factory=list)
    as_of: date
    provider_mode: ProviderMode = ProviderMode.PUBLIC_PROTOTYPE
    leadership_state: LeadershipState
    diffusion_state: DiffusionState
    diffusion_state_v2: Optional[DiffusionStateV2] = None
    # Optional only for deserializing legacy v1 evidence fixtures.  The
    # canonical builder always populates both nested objects.
    leadership: Optional[LeadershipEvidence] = None
    diffusion: Optional[DiffusionEvidence] = None
    concentration: ConcentrationEvidence = Field(default_factory=ConcentrationEvidence)
    performance: PerformanceEvidence = Field(default_factory=PerformanceEvidence)
    confirmation: ConfirmationEvidence = Field(default_factory=ConfirmationEvidence)
    evidence: list[EvidenceRecord] = Field(default_factory=list)
    contradictions: list[ContradictionRecord] = Field(default_factory=list)
    data_gaps: list[DataGap] = Field(default_factory=list)
    invalidation: list[InvalidationCondition] = Field(default_factory=list)
    method_version: str = "methodology-v1"
    contract_version: str = "intelligence-v1"
