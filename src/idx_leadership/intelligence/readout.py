"""Small deterministic templates for market and group interpretation.

These functions describe the analytical state.  They do not predict returns,
recommend securities, or invoke a language model.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Iterable

from ..models import GroupEvidence, LeadershipState
from ..signals.change_digest import ChangeDigest


@dataclass(frozen=True)
class MarketRead:
    headline: str
    summary: str
    supporting_bullets: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class GroupRead:
    group: str
    headline: str
    interpretation: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class StoryMode:
    market_read: MarketRead
    material_shifts: list[dict]
    highlighted_group: str | None
    contradiction: str | None

    def to_dict(self) -> dict:
        return {
            "market_read": self.market_read.to_dict(),
            "material_shifts": list(self.material_shifts),
            "highlighted_group": self.highlighted_group,
            "contradiction": self.contradiction,
        }


def build_market_read(digest: ChangeDigest | dict) -> MarketRead:
    payload = digest.to_dict() if isinstance(digest, ChangeDigest) else digest
    events = list(payload.get("events") or _legacy_events(payload))
    material = [e for e in events if e.get("materiality_label") != "STABLE"]
    new_leaders = [e for e in material if "new leaders" in e.get("categories", [])]
    broadening = [e for e in material if "broadening" in e.get("categories", [])]
    narrowing = [e for e in material if "narrowing" in e.get("categories", [])]
    weakening = [e for e in material if "weakening" in e.get("categories", [])]

    if new_leaders and broadening:
        headline = "Leadership strengthened as participation broadened."
    elif narrowing and (new_leaders or not weakening):
        headline = "Headline leadership held, but participation narrowed."
    elif weakening:
        headline = "Leadership weakened across the most material changes."
    elif broadening:
        headline = "Participation broadened without a broad leadership reset."
    else:
        headline = "Leadership was broadly stable in the latest comparison."

    clauses: list[str] = []
    if new_leaders:
        clauses.append(f"{_names(new_leaders)} moved into leadership")
    if broadening:
        clauses.append(f"participation broadened in {_names(broadening)}")
    if narrowing:
        clauses.append(f"participation narrowed in {_names(narrowing)}")
    if weakening:
        clauses.append(f"relative leadership weakened in {_names(weakening)}")
    if not clauses:
        summary = "No change cleared the configured materiality thresholds."
    else:
        raw_summary = "; ".join(clauses[:3])
        summary = raw_summary[:1].upper() + raw_summary[1:] + "."

    bullets: list[str] = []
    for event in material[:5]:
        evidence = list(event.get("primary_evidence") or [])
        reason = event.get("materiality_reason")
        detail = evidence[0] if evidence else reason or "material state change"
        bullets.append(f"{event.get('group') or event.get('group_id')}: {detail}")
    return MarketRead(headline=headline, summary=summary, supporting_bullets=bullets)


def build_group_read(evidence: GroupEvidence) -> GroupRead:
    group = evidence.group or evidence.group_id
    diffusion = (
        evidence.diffusion.state
        if evidence.diffusion is not None
        else (evidence.diffusion_state_v2 or evidence.diffusion_state).value
    )
    medium = evidence.performance.excess_60d
    breadth_delta = evidence.diffusion.breadth_delta if evidence.diffusion is not None else None

    if evidence.leadership_state == LeadershipState.LEADING and "NARROWING" in diffusion:
        text = "Headline leadership remains positive, but participation narrowed."
    elif evidence.leadership_state == LeadershipState.LEADING and "BROADENING" in diffusion:
        text = "Relative leadership strengthened while participation broadened."
    elif (
        evidence.leadership_state == LeadershipState.IMPROVING
        and medium is not None
        and medium < 0
        and breadth_delta is not None
        and breadth_delta > 0
    ):
        text = "Breadth improved before medium-term relative strength turned positive."
    elif evidence.leadership_state == LeadershipState.WEAKENING:
        text = "Medium-term relative strength remains positive, but short-horizon momentum weakened."
    elif evidence.leadership_state == LeadershipState.LAGGING:
        text = "Relative performance remains negative and participation has not confirmed recovery."
    else:
        text = "The current state is unconfirmed because the evidence threshold was not met."
    return GroupRead(group=group, headline=f"{group}: {evidence.leadership_state.value}", interpretation=text)


def build_story_mode(
    digest: ChangeDigest | dict,
    evidence: Iterable[GroupEvidence],
) -> StoryMode:
    market_read = build_market_read(digest)
    payload = digest.to_dict() if isinstance(digest, ChangeDigest) else digest
    events = list(payload.get("events") or _legacy_events(payload))
    material = [e for e in events if e.get("materiality_label") != "STABLE"][:5]
    highlighted = material[0].get("group") or material[0].get("group_id") if material else None
    contradiction = None
    evidence_by_group = {e.group or e.group_id: e for e in evidence}
    if highlighted in evidence_by_group and evidence_by_group[highlighted].contradictions:
        item = evidence_by_group[highlighted].contradictions[0]
        contradiction = item.evidence or item.label or item.metric
    return StoryMode(
        market_read=market_read,
        material_shifts=material,
        highlighted_group=highlighted,
        contradiction=contradiction,
    )


def _names(events: list[dict]) -> str:
    names: list[str] = []
    for event in events:
        name = str(event.get("group") or event.get("group_id") or "Unknown group")
        if name not in names:
            names.append(name)
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} and {names[1]}"
    return ", ".join(names[:2]) + f" and {len(names) - 2} others"


def _legacy_events(payload: dict) -> list[dict]:
    events: list[dict] = []
    category_map = {
        "new_leaders": "new leaders",
        "lost_leadership": "lost leadership",
        "upgrades": "improving",
        "downgrades": "weakening",
        "broadening": "broadening",
        "narrowing": "narrowing",
        "stable": "stable",
    }
    seen: set[str] = set()
    for bucket, category in category_map.items():
        for record in payload.get(bucket, []):
            group_id = str(record.get("group_id"))
            if group_id in seen:
                continue
            seen.add(group_id)
            row = dict(record)
            row.setdefault("group", group_id)
            row.setdefault("categories", [category])
            events.append(row)
    return events
