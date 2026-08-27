"""Transition event builder.

A transition compares two GroupSnapshots (current vs previous) and
produces a TransitionEvent including leadership/diffusion state
changes and a plain-text label.
"""
from __future__ import annotations

from datetime import date
from typing import Iterable, Optional

import pandas as pd

from ..models import (
    DiffusionState,
    GroupSnapshot,
    LeadershipState,
    MaterialityLabel,
    TransitionEvent,
)


def transition_label(prev, curr) -> Optional[str]:
    if prev is None or curr is None:
        return None
    if prev == curr:
        return None
    return f"{prev.value if hasattr(prev, 'value') else prev} -> {curr.value if hasattr(curr, 'value') else curr}"


def compute_transition(
    *,
    current: GroupSnapshot,
    previous: Optional[GroupSnapshot],
    materiality_breadth_delta_pp: float = 10.0,
    materiality_excess_delta_pp: float = 1.5,
    materiality_rank_delta_min: int = 3,
) -> TransitionEvent:
    """Compute a transition event from current vs previous GroupSnapshot."""
    if previous is None:
        return TransitionEvent(
            current_date=current.snapshot_date,
            previous_date=None,
            taxonomy_level=current.taxonomy_level,
            group_id=current.group_id,
            previous_leadership_state=LeadershipState.UNCONFIRMED,
            current_leadership_state=current.leadership_state,
            previous_diffusion_state=DiffusionState.UNCONFIRMED,
            current_diffusion_state=current.diffusion_state,
            previous_diffusion_state_v2=None,
            current_diffusion_state_v2=current.diffusion_state_v2,
            diffusion_transition_v2=None,
            leadership_transition=None,
            diffusion_transition=None,
            breadth_delta=current.breadth_delta,
            relative_strength_delta=current.relative_strength_level,
            rank_delta=None,
            materiality_label=MaterialityLabel.STABLE,
            materiality_reason="no previous snapshot",
        )
    bd = current.breadth_delta
    if (
        bd is None
        and current.breadth_outperforming is not None
        and previous.breadth_outperforming is not None
    ):
        bd = float(current.breadth_outperforming) - float(previous.breadth_outperforming)
    rd = None
    if current.relative_strength_level is not None and previous.relative_strength_level is not None:
        rd = float(current.relative_strength_level) - float(previous.relative_strength_level)
    rank_delta = None
    if current.leadership_rank is not None and previous.leadership_rank is not None:
        rank_delta = int(previous.leadership_rank) - int(current.leadership_rank)  # positive = improved
    label, reason = _classify_materiality(
        prev_lead=previous.leadership_state,
        curr_lead=current.leadership_state,
        prev_diff=previous.diffusion_state,
        curr_diff=current.diffusion_state,
        breadth_delta=bd,
        excess_delta=rd,
        rank_delta=rank_delta,
        materiality_breadth_delta_pp=materiality_breadth_delta_pp,
        materiality_excess_delta_pp=materiality_excess_delta_pp,
        materiality_rank_delta_min=materiality_rank_delta_min,
    )
    primary, secondary = _materiality_evidence(
        leadership_transition=transition_label(previous.leadership_state, current.leadership_state),
        diffusion_transition=transition_label(previous.diffusion_state, current.diffusion_state),
        breadth_delta=bd,
        excess_delta=rd,
        rank_delta=rank_delta,
        breadth_threshold=materiality_breadth_delta_pp,
        excess_threshold=materiality_excess_delta_pp,
        rank_threshold=materiality_rank_delta_min,
    )
    contradictory = (
        current.leadership_state == LeadershipState.LEADING
        and current.diffusion_state == DiffusionState.NARROWING
    )
    return TransitionEvent(
        current_date=current.snapshot_date,
        previous_date=previous.snapshot_date,
        taxonomy_level=current.taxonomy_level,
        group_id=current.group_id,
        previous_leadership_state=previous.leadership_state,
        current_leadership_state=current.leadership_state,
        previous_diffusion_state=previous.diffusion_state,
        current_diffusion_state=current.diffusion_state,
        previous_diffusion_state_v2=previous.diffusion_state_v2,
        current_diffusion_state_v2=current.diffusion_state_v2,
        diffusion_transition_v2=transition_label(
            previous.diffusion_state_v2,
            current.diffusion_state_v2,
        ),
        leadership_transition=transition_label(previous.leadership_state, current.leadership_state),
        diffusion_transition=transition_label(previous.diffusion_state, current.diffusion_state),
        breadth_delta=bd,
        relative_strength_delta=rd,
        rank_delta=rank_delta,
        materiality_label=label,
        materiality_reason=reason,
        primary_evidence=primary,
        secondary_evidence=secondary,
        contradictory=contradictory,
    )


def build_transition_events(
    *,
    current: Iterable[GroupSnapshot],
    previous_by_group: dict[str, GroupSnapshot],
    materiality_breadth_delta_pp: float = 10.0,
    materiality_excess_delta_pp: float = 1.5,
    materiality_rank_delta_min: int = 3,
) -> list[TransitionEvent]:
    out: list[TransitionEvent] = []
    for c in current:
        prev = previous_by_group.get(c.group_id)
        out.append(
            compute_transition(
                current=c,
                previous=prev,
                materiality_breadth_delta_pp=materiality_breadth_delta_pp,
                materiality_excess_delta_pp=materiality_excess_delta_pp,
                materiality_rank_delta_min=materiality_rank_delta_min,
            )
        )
    return out


