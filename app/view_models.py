"""Pure product view models for the Streamlit app and brief exporter.

All ranking, deterministic copy, evidence shaping, and display semantics live
here.  Rendering code receives immutable dataclasses and does not recompute
analytics.  Inputs are persisted snapshot rows or the clearly labelled demo
fixture; no provider access occurs in this module.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

from idx_leadership.evidence.builder import build_group_evidence
from idx_leadership.models import (
    ContradictionRecord,
    DataGap,
    DataGapCategory,
    InvalidationCondition,
    ProviderMode,
)

from app.snapshot_adapter import row_to_group_snapshot


CONFIRMATION_DATA_GAP = "DATA GAP — SECTORS LIVE NOT CONNECTED"

MODE_LABELS = {
    "DEMO_FIXTURE": "DEMO FIXTURE",
    "PUBLIC_PROTOTYPE": "PUBLIC PROTOTYPE",
    "SECTORS_FIXTURE": "SECTORS FIXTURE",
    "SECTORS_LIVE": "SECTORS LIVE",
}


# --- Section order is frozen at contract v1. Do not reorder. ---
BRIEF_SECTIONS: tuple[str, ...] = (
    "Market Read",
    "Leadership",
    "Broadening",
    "Narrowing",
    "Material Shifts",
    "Contradictions",
    "Selected Evidence",
    "Screen Invalidation",
    "Data Gaps",
)


@dataclass(frozen=True)
class HistoryPoint:
    group_id: str
    as_of: str
    excess_20d: float | None
    breadth: float | None
    breadth_delta: float | None


@dataclass(frozen=True)
class ConstituentView:
    ticker: str
    company_name: str
    excess_5d: float | None
    excess_20d: float | None
    excess_60d: float | None
    participating: bool


@dataclass(frozen=True)
class ContradictionView:
    """UI-level projection of a ContradictionRecord for the brief and table."""

    metric: str
    label: str
    severity: str
    evidence: str | None = None

    @classmethod
    def from_record(cls, record: ContradictionRecord | Mapping[str, Any]) -> "ContradictionView":
        if isinstance(record, ContradictionRecord):
            return cls(
                metric=record.metric,
                label=record.label,
                severity=record.severity,
                evidence=record.evidence,
            )
        return cls(
            metric=str(record.get("metric", "")),
            label=str(record.get("label", record.get("metric", ""))),
            severity=str(record.get("severity", "WARNING")),
            evidence=record.get("evidence"),
        )


@dataclass(frozen=True)
class InvalidationView:
    metric: str
    condition: str
    threshold: str | None
    rationale: str

    @classmethod
    def from_record(cls, record: InvalidationCondition | Mapping[str, Any]) -> "InvalidationView":
        if isinstance(record, InvalidationCondition):
            return cls(
                metric=record.metric,
                condition=record.condition,
                threshold=record.threshold,
                rationale=record.rationale,
            )
        return cls(
            metric=str(record.get("metric", "")),
            condition=str(record.get("condition", record.get("metric", ""))),
            threshold=record.get("threshold"),
            rationale=str(record.get("rationale", "")),
        )


@dataclass(frozen=True)
class DataGapView:
    """UI-level projection of a DataGap; consumed by brief and table."""

    category: str
    status: str
    label: str
    note: str | None = None

    @classmethod
    def from_record(cls, record: DataGap | Mapping[str, Any]) -> "DataGapView":
        if isinstance(record, DataGap):
            return cls(
                category=record.category.value,
                status=record.status.value,
                label=record.label,
                note=record.note,
            )
        return cls(
            category=str(record.get("category", "")),
            status=str(record.get("status", "")),
            label=str(record.get("label", "")),
            note=record.get("note"),
        )


@dataclass(frozen=True)
class GroupView:
    group_id: str
    name: str
    taxonomy_path: tuple[str, ...]
    as_of: str
    rank: int | None
    change_rank: int | None
    leadership: str
    previous_leadership: str | None
    leadership_persistence: int
    diffusion: str
    diffusion_detail: str
    previous_diffusion: str | None
    diffusion_persistence: int
    excess_5d: float | None
    excess_20d: float | None
    excess_60d: float | None
    group_return_20d: float | None
    breadth: float | None
    breadth_delta: float | None
    breadth_numerator: int
    eligible_count: int
    missing_count: int
    total_count: int
    concentration_status: str
    concentration_label: str
    top1: float | None
    top3: float | None
    hhi: float | None
    fundamentals: str
    foreign_flow: str
    contradictions: tuple[ContradictionView, ...]
    invalidation: tuple[InvalidationView, ...]
    data_gaps: tuple[DataGapView, ...]
    interpretation: str
    materiality_label: str
    materiality_reason: str
    history: tuple[HistoryPoint, ...] = field(default_factory=tuple)
    constituents: tuple[ConstituentView, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class MaterialShiftView:
    rank: int
    group_id: str
    group_name: str
    leadership_transition: str | None
    diffusion_transition: str | None
    primary_evidence: str
    secondary_evidence: str
    materiality_reason: str
    contradiction: str | None


@dataclass(frozen=True)
class ContradictionRow:
    """One ranked row for the Overview's Contradictions block.

    Pure presentation; no analytics.  Sorts CRITICAL before WARNING
    and breaks ties by group name.
    """

    rank: int
    group_id: str
    group_name: str
    severity: str
    label: str
    evidence: str | None
    breadth_delta: float | None
    breadth: float | None
    leadership: str
    diffusion: str

    @classmethod
    def from_view(
        cls,
        rank: int,
        group: "GroupView",
        contradiction: "ContradictionView",
    ) -> "ContradictionRow":
        return cls(
            rank=rank,
            group_id=group.group_id,
            group_name=group.name,
            severity=contradiction.severity,
            label=contradiction.label,
            evidence=contradiction.evidence,
            breadth_delta=group.breadth_delta,
            breadth=group.breadth,
            leadership=group.leadership,
            diffusion=group.diffusion,
        )


@dataclass(frozen=True)
class InvalidationRow:
    """One row in the screen-invalidation block of the selected group."""

    metric: str
    condition: str
    threshold: str | None
    rationale: str

    @classmethod
    def from_view(
        cls,
        invalidation: "InvalidationView",
    ) -> "InvalidationRow":
        return cls(
            metric=invalidation.metric,
            condition=invalidation.condition,
            threshold=invalidation.threshold,
            rationale=invalidation.rationale,
        )


@dataclass(frozen=True)
class DataQualityLayer:
    layer: str
    status: str
    detail: str


@dataclass(frozen=True)
class DashboardView:
    provider_mode: str
    provider_badge: str
    is_demo: bool
    as_of: str
    market_date: str | None
    benchmark_date: str | None
    source_path: str
    headline: str
    market_read: str
    supporting_points: tuple[str, ...]
    groups: tuple[GroupView, ...]
    material_shifts: tuple[MaterialShiftView, ...]
    contradiction_rows: tuple[ContradictionRow, ...]
    highlighted_group_id: str | None
    leading_count: int
    improving_count: int
    broadening_count: int
    narrowing_count: int
    eligible_count: int
    total_count: int
    methodology: Mapping[str, Any]
    manifest: Mapping[str, Any]
    quality_layers: tuple[DataQualityLayer, ...]
    frozen_contract_version: str = "brief-v1"
    intelligence_version: str = "intelligence-v1"
    coverage: Mapping[str, Any] = field(default_factory=dict)
    provider_provenance: Mapping[str, Any] = field(default_factory=dict)
    data_warnings: Mapping[str, Any] = field(default_factory=dict)
    api_credit_audit: Mapping[str, Any] = field(default_factory=dict)
    methodology_sensitivity: Mapping[str, Any] = field(default_factory=dict)
    you_context: Mapping[str, Any] = field(default_factory=dict)

    def group(self, group_id: str | None) -> GroupView | None:
        if group_id is None:
            return None
        return next((group for group in self.groups if group.group_id == group_id), None)


def build_dashboard_view(payload: Mapping[str, Any]) -> DashboardView:
    """Build the complete deterministic product contract from local rows."""
    mode = _provider_mode(payload)
    provider_enum = ProviderMode(mode)
    current_rows = _row_sequence(payload.get("groups"))
    if not current_rows:
        raise ValueError("Cannot build product view without group rows")

    previous_rows = _row_sequence(payload.get("previous_groups"))
    previous_by_id = {str(row.get("group_id")): row for row in previous_rows}
    transition_by_id = {
        str(row.get("group_id")): row
        for row in _row_sequence(payload.get("transitions"))
        if row.get("group_id") is not None
    }
    history_by_id = _history_by_group(_row_sequence(payload.get("history")))
    constituent_by_id = _constituents_by_group(payload.get("constituents"))

    groups: list[GroupView] = []
    for row in current_rows:
        group_id = str(row.get("group_id"))
        previous_row = previous_by_id.get(group_id)
        current = row_to_group_snapshot(row)
        previous = row_to_group_snapshot(previous_row) if previous_row else None
        evidence = build_group_evidence(
            current,
            previous=previous,
            provider_mode=provider_enum,
        )
        transition = transition_by_id.get(group_id, {})
        groups.append(
            _build_group_view(
                row,
                evidence,
                transition,
                history_by_id.get(group_id, ()),
                constituent_by_id.get(group_id, ()),
            )
        )

    groups.sort(key=_group_sort_key)
    shifts = _build_material_shifts(groups)
    contradiction_rows = _build_contradiction_rows(groups)
    headline, market_read, supporting = _build_market_read(groups)
    leading = sum(group.leadership == "LEADING" for group in groups)
    improving = sum(group.leadership == "IMPROVING" for group in groups)
    broadening = sum(group.diffusion == "BROADENING" for group in groups)
    narrowing = sum(group.diffusion == "NARROWING" for group in groups)
    eligible = sum(group.eligible_count for group in groups)
    total = sum(group.total_count for group in groups)
    manifest = payload.get("manifest") if isinstance(payload.get("manifest"), Mapping) else {}
    as_of = str(payload.get("as_of") or groups[0].as_of)

    return DashboardView(
        provider_mode=mode,
        provider_badge=MODE_LABELS[mode],
        is_demo=mode == "DEMO_FIXTURE",
        as_of=as_of,
        market_date=_text_or_none(payload.get("market_date")),
        benchmark_date=_text_or_none(payload.get("benchmark_date")),
        source_path=str(payload.get("source_path") or ""),
        headline=headline,
        market_read=market_read,
        supporting_points=supporting,
        groups=tuple(groups),
        material_shifts=shifts,
        contradiction_rows=contradiction_rows,
        highlighted_group_id=shifts[0].group_id if shifts else (
            contradiction_rows[0].group_id if contradiction_rows else groups[0].group_id
        ),
        leading_count=leading,
        improving_count=improving,
        broadening_count=broadening,
        narrowing_count=narrowing,
        eligible_count=eligible,
        total_count=total,
        methodology=(
            payload.get("methodology_config")
            if isinstance(payload.get("methodology_config"), Mapping)
            else {}
        ),
        manifest=manifest,
        quality_layers=_quality_layers(payload, mode),
        frozen_contract_version="brief-v1",
        intelligence_version="intelligence-v1",
        coverage=_mapping_or_empty(payload.get("coverage")),
        provider_provenance=_mapping_or_empty(payload.get("provider_provenance")),
        data_warnings=_mapping_or_empty(payload.get("data_warnings")),
        api_credit_audit=_mapping_or_empty(payload.get("api_credit_audit")),
        methodology_sensitivity=_mapping_or_empty(payload.get("methodology_sensitivity")),
        you_context=_mapping_or_empty(payload.get("you_context")),
    )


def _build_group_view(
    row: Mapping[str, Any],
    evidence: Any,
    transition: Mapping[str, Any],
    history: Sequence[HistoryPoint],
    constituents: Sequence[ConstituentView],
) -> GroupView:
    diffusion_detail = str(evidence.diffusion.state)
    diffusion = _collapse_diffusion(diffusion_detail)
    previous_diffusion = _collapse_diffusion(evidence.diffusion.previous_state)
    top1 = _number(evidence.concentration.top1)
    top3 = _number(evidence.concentration.top3)
    hhi = _number(evidence.concentration.hhi)
    concentration_status = str(evidence.concentration.status)
    concentration_label = _concentration_label(concentration_status, top1, hhi)
    contradictions = tuple(
        ContradictionView.from_record(record) for record in evidence.contradictions
    )
    invalidation = tuple(
        InvalidationView.from_record(record) for record in evidence.invalidation
    )
    data_gaps = tuple(DataGapView.from_record(record) for record in evidence.data_gaps)
    leadership = evidence.leadership.state.value
    excess_20d = _first_number(
        row.get("group_excess_return_20d"),
        row.get("group_excess_return"),
        evidence.performance.excess_20d,
    )
    excess_60d = _first_number(row.get("group_excess_return_60d"), evidence.performance.excess_60d)
    breadth = _first_number(row.get("breadth_outperforming"), evidence.diffusion.breadth)
    breadth_delta = _first_number(row.get("breadth_delta"), evidence.diffusion.breadth_delta)
    name = str(evidence.group or evidence.group_id)
    materiality_label = str(
        transition.get("materiality_label")
        or row.get("materiality_label")
        or "STABLE"
    )
    materiality_reason = str(
        transition.get("materiality_reason")
        or row.get("materiality_reason")
        or "no material change"
    )
    return GroupView(
        group_id=evidence.group_id,
        name=name,
        taxonomy_path=tuple(str(part) for part in evidence.taxonomy_path),
        as_of=evidence.as_of.isoformat(),
        rank=_integer(row.get("leadership_rank")),
        change_rank=_integer(row.get("change_rank")),
        leadership=leadership,
        previous_leadership=(
            evidence.leadership.previous_state.value
            if evidence.leadership.previous_state is not None
            else None
        ),
        leadership_persistence=int(evidence.leadership.persistence),
        diffusion=diffusion,
        diffusion_detail=diffusion_detail,
        previous_diffusion=previous_diffusion,
        diffusion_persistence=int(row.get("diffusion_persistence") or 1),
        excess_5d=_first_number(row.get("group_excess_return_5d"), evidence.performance.excess_5d),
        excess_20d=excess_20d,
        excess_60d=excess_60d,
        group_return_20d=_first_number(row.get("group_return_equal_weight"), evidence.performance.return_20d),
        breadth=breadth,
        breadth_delta=breadth_delta,
        breadth_numerator=int(evidence.diffusion.numerator),
        eligible_count=int(evidence.diffusion.eligible_denominator or row.get("eligible_count") or 0),
        missing_count=int(evidence.diffusion.missing_count or row.get("missing_count") or 0),
        total_count=int(evidence.diffusion.total_count or row.get("constituent_count") or 0),
        concentration_status=concentration_status,
        concentration_label=concentration_label,
        top1=top1,
        top3=top3,
        hhi=hhi,
        fundamentals=CONFIRMATION_DATA_GAP,
        foreign_flow=CONFIRMATION_DATA_GAP,
        contradictions=contradictions,
        invalidation=invalidation,
        data_gaps=data_gaps,
        interpretation=_group_interpretation(
            leadership,
            diffusion,
            excess_60d,
            concentration_label,
        ),
        materiality_label=materiality_label,
        materiality_reason=materiality_reason,
        history=tuple(history),
        constituents=tuple(sorted(constituents, key=_constituent_sort_key)),
    )


def _build_market_read(
    groups: Sequence[GroupView],
) -> tuple[str, str, tuple[str, ...]]:
    broadening = sorted(
        (
            group
            for group in groups
            if group.diffusion == "BROADENING"
            and group.leadership in {"LEADING", "IMPROVING"}
        ),
        key=lambda group: (-(group.breadth_delta or 0.0), group.name),
    )
    narrow_leaders = sorted(
        (
            group
            for group in groups
            if group.leadership == "LEADING" and group.diffusion == "NARROWING"
        ),
        key=lambda group: (group.rank or 999, group.name),
    )
    weakening = [group for group in groups if group.leadership == "WEAKENING"]

    if broadening and narrow_leaders:
        headline = "Participation broadened across emerging leadership, while established strength narrowed."
        market_read = (
            f"Leadership broadened in {_join_names(group.name for group in broadening[:2])}, "
            f"while {_join_names(group.name for group in narrow_leaders[:1])} remained strong "
            "but participation narrowed."
        )
    elif broadening:
        headline = "Leadership strengthened alongside broader constituent participation."
        market_read = (
            f"Relative leadership strengthened in {_join_names(group.name for group in broadening[:3])}; "
            "breadth confirmed the move across the latest observation."
        )
    elif narrow_leaders:
        headline = "Headline leadership held, but participation became less supportive."
        market_read = (
            f"{_join_names(group.name for group in narrow_leaders[:2])} remained in leadership, "
            "while narrowing breadth increased concentration risk."
        )
    else:
        headline = "Leadership was stable without a broad cross-group participation shift."
        market_read = (
            "No broadening or narrowing event met the materiality rules in the latest local snapshot."
        )

    supporting = (
        f"{sum(group.leadership == 'LEADING' for group in groups)} leading and "
        f"{sum(group.leadership == 'IMPROVING' for group in groups)} improving groups.",
        f"{sum(group.diffusion == 'BROADENING' for group in groups)} broadening and "
        f"{sum(group.diffusion == 'NARROWING' for group in groups)} narrowing groups.",
        (
            f"{_join_names(group.name for group in weakening[:2])} showed weakening leadership."
            if weakening
            else "No group was classified as weakening."
        ),
    )
    return headline, market_read, supporting


def _build_material_shifts(groups: Sequence[GroupView]) -> tuple[MaterialShiftView, ...]:
    candidates = [group for group in groups if group.materiality_label != "STABLE"]
    candidates.sort(
        key=lambda group: (
            group.change_rank or 999,
            -_materiality_score(group),
            group.name,
        )
    )
    shifts: list[MaterialShiftView] = []
    for position, group in enumerate(candidates[:5], start=1):
        leadership_transition = _transition(group.previous_leadership, group.leadership)
        diffusion_transition = _transition(group.previous_diffusion, group.diffusion)
        primary = (
            f"Breadth {_format_signed(group.breadth_delta, 'pp')}"
            if group.breadth_delta is not None
            else f"20D excess {_format_signed(group.excess_20d, '%')}"
        )
        secondary = (
            f"20D excess {_format_signed(group.excess_20d, '%')} · "
            f"60D excess {_format_signed(group.excess_60d, '%')}"
        )
        shifts.append(
            MaterialShiftView(
                rank=position,
                group_id=group.group_id,
                group_name=group.name,
                leadership_transition=leadership_transition,
                diffusion_transition=diffusion_transition,
                primary_evidence=primary,
                secondary_evidence=secondary,
                materiality_reason=group.materiality_reason,
                contradiction=group.contradictions[0] if group.contradictions else None,
            )
        )
    return tuple(shifts)


def _build_contradiction_rows(
    groups: Sequence[GroupView],
) -> tuple[ContradictionRow, ...]:
    """Rank all contradictions across the panel for the Overview block.

    Dedupes by (group, metric), sorts CRITICAL before WARNING, and
    breaks ties by group name.  The output is pure presentation data;
    no analytics live here.
    """
    seen: set[tuple[str, str]] = set()
    rows: list[ContradictionRow] = []
    for group in groups:
        for cn in group.contradictions:
            key = (group.group_id, cn.metric)
            if key in seen:
                continue
            seen.add(key)
            rows.append(ContradictionRow.from_view(rank=0, group=group, contradiction=cn))
    rows.sort(
        key=lambda row: (
            0 if row.severity == "CRITICAL" else 1,
            row.group_name,
        )
    )
    ranked = [
        ContradictionRow(
            rank=index,
            group_id=row.group_id,
            group_name=row.group_name,
            severity=row.severity,
            label=row.label,
            evidence=row.evidence,
            breadth_delta=row.breadth_delta,
            breadth=row.breadth,
            leadership=row.leadership,
            diffusion=row.diffusion,
        )
        for index, row in enumerate(rows, start=1)
    ]
    return tuple(ranked)


def invalidation_rows_for(group: GroupView) -> tuple[InvalidationRow, ...]:
    """UI helper: project a group's structured invalidation conditions.

    Pure derivation.  The freeze-pass contract uses these rows for
    both the selected group's Under-the-Surface panel and the brief's
    "Screen Invalidation" subsection.
    """
    return tuple(InvalidationRow.from_view(item) for item in group.invalidation)


def aggregate_data_gap_status(
    groups: Sequence[GroupView],
    category: DataGapCategory,
) -> str:
    """Return the worst observed status for a given data-gap category.

    Priority order: ``FAILED`` > ``DATA_GAP`` > ``STALE`` >
    ``NOT_INTEGRATED`` > ``NOT_APPLIED`` > ``PROTOTYPE`` > ``READY``.
    The Method/Quality "Known gaps" section consumes this to give a
    per-category rollup rather than a list of free-form strings.
    """
    priority = {
        "READY": 0,
        "PROTOTYPE": 1,
        "NOT_APPLIED": 2,
        "NOT_INTEGRATED": 3,
        "STALE": 4,
        "DATA_GAP": 5,
    }
    worst: str | None = None
    worst_score = -1
    for group in groups:
        for gap in group.data_gaps:
            if gap.category != category.value:
                continue
            score = priority.get(gap.status, 0)
            if score > worst_score:
                worst = gap.status
                worst_score = score
    return worst or "READY"


def data_gap_rollup(
    groups: Sequence[GroupView],
) -> list[dict[str, str]]:
    """Build a per-category rollup of data-gap status across the panel.

    Used by the Method/Quality page and the sidebar.  Categories are
    drawn from the frozen :class:`DataGapCategory` enum so the
    rollup is identical to the brief contract.
    """
    return [
        {
            "category": category.value,
            "label": _data_gap_category_label(category.value),
            "status": aggregate_data_gap_status(groups, category),
        }
        for category in (
            DataGapCategory.FUNDAMENTALS,
            DataGapCategory.FOREIGN_FLOW,
            DataGapCategory.BROKER_ACTIVITY,
            DataGapCategory.FREE_FLOAT,
            DataGapCategory.TAXONOMY,
            DataGapCategory.CORPORATE_ACTIONS,
            DataGapCategory.BENCHMARK,
        )
    ]


def render_market_brief(view: DashboardView, selected_group_id: str | None = None) -> str:
    """Render the same product contract as an auditable Markdown brief.

    The section order is frozen at contract v1 — see ``BRIEF_SECTIONS``.
    Adding a new section requires a version bump; renaming an existing
    one breaks every downstream consumer.
    """
    selected = view.group(selected_group_id or view.highlighted_group_id)
    lines: list[str] = [
        "# IDX Leadership Diffusion — Market Brief",
        "",
        f"**Mode:** {view.provider_badge}",
        f"**As of:** {view.as_of}",
    ]
    if view.is_demo:
        lines.extend(
            [
                "",
                "> **DEMO FIXTURE — deterministic synthetic data; not a live market result.**",
            ]
        )
    lines.extend(
        [
            "",
            "## Market Read",
            "",
            f"**{view.headline}**",
            "",
            view.market_read,
            "",
            *[f"- {point}" for point in view.supporting_points],
            "",
            "## Leadership",
            "",
            *_group_bullets(view.groups, {"LEADING", "IMPROVING"}, "leadership"),
            "",
            "## Broadening",
            "",
            *_diffusion_bullets(view.groups, "BROADENING"),
            "",
            "## Narrowing",
            "",
            *_diffusion_bullets(view.groups, "NARROWING"),
            "",
            "## Material Shifts",
            "",
        ]
    )
    if view.material_shifts:
        for shift in view.material_shifts:
            transition_parts = [
                part
                for part in (shift.leadership_transition, shift.diffusion_transition)
                if part
            ]
            lines.append(
                f"{shift.rank}. **{_md_escape(shift.group_name)}** — "
                f"{' | '.join(transition_parts) or 'material evidence change'}; "
                f"{_md_escape(shift.primary_evidence)}. {_md_escape(shift.materiality_reason)}."
            )
    else:
        lines.append("- No change met the configured materiality rules.")

    # --- Contradictions (brief contract v1) ---
    lines.extend(["", "## Contradictions", ""])
    # Deduplicate by (group, metric) so the brief doesn't render the same
    # fact twice.  The leadership_vs_diffusion and leading_but_narrowing
    # heuristics overlap when both are present.
    seen_contradictions: set[tuple[str, str]] = set()
    contradiction_rows: list[tuple[str, ContradictionView, float | None, float | None]] = []
    for group in view.groups:
        for cn in group.contradictions:
            key = (group.name, cn.metric)
            if key in seen_contradictions:
                continue
            seen_contradictions.add(key)
            contradiction_rows.append((group.name, cn, group.breadth_delta, group.breadth))
    contradiction_rows.sort(
        key=lambda row: (
            0 if row[1].severity == "CRITICAL" else 1,
            row[0],
        )
    )
    if contradiction_rows:
        for name, cn, breadth_delta, breadth in contradiction_rows:
            qualifier = cn.evidence or cn.label
            detail_bits = [_md_escape(qualifier)]
            if breadth_delta is not None:
                detail_bits.append(f"breadth {breadth_delta:+.1f}pp")
            if breadth is not None:
                detail_bits.append(f"current breadth {breadth:.1f}%")
            lines.append(f"- **{_md_escape(name)}** — {_md_escape(cn.label)}; {'; '.join(detail_bits)}.")
    else:
        lines.append("- No contradictions were flagged on the latest observation.")

    # --- Selected Evidence ---
    lines.extend(["", "## Selected Evidence", ""])
    if selected is None:
        lines.append("- No group selected.")
    else:
        lines.extend(
            [
                f"### {_md_escape(selected.name)}",
                "",
                _md_escape(selected.interpretation),
                "",
                f"- Leadership: {selected.leadership} ({selected.leadership_persistence} observations)",
                f"- Diffusion: {selected.diffusion_detail} ({selected.diffusion_persistence} observations)",
                f"- Breadth: {_format_value(selected.breadth, '%')} "
                f"({selected.breadth_numerator}/{selected.eligible_count} eligible)",
                f"- Concentration: {selected.concentration_label}; top-1 {_format_share(selected.top1)}",
            ]
        )
        if selected.contradictions:
            lines.append("- Contradictions:")
            for cn in selected.contradictions:
                lines.append(f"  - {_md_escape(cn.label)} — {_md_escape(cn.evidence or '')}".rstrip())
        else:
            lines.append("- Contradictions: none flagged.")

        # --- Screen Invalidation (brief contract v1) ---
        lines.extend(["", "### Screen Invalidation", ""])
        if selected.invalidation:
            intro = (
                f"{_md_escape(selected.name)} would lose its current {selected.leadership}/"
                f"{selected.diffusion_detail} interpretation if:"
            )
            lines.append(intro)
            for inv in selected.invalidation:
                threshold = f" ({_md_escape(inv.threshold)})" if inv.threshold else ""
                lines.append(f"- {_md_escape(inv.condition)}{threshold}.")
        else:
            lines.append("- No invalidation conditions are available for this group.")

    # --- Data Gaps (brief contract v1) ---
    lines.extend(["", "## Data Gaps", ""])
    if selected is not None and selected.data_gaps:
        for gap in selected.data_gaps:
            lines.append(f"- **{_data_gap_category_label(gap.category)}** — {gap.label}")
    else:
        for category in (
            DataGapCategory.FUNDAMENTALS,
            DataGapCategory.FOREIGN_FLOW,
            DataGapCategory.BROKER_ACTIVITY,
            DataGapCategory.FREE_FLOAT,
            DataGapCategory.TAXONOMY,
        ):
            lines.append(
                f"- **{_data_gap_category_label(category.value)}** — "
                f"{CONFIRMATION_DATA_GAP}"
            )
    return "\n".join(lines).rstrip() + "\n"


def _data_gap_category_label(category: str) -> str:
    return category.replace("_", " ").title()


def group_tape_rows(groups: Sequence[GroupView]) -> list[dict[str, Any]]:
    """Stable tabular contract used by Streamlit and focused tests.

    The columns are pure presentation data.  The ``Contradictions``
    column derives from the structured :class:`ContradictionView`
    list on each group; the ``Confirmation`` column derives from the
    structured :class:`DataGapView` list and shows the worst
    observed status across the frozen categories.
    """
    confirmation_priority = {
        "READY": 0,
        "PROTOTYPE": 1,
        "NOT_APPLIED": 2,
        "NOT_INTEGRATED": 3,
        "STALE": 4,
        "DATA_GAP": 5,
    }
    rows: list[dict[str, Any]] = []
    for group in groups:
        # Contradiction summary: count + top severity.
        if group.contradictions:
            top = sorted(
                group.contradictions,
                key=lambda cn: 0 if cn.severity == "CRITICAL" else 1,
            )[0]
            contradiction_summary = f"{len(group.contradictions)} · {top.severity}"
        else:
            contradiction_summary = "—"
        # Confirmation summary: the worst data-gap status across the
        # frozen categories.  If a group carries no data gaps, the
        # confirmation column is "READY".
        worst_status = "READY"
        worst_score = -1
        for gap in group.data_gaps:
            score = confirmation_priority.get(gap.status, 0)
            if score > worst_score:
                worst_status = gap.status
                worst_score = score
        rows.append(
            {
                "Rank": group.rank,
                "Group": group.name,
                "Leadership": group.leadership,
                "Diffusion": group.diffusion,
                "20D Excess": group.excess_20d,
                "60D Excess": group.excess_60d,
                "Breadth": group.breadth,
                "Δ Breadth": group.breadth_delta,
                "Concentration": group.concentration_label,
                "Persistence": group.leadership_persistence,
                "Contradictions": contradiction_summary,
                "Confirmation": worst_status,
            }
        )
    return rows


def _quality_layers(payload: Mapping[str, Any], mode: str) -> tuple[DataQualityLayer, ...]:
    explicit = payload.get("quality_layers")
    if isinstance(explicit, Sequence) and not isinstance(explicit, (str, bytes)):
        return tuple(
            DataQualityLayer(
                layer=str(row.get("layer") or "Unknown"),
                status=str(row.get("status") or "DATA GAP"),
                detail=str(row.get("detail") or ""),
            )
            for row in explicit
            if isinstance(row, Mapping)
        )

    quality = payload.get("quality") if isinstance(payload.get("quality"), Mapping) else {}
    raw_status = str(quality.get("status") or "PROTOTYPE").upper().replace(" ", "_")
    coverage = payload.get("coverage") if isinstance(payload.get("coverage"), Mapping) else {}
    if mode == "SECTORS_LIVE":
        valid_statuses = {"READY", "READY_WITH_GAPS", "PARTIAL", "STALE", "FAILED"}
        market_status = raw_status if raw_status in valid_statuses else "READY_WITH_GAPS"
        history_pct = coverage.get("price_history_coverage_pct")
        eligible = coverage.get("eligible_securities")
        discovered = coverage.get("security_master_total")
        market_detail = (
            f"Sectors daily history · {history_pct}% usable · "
            f"{eligible}/{discovered} eligible"
            if history_pct is not None and eligible is not None and discovered is not None
            else "Sectors live snapshot quality report"
        )
        taxonomy_pct = coverage.get("taxonomy_coverage_pct")
        try:
            taxonomy_complete = taxonomy_pct is not None and float(taxonomy_pct) >= 100
        except (TypeError, ValueError):
            taxonomy_complete = False
        taxonomy_status = "READY" if taxonomy_complete else "READY_WITH_GAPS"
        taxonomy_detail = f"Sectors structured taxonomy · {taxonomy_pct}% complete" if taxonomy_pct is not None else "Sectors taxonomy coverage report"
        benchmark_date = quality.get("benchmark_latest_date") or coverage.get("latest_available_benchmark_date")
        benchmark_status = "READY" if benchmark_date else market_status
        benchmark_detail = f"Sectors native IHSG · latest {benchmark_date}" if benchmark_date else "Sectors benchmark is unavailable"
        corporate_detail = "Raw close; corporate-action adjustment semantics UNKNOWN / VERIFY"
    else:
        market_status = "FIXTURE" if mode == "SECTORS_FIXTURE" else "PROTOTYPE"
        taxonomy_status = "FIXTURE" if mode == "SECTORS_FIXTURE" else "PROTOTYPE"
        market_detail = raw_status
        taxonomy_detail = "Snapshot taxonomy contract"
        benchmark_status = market_status
        benchmark_detail = "Snapshot benchmark artifact"
        corporate_detail = "Price-basis audit pending live data"
    layers = (
        DataQualityLayer("Market Data", market_status, market_detail),
        DataQualityLayer("Taxonomy", taxonomy_status, taxonomy_detail),
        DataQualityLayer("Benchmark", benchmark_status, benchmark_detail),
        DataQualityLayer("Fundamentals", "DATA GAP", "SECTORS LIVE NOT CONNECTED"),
        DataQualityLayer("Foreign Flow", "DATA GAP", "SECTORS LIVE NOT CONNECTED"),
        DataQualityLayer("Corporate Actions", "DATA GAP", corporate_detail),
    )
    return layers


def _mapping_or_empty(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _history_by_group(rows: Sequence[Mapping[str, Any]]) -> dict[str, tuple[HistoryPoint, ...]]:
    grouped: dict[str, list[HistoryPoint]] = {}
    for row in rows:
        group_id = row.get("group_id")
        as_of = row.get("snapshot_date") or row.get("as_of")
        if group_id is None or as_of is None:
            continue
        grouped.setdefault(str(group_id), []).append(
            HistoryPoint(
                group_id=str(group_id),
                as_of=str(as_of),
                excess_20d=_first_number(row.get("group_excess_return_20d"), row.get("group_excess_return")),
                breadth=_number(row.get("breadth_outperforming")),
                breadth_delta=_number(row.get("breadth_delta")),
            )
        )
    return {
        group_id: tuple(sorted(points, key=lambda point: point.as_of))
        for group_id, points in grouped.items()
    }


def _constituents_by_group(value: Any) -> dict[str, tuple[ConstituentView, ...]]:
    if not isinstance(value, Mapping):
        return {}
    out: dict[str, tuple[ConstituentView, ...]] = {}
    for group_id, raw_rows in value.items():
        rows = raw_rows if isinstance(raw_rows, Sequence) else []
        constituents = []
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            excess_20d = _number(row.get("excess_return_20d"))
            constituents.append(
                ConstituentView(
                    ticker=str(row.get("ticker") or "—"),
                    company_name=str(row.get("company_name") or row.get("ticker") or "—"),
                    excess_5d=_number(row.get("excess_return_5d")),
                    excess_20d=excess_20d,
                    excess_60d=_number(row.get("excess_return_60d")),
                    participating=bool(
                        row.get("participating")
                        if row.get("participating") is not None
                        else excess_20d is not None and excess_20d > 0
                    ),
                )
            )
        out[str(group_id)] = tuple(constituents)
    return out


def _provider_mode(payload: Mapping[str, Any]) -> str:
    mode = str(payload.get("provider_mode") or "PUBLIC_PROTOTYPE")
    if mode not in MODE_LABELS:
        raise ValueError(f"Unsupported provider mode: {mode}")
    return mode


def _collapse_diffusion(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    if text.startswith("BROADENING"):
        return "BROADENING"
    if text.startswith("NARROWING"):
        return "NARROWING"
    return text


def _concentration_label(
    status: str,
    top1: float | None,
    hhi: float | None,
) -> str:
    if status == "UNDEFINED" and top1 is None and hhi is None:
        return "UNDEFINED"
    if (top1 is not None and top1 >= 0.60) or (hhi is not None and hhi >= 0.35):
        return "HIGH"
    if (top1 is not None and top1 >= 0.35) or (hhi is not None and hhi >= 0.20):
        return "MODERATE"
    return "LOW"


def _group_interpretation(
    leadership: str,
    diffusion: str,
    excess_60d: float | None,
    concentration: str,
) -> str:
    if leadership == "LEADING" and diffusion == "NARROWING":
        return "Headline leadership remains positive, but participation narrowed."
    if leadership == "IMPROVING" and diffusion == "BROADENING" and (excess_60d or 0.0) < 0:
        return "Breadth is improving before medium-term relative strength turns positive."
    if leadership in {"LEADING", "IMPROVING"} and diffusion == "BROADENING":
        return "Relative leadership strengthened while breadth expanded."
    if leadership == "WEAKENING" and diffusion == "NARROWING":
        return "Relative leadership weakened as constituent participation contracted."
    if leadership == "LEADING" and concentration == "HIGH":
        return "Headline strength remains intact, but leadership has become concentrated."
    if leadership == "LAGGING":
        return "Relative performance remains weak without a confirmed breadth recovery."
    return "Leadership and participation were stable on the latest observation."


def _materiality_score(group: GroupView) -> float:
    state_change = float(
        group.previous_leadership is not None
        and group.previous_leadership != group.leadership
    )
    diffusion_change = float(
        group.previous_diffusion is not None
        and group.previous_diffusion != group.diffusion
    )
    return 4.0 * state_change + 3.0 * diffusion_change + abs(group.breadth_delta or 0.0) / 10.0


def _group_sort_key(group: GroupView) -> tuple[Any, ...]:
    return (
        group.rank if group.rank is not None else 999,
        -(group.excess_20d if group.excess_20d is not None else -999.0),
        group.name,
    )


def _constituent_sort_key(constituent: ConstituentView) -> tuple[Any, ...]:
    return (
        -(constituent.excess_20d if constituent.excess_20d is not None else -999.0),
        constituent.ticker,
    )


def _row_sequence(value: Any) -> list[Mapping[str, Any]]:
    if value is None:
        return []
    if hasattr(value, "to_dict"):
        try:
            return list(value.to_dict(orient="records"))
        except TypeError:
            pass
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return [row for row in value if isinstance(row, Mapping)]
    return []


def _number(value: Any) -> float | None:
    if value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if result != result:
        return None
    return result


def _first_number(*values: Any) -> float | None:
    for value in values:
        parsed = _number(value)
        if parsed is not None:
            return parsed
    return None


def _integer(value: Any) -> int | None:
    parsed = _number(value)
    return int(parsed) if parsed is not None else None


def _text_or_none(value: Any) -> str | None:
    return None if value is None else str(value)


def _transition(previous: str | None, current: str) -> str | None:
    if previous is None or previous == current:
        return None
    return f"{previous} → {current}"


def _join_names(names: Iterable[str]) -> str:
    values = list(names)
    if not values:
        return "no groups"
    if len(values) == 1:
        return values[0]
    if len(values) == 2:
        return f"{values[0]} and {values[1]}"
    return f"{', '.join(values[:-1])}, and {values[-1]}"


def _format_signed(value: float | None, suffix: str) -> str:
    return "UNAVAILABLE" if value is None else f"{value:+.1f}{suffix}"


def _format_value(value: float | None, suffix: str) -> str:
    return "UNAVAILABLE" if value is None else f"{value:.1f}{suffix}"


def _format_share(value: float | None) -> str:
    return "UNDEFINED" if value is None else f"{value:.0%}"


def _md_escape(value: object) -> str:
    """Escape Markdown metacharacters in snapshot-derived strings for briefs."""
    text = "" if value is None else str(value)
    for ch in ("\\", "`", "*", "_", "{", "}", "[", "]", "(", ")", "#", "+", "-", ".", "!"):
        text = text.replace(ch, "\\" + ch)
    return text


def _group_bullets(
    groups: Sequence[GroupView],
    states: set[str],
    dimension: str,
) -> list[str]:
    selected = [group for group in groups if group.leadership in states]
    if not selected:
        return ["- No group met the leadership condition."]
    return [
        f"- **{_md_escape(group.name)}** — {getattr(group, dimension)}; "
        f"20D excess {_format_signed(group.excess_20d, '%')}; {group.diffusion.lower()}."
        for group in selected
    ]


def _diffusion_bullets(groups: Sequence[GroupView], state: str) -> list[str]:
    selected = [group for group in groups if group.diffusion == state]
    if not selected:
        return [f"- No group was classified as {state.lower()}."]
    return [
        f"- **{_md_escape(group.name)}** — breadth {_format_value(group.breadth, '%')}; "
        f"change {_format_signed(group.breadth_delta, 'pp')}."
        for group in selected
    ]
