"""What changed digest.

Produces a machine-readable summary of meaningful changes between two
snapshots. Each group appears at most once; events are bucketed by
materiality label.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from ..models import DiffusionState, MaterialityLabel, TransitionEvent


@dataclass
class ChangeDigest:
    as_of: Optional[str]
    previous: Optional[str]
    upgrades: list[dict] = field(default_factory=list)
    downgrades: list[dict] = field(default_factory=list)
    broadening: list[dict] = field(default_factory=list)
    narrowing: list[dict] = field(default_factory=list)
    new_leaders: list[dict] = field(default_factory=list)
    lost_leadership: list[dict] = field(default_factory=list)
    stable: list[dict] = field(default_factory=list)
    # Canonical v2 feed: one record per group, with all applicable
    # categories.  Legacy buckets above remain for older readers.
    events: list[dict] = field(default_factory=list)
    improving: list[dict] = field(default_factory=list)
    weakening: list[dict] = field(default_factory=list)
    contradictory_changes: list[dict] = field(default_factory=list)
    stable_leaders: list[dict] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_change_digest(
    transitions: list[TransitionEvent],
    *,
    as_of: Optional[str] = None,
    previous: Optional[str] = None,
) -> ChangeDigest:
    digest = ChangeDigest(as_of=as_of, previous=previous)
    for ev in transitions:
        categories = _categories(ev)
        record = {
            "group_id": ev.group_id,
            "group": ev.group_id,
            "previous_state": {
                "leadership": ev.previous_leadership_state.value,
                "diffusion": ev.previous_diffusion_state.value,
            },
            "current_state": {
                "leadership": ev.current_leadership_state.value,
                "diffusion": ev.current_diffusion_state.value,
            },
            "leadership_transition": ev.leadership_transition,
            "diffusion_transition": ev.diffusion_transition,
            "breadth_delta": ev.breadth_delta,
            "relative_strength_delta": ev.relative_strength_delta,
            "rank_delta": ev.rank_delta,
            "materiality_label": ev.materiality_label.value,
            "materiality_reason": ev.materiality_reason,
            "primary_evidence": list(ev.primary_evidence),
            "secondary_evidence": list(ev.secondary_evidence),
            "data_gaps": list(ev.data_gaps),
            "categories": categories,
            "contradictory": ev.contradictory,
        }
        digest.events.append(record)
        if ev.materiality_label == MaterialityLabel.NEW_LEADER:
            digest.new_leaders.append(record)
        elif ev.materiality_label == MaterialityLabel.LOSS_OF_LEADERSHIP:
            digest.lost_leadership.append(record)
        elif ev.materiality_label == MaterialityLabel.IMPROVING:
            digest.upgrades.append(record)
        elif ev.materiality_label == MaterialityLabel.DETERIORATING:
            digest.downgrades.append(record)
        elif ev.materiality_label == MaterialityLabel.BROADENING:
            digest.broadening.append(record)
        elif ev.materiality_label == MaterialityLabel.NARROWING:
            digest.narrowing.append(record)
        else:
            digest.stable.append(record)
        if "improving" in categories:
            digest.improving.append(record)
        if "weakening" in categories:
            digest.weakening.append(record)
        if "contradictory changes" in categories:
            digest.contradictory_changes.append(record)
        if "stable leaders" in categories:
            digest.stable_leaders.append(record)
    return digest


def _categories(ev: TransitionEvent) -> list[str]:
    categories: list[str] = []
    if ev.materiality_label == MaterialityLabel.NEW_LEADER:
        categories.append("new leaders")
    elif ev.materiality_label == MaterialityLabel.LOSS_OF_LEADERSHIP:
        categories.append("lost leadership")
    elif ev.materiality_label == MaterialityLabel.IMPROVING:
        categories.append("improving")
    elif ev.materiality_label == MaterialityLabel.DETERIORATING:
        categories.append("weakening")
    elif ev.materiality_label == MaterialityLabel.BROADENING:
        categories.append("broadening")
    elif ev.materiality_label == MaterialityLabel.NARROWING:
        categories.append("narrowing")

    # Secondary state changes are retained as categories on the same record,
    # rather than duplicating the group across the canonical feed.
    if (
        ev.current_diffusion_state == DiffusionState.BROADENING
        and ev.previous_diffusion_state != ev.current_diffusion_state
        and "broadening" not in categories
    ):
        categories.append("broadening")
    if (
        ev.current_diffusion_state == DiffusionState.NARROWING
        and ev.previous_diffusion_state != ev.current_diffusion_state
        and "narrowing" not in categories
    ):
        categories.append("narrowing")
    if ev.contradictory:
        categories.append("contradictory changes")
    if (
        ev.materiality_label == MaterialityLabel.STABLE
        and ev.current_leadership_state.value == "LEADING"
    ):
        categories.append("stable leaders")
    if not categories:
        categories.append("stable")
    return categories
