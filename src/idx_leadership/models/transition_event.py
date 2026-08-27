"""Transition event between two observation dates."""
from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from .enums import DiffusionState, DiffusionStateV2, LeadershipState, MaterialityLabel


class TransitionEvent(BaseModel):
    """Records a meaningful change between two observation dates for one group."""

    model_config = ConfigDict(extra="forbid")

    current_date: date
    previous_date: Optional[date] = None

    taxonomy_level: str = "sector"
    group_id: str

    previous_leadership_state: LeadershipState = LeadershipState.UNCONFIRMED
    current_leadership_state: LeadershipState = LeadershipState.UNCONFIRMED

    previous_diffusion_state: DiffusionState = DiffusionState.UNCONFIRMED
    current_diffusion_state: DiffusionState = DiffusionState.UNCONFIRMED
    previous_diffusion_state_v2: Optional[DiffusionStateV2] = None
    current_diffusion_state_v2: Optional[DiffusionStateV2] = None
    diffusion_transition_v2: Optional[str] = None

    leadership_transition: Optional[str] = None
    diffusion_transition: Optional[str] = None

    breadth_delta: Optional[float] = None
    relative_strength_delta: Optional[float] = None
    rank_delta: Optional[int] = None

    materiality_label: MaterialityLabel = MaterialityLabel.STABLE
    materiality_reason: Optional[str] = None
    primary_evidence: list[str] = Field(default_factory=list)
    secondary_evidence: list[str] = Field(default_factory=list)
    data_gaps: list[str] = Field(default_factory=list)
    contradictory: bool = False

    transition_version: str = "transitions-v2"
