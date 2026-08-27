"""Story-mode UI rendering for GroupEvidence.

This module is **deterministic**: it consumes `GroupEvidence` objects
and renders a structured, narrative-friendly text + small table
hierarchy. No LLM is involved. The output is suitable for both
humans (Streamlit) and audit (Markdown reports).

The output is one `StoryCard` per group, structured for the
`What Changed` view. Each card contains:

* header (group name + as-of)
* leadership and diffusion transitions (vs previous snapshot)
* 3-5 most important evidence points
* the most important contradiction (if any)
* one deterministic interpretation line
* invalidation conditions
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from idx_leadership.analytics import (
    build_contradictions,
    build_invalidation_conditions,
    compute_persistence,
)
from idx_leadership.models import (
    ContradictionRecord,
    EvidenceRecord,
    GroupEvidence,
    GroupSnapshot,
    InvalidationCondition,
)


@dataclass
class StoryCard:
    group_id: str
    as_of: str
    leadership: str
    diffusion: str
    leadership_transition: Optional[str] = None
    diffusion_transition: Optional[str] = None
    headline: str = ""
    key_evidence: list[dict] = field(default_factory=list)
    contradictions: list[dict] = field(default_factory=list)
    invalidation: list[dict] = field(default_factory=list)
    persistence_snapshots: int = 0
    interpretation: str = ""

    def to_dict(self) -> dict:
        return {
            "group_id": self.group_id,
            "as_of": self.as_of,
            "leadership": self.leadership,
            "diffusion": self.diffusion,
            "leadership_transition": self.leadership_transition,
            "diffusion_transition": self.diffusion_transition,
            "headline": self.headline,
            "key_evidence": list(self.key_evidence),
            "contradictions": list(self.contradictions),
            "invalidation": list(self.invalidation),
            "persistence_snapshots": self.persistence_snapshots,
            "interpretation": self.interpretation,
        }


def _diffusion_label(snapshot: GroupSnapshot) -> str:
    state = snapshot.diffusion_state_v2 or snapshot.diffusion_state
    return state.value


def _evidence_to_dict(e: EvidenceRecord) -> dict:
    return {
        "metric": e.metric,
        "value": e.value if isinstance(e.value, (str, int, float)) else str(e.value),
        "unit": e.unit,
        "direction": e.direction,
        "comment": e.comment,
    }


def _contradiction_to_dict(c: ContradictionRecord) -> dict:
    return {
        "metric": c.metric,
        "label": c.label,
        "severity": c.severity,
        "evidence": c.evidence,
    }


def _invalidation_to_dict(inv: InvalidationCondition) -> dict:
    return {
        "metric": inv.metric,
        "condition": inv.condition,
        "threshold": inv.threshold,
        "rationale": inv.rationale,
    }


def build_story_card(
    current: GroupSnapshot,
    previous: Optional[GroupSnapshot],
    evidence: GroupEvidence,
    persistence_history: list[GroupSnapshot] | None = None,
) -> StoryCard:
    """Compose a `StoryCard` for one group.

    `persistence_history` is an optional list of older GroupSnapshots
    (chronological order, oldest first). If absent, persistence shows 0.
    """
    card = StoryCard(
        group_id=current.group_id,
        as_of=current.snapshot_date.isoformat(),
        leadership=current.leadership_state.value,
        diffusion=_diffusion_label(current),
    )
    if previous is not None:
        if previous.leadership_state != current.leadership_state:
            card.leadership_transition = (
                f"{previous.leadership_state.value} -> {current.leadership_state.value}"
            )
        previous_diffusion = previous.diffusion_state_v2 or previous.diffusion_state
        current_diffusion = current.diffusion_state_v2 or current.diffusion_state
        if previous_diffusion != current_diffusion:
            card.diffusion_transition = (
                f"{previous_diffusion.value} -> {current_diffusion.value}"
            )

    # Top evidence (up to 5)
    for e in evidence.evidence[:5]:
        card.key_evidence.append(_evidence_to_dict(e))

    # Contradictions (heuristic)
    contradictions = build_contradictions(current)
    for c in contradictions[:3]:
        card.contradictions.append(_contradiction_to_dict(c))

    # Invalidation
    for inv in build_invalidation_conditions(current):
        card.invalidation.append(_invalidation_to_dict(inv))

    # Persistence
    if persistence_history:
        p = compute_persistence(current.group_id, current, persistence_history)
        card.persistence_snapshots = p.leadership_persistence_snapshots

    # Headline + interpretation
    if card.leadership_transition and card.diffusion_transition:
        card.headline = (
            f"{current.group_id}: {card.leadership_transition} | {card.diffusion_transition}"
        )
    elif card.leadership_transition:
        card.headline = f"{current.group_id}: {card.leadership_transition}"
    elif card.diffusion_transition:
        card.headline = f"{current.group_id}: {card.diffusion_transition}"
    else:
        card.headline = f"{current.group_id}: {current.leadership_state.value} / {_diffusion_label(current)}"

    parts: list[str] = []
    if current.group_excess_return is not None:
        parts.append(f"20D excess return {current.group_excess_return:+.2f}%")
    if current.breadth_outperforming is not None:
        parts.append(f"breadth {current.breadth_outperforming:.1f}%")
    if card.persistence_snapshots > 0:
        parts.append(f"persistence {card.persistence_snapshots} observations")
    if card.contradictions:
        parts.append(f"{len(card.contradictions)} contradictions flagged")
    card.interpretation = "; ".join(parts) if parts else "No quantitative signal."
    return card


def render_what_changed(cards: list[StoryCard]) -> str:
    """Render a Markdown block of the top material cards."""
    out: list[str] = ["# What Changed", ""]
    for c in cards:
        out.append(f"## {c.headline}")
        out.append("")
        if c.leadership_transition or c.diffusion_transition:
            lines: list[str] = []
            if c.leadership_transition:
                lines.append(f"- Leadership: {c.leadership_transition}")
            if c.diffusion_transition:
                lines.append(f"- Diffusion: {c.diffusion_transition}")
            if c.persistence_snapshots:
                lines.append(f"- Persistence: {c.persistence_snapshots} observations")
            out.extend(lines)
            out.append("")
        if c.key_evidence:
            out.append("### Key evidence")
            for e in c.key_evidence:
                out.append(
                    f"- {e['metric']}: {e['value']}{(' ' + e['unit']) if e['unit'] else ''} "
                    f"({e['direction']}) — {e['comment']}"
                )
            out.append("")
        if c.contradictions:
            out.append("### Contradictions")
            for cn in c.contradictions:
                out.append(
                    f"- {cn['metric']}: {cn['label']} — {cn['evidence']}"
                )
            out.append("")
        if c.invalidation:
            out.append("### Screen invalidation")
            for inv in c.invalidation:
                out.append(f"- {inv['metric']}: {inv['condition']} — {inv['rationale']}")
            out.append("")
        out.append("---")
        out.append("")
    return "\n".join(out)
