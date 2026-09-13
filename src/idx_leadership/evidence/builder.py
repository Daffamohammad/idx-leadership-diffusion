"""Evidence builder for group snapshots.

Produces a `GroupEvidence` Pydantic object with a list of metric
records. The future narration layer should consume this object rather
than re-deriving metrics from raw data.
"""
from __future__ import annotations

from datetime import date
from typing import Iterable

from ..models import (
    ConcentrationEvidence,
    ConfirmationEvidence,
    ContradictionRecord,
    DataGap,
    DiffusionEvidence,
    DiffusionState,
    DiffusionStateV2,
    EvidenceRecord,
    GroupEvidence,
    GroupSnapshot,
    InvalidationCondition,
    LeadershipEvidence,
    LeadershipState,
    PerformanceEvidence,
    ProviderMode,
)
from ..analytics.contradictions import build_contradictions
from ..analytics.data_gaps import build_data_gaps
from ..analytics.invalidation import build_invalidation_conditions


def _direction(value) -> str:
    if value is None:
        return "neutral"
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "neutral"
    if v > 0:
        return "positive"
    if v < 0:
        return "negative"
    return "neutral"


def build_group_evidence(
    snap: GroupSnapshot,
    *,
    previous: GroupSnapshot | None = None,
    provider_mode: ProviderMode = ProviderMode.PUBLIC_PROTOTYPE,
) -> GroupEvidence:
    evidence: list[EvidenceRecord] = []
    if snap.group_excess_return_5d is not None:
        evidence.append(
            EvidenceRecord(
                metric="excess_return_5d",
                value=round(float(snap.group_excess_return_5d), 2),
                unit="%",
                direction=_direction(snap.group_excess_return_5d),
                comment="short-horizon excess return vs benchmark",
            )
        )
    if snap.group_excess_return is not None:
        evidence.append(
            EvidenceRecord(
                metric="excess_return_20d",
                value=round(float(snap.group_excess_return), 2),
                unit="%",
                direction=_direction(snap.group_excess_return),
                comment="primary-horizon excess return vs benchmark",
            )
        )
    if snap.group_excess_return_60d is not None:
        evidence.append(
            EvidenceRecord(
                metric="excess_return_60d",
                value=round(float(snap.group_excess_return_60d), 2),
                unit="%",
                direction=_direction(snap.group_excess_return_60d),
                comment="medium-horizon excess return vs benchmark",
            )
        )
    if snap.breadth_outperforming is not None:
        evidence.append(
            EvidenceRecord(
                metric="breadth_outperforming",
                value=round(float(snap.breadth_outperforming), 2),
                unit="%",
                direction=_direction(snap.breadth_outperforming),
                comment="% constituents with positive excess return at primary horizon",
            )
        )
    if snap.breadth_delta is not None:
        evidence.append(
            EvidenceRecord(
                metric="breadth_delta",
                value=round(float(snap.breadth_delta), 2),
                unit="pp",
                direction=_direction(snap.breadth_delta),
                comment="change in outperformance share vs prior observation",
            )
        )
    if snap.concentration.top1_contribution_share is not None:
        evidence.append(
            EvidenceRecord(
                metric="concentration_top1",
                value=round(float(snap.concentration.top1_contribution_share), 4),
                unit="share",
                direction="neutral",
                comment=(
                    "top-1 share of group absolute move "
                    f"(convention: {snap.concentration.convention})"
                ),
            )
        )
    if snap.concentration.hhi_contribution is not None:
        evidence.append(
            EvidenceRecord(
                metric="concentration_hhi",
                value=round(float(snap.concentration.hhi_contribution), 4),
                unit="hhi",
                direction="neutral",
                comment="Herfindahl of absolute contribution shares",
            )
        )

    contradictions: list[ContradictionRecord] = []
    effective_diffusion = snap.diffusion_state_v2 or snap.diffusion_state
    if (
        snap.leadership_state in (LeadershipState.LEADING, LeadershipState.IMPROVING)
        and snap.breadth_outperforming is not None
        and snap.breadth_outperforming < 30.0
    ):
        contradictions.append(
            ContradictionRecord(
                metric="thin_breadth",
                label=f"breadth {snap.breadth_outperforming:.1f}%",
                severity="WARNING",
                evidence="improving or leading but few constituents participate",
            )
        )

    # Preserve the original contract metric names, then add the expanded
    # deterministic contradiction rules without duplicating a metric.
    # The ``build_contradictions`` engine emits ``leading_but_narrowing`` for
    # the LEADING + NARROWING case; the evidence builder no longer adds
    # a duplicate ``leadership_vs_diffusion`` entry.
    known_metrics = {record.metric for record in contradictions}
    for record in build_contradictions(snap):
        if record.metric not in known_metrics:
            contradictions.append(record)
            known_metrics.add(record.metric)

    data_gaps: list[DataGap] = build_data_gaps(provider_mode=provider_mode)

    effective_diffusion = snap.diffusion_state_v2 or snap.diffusion_state
    previous_diffusion = None
    if previous is not None:
        previous_diffusion_state = previous.diffusion_state_v2 or previous.diffusion_state
        previous_diffusion = previous_diffusion_state.value

    taxonomy_path = list(snap.taxonomy_path)
    if not taxonomy_path:
        taxonomy_path = [snap.taxonomy_level, snap.group_name or snap.group_id]

    concentration_status = snap.concentration.status
    if concentration_status == "UNDEFINED" and snap.concentration.top1_contribution_share is not None:
        concentration_status = "DEFINED"
    signed_status = snap.concentration.signed_attribution_status
    if signed_status == "UNDEFINED" and snap.concentration.top1_signed_share is not None:
        signed_status = "DEFINED"

    return GroupEvidence(
        group_id=snap.group_id,
        group=snap.group_name or snap.group_id,
        taxonomy_path=taxonomy_path,
        as_of=snap.snapshot_date,
        provider_mode=provider_mode,
        leadership_state=snap.leadership_state,
        diffusion_state=snap.diffusion_state,
        diffusion_state_v2=snap.diffusion_state_v2,
        leadership=LeadershipEvidence(
            state=snap.leadership_state,
            previous_state=previous.leadership_state if previous is not None else None,
            persistence=snap.leadership_persistence,
        ),
        diffusion=DiffusionEvidence(
            state=effective_diffusion.value,
            previous_state=previous_diffusion,
            breadth=snap.breadth_outperforming,
            breadth_delta=snap.breadth_delta,
            numerator=snap.breadth_outperforming_count,
            eligible_denominator=(
                snap.breadth_eligible_count
                if snap.breadth_eligible_count is not None
                else snap.eligible_count
            ),
            missing_count=(
                snap.breadth_missing_count
                if snap.breadth_missing_count is not None
                else snap.missing_count
            ),
            total_count=(
                snap.breadth_total_count
                if snap.breadth_total_count is not None
                else snap.constituent_count
            ),
        ),
        concentration=ConcentrationEvidence(
            status=concentration_status,
            signed_attribution_status=signed_status,
            top1=snap.concentration.top1_contribution_share,
            top3=snap.concentration.top3_contribution_share,
            hhi=snap.concentration.hhi_contribution,
        ),
        performance=PerformanceEvidence(
            return_20d=snap.group_return_equal_weight,
            excess_5d=snap.group_excess_return_5d,
            excess_20d=(
                snap.group_excess_return_20d
                if snap.group_excess_return_20d is not None
                else snap.group_excess_return
            ),
            excess_60d=snap.group_excess_return_60d,
        ),
        confirmation=ConfirmationEvidence(),
        evidence=evidence,
        contradictions=contradictions,
        data_gaps=data_gaps,
        invalidation=build_invalidation_conditions(snap),
        method_version=snap.method_version,
        contract_version="intelligence-v1",
    )


def build_evidence_table(
    snapshots: Iterable[GroupSnapshot],
    *,
    provider_mode: ProviderMode = ProviderMode.PUBLIC_PROTOTYPE,
    previous_by_group: dict[str, GroupSnapshot] | None = None,
) -> list[GroupEvidence]:
    """Build evidence with an explicit provider mode and prior-state map."""

    previous_by_group = previous_by_group or {}
    return [
        build_group_evidence(
            snapshot,
            previous=previous_by_group.get(snapshot.group_id),
            provider_mode=provider_mode,
        )
        for snapshot in snapshots
    ]