def _classify_materiality(
    *,
    prev_lead: LeadershipState,
    curr_lead: LeadershipState,
    prev_diff: DiffusionState,
    curr_diff: DiffusionState,
    breadth_delta: Optional[float],
    excess_delta: Optional[float],
    rank_delta: Optional[int],
    materiality_breadth_delta_pp: float,
    materiality_excess_delta_pp: float,
    materiality_rank_delta_min: int,
) -> tuple[MaterialityLabel, str]:
    breadth_material = (
        breadth_delta is not None
        and abs(float(breadth_delta)) >= materiality_breadth_delta_pp
    )
    excess_material = (
        excess_delta is not None
        and abs(float(excess_delta)) >= materiality_excess_delta_pp
    )
    rank_material = (
        rank_delta is not None and abs(int(rank_delta)) >= materiality_rank_delta_min
    )
    corroborated = breadth_material or excess_material or rank_material

    # A categorical state change alone is not material.  It must be
    # corroborated by breadth, relative-strength, or rank movement.
    if prev_lead in (LeadershipState.LEADING, LeadershipState.IMPROVING) and curr_lead in (
        LeadershipState.LAGGING,
        LeadershipState.WEAKENING,
        LeadershipState.UNCONFIRMED,
    ) and corroborated:
        return MaterialityLabel.LOSS_OF_LEADERSHIP, f"leadership {prev_lead.value} -> {curr_lead.value}"
    # New leader
    if (
        prev_lead in (LeadershipState.LAGGING, LeadershipState.WEAKENING, LeadershipState.UNCONFIRMED)
        and curr_lead == LeadershipState.LEADING
        and corroborated
    ):
        return MaterialityLabel.NEW_LEADER, f"leadership {prev_lead.value} -> {curr_lead.value}"
    # Broadening
    if prev_diff != curr_diff and curr_diff == DiffusionState.BROADENING and corroborated:
        return MaterialityLabel.BROADENING, f"diffusion {prev_diff.value} -> {curr_diff.value}"
    # Narrowing
    if prev_diff != curr_diff and curr_diff == DiffusionState.NARROWING and corroborated:
        return MaterialityLabel.NARROWING, f"diffusion {prev_diff.value} -> {curr_diff.value}"
    # Improving leadership (no new leader)
    if curr_lead == LeadershipState.IMPROVING and prev_lead != LeadershipState.IMPROVING and corroborated:
        return MaterialityLabel.IMPROVING, f"leadership {prev_lead.value} -> {curr_lead.value}"
    # Deteriorating
    if curr_lead in (LeadershipState.WEAKENING, LeadershipState.LAGGING) and prev_lead in (
        LeadershipState.LEADING,
        LeadershipState.IMPROVING,
    ) and corroborated:
        return MaterialityLabel.DETERIORATING, f"leadership {prev_lead.value} -> {curr_lead.value}"
    # Material breadth move
    if breadth_delta is not None and abs(breadth_delta) >= materiality_breadth_delta_pp:
        if breadth_delta > 0:
            return MaterialityLabel.BROADENING, f"breadth_delta={breadth_delta:.1f}pp"
        return MaterialityLabel.NARROWING, f"breadth_delta={breadth_delta:.1f}pp"
    # Material excess return move
    if excess_delta is not None and abs(excess_delta) >= materiality_excess_delta_pp:
        if excess_delta > 0:
            return MaterialityLabel.IMPROVING, f"excess_return_delta={excess_delta:.2f}pp"
        return MaterialityLabel.DETERIORATING, f"excess_return_delta={excess_delta:.2f}pp"
    if rank_delta is not None and abs(rank_delta) >= materiality_rank_delta_min:
        if rank_delta > 0:
            return MaterialityLabel.IMPROVING, f"rank_delta={rank_delta:+d}"
        return MaterialityLabel.DETERIORATING, f"rank_delta={rank_delta:+d}"
    if prev_lead != curr_lead or prev_diff != curr_diff:
        return MaterialityLabel.STABLE, "state changed without corroborating material move"
    return MaterialityLabel.STABLE, "no material change"


def _materiality_evidence(
    *,
    leadership_transition: str | None,
    diffusion_transition: str | None,
    breadth_delta: float | None,
    excess_delta: float | None,
    rank_delta: int | None,
    breadth_threshold: float,
    excess_threshold: float,
    rank_threshold: int,
) -> tuple[list[str], list[str]]:
    categorical = [
        value
        for value in (leadership_transition, diffusion_transition)
        if value is not None
    ]
    quantitative: list[str] = []
    if breadth_delta is not None and abs(breadth_delta) >= breadth_threshold:
        quantitative.append(f"breadth {breadth_delta:+.1f}pp")
    if excess_delta is not None and abs(excess_delta) >= excess_threshold:
        quantitative.append(f"relative strength {excess_delta:+.2f}pp")
    if rank_delta is not None and abs(rank_delta) >= rank_threshold:
        quantitative.append(f"rank {rank_delta:+d}")
    primary = quantitative[:1] or categorical[:1]
    secondary = quantitative[1:] + categorical
    if primary and primary[0] in secondary:
        secondary.remove(primary[0])
    return primary, secondary
