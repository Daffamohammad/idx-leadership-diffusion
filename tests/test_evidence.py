"""Tests for the evidence builder."""
from __future__ import annotations

from datetime import date

import pytest

from idx_leadership.evidence.builder import build_group_evidence
from idx_leadership.models import (
    ConcentrationMetrics,
    DataGap,
    DataGapCategory,
    DataGapStatus,
    DiffusionState,
    DiffusionStateV2,
    GroupSnapshot,
    LeadershipState,
)


def _snap(lead, diff, **kwargs):
    return GroupSnapshot(
        snapshot_date=date(2026, 8, 20),
        group_id="X",
        leadership_state=lead,
        diffusion_state=diff,
        concentration=ConcentrationMetrics(),
        **kwargs,
    )


def test_evidence_includes_key_metrics():
    s = _snap(
        LeadershipState.LEADING,
        DiffusionState.BROADENING,
        group_excess_return=3.5,
        group_excess_return_5d=1.0,
        group_excess_return_60d=0.5,
        breadth_outperforming=70.0,
        breadth_delta=12.0,
    )
    ev = build_group_evidence(s)
    metrics = [r.metric for r in ev.evidence]
    assert "excess_return_20d" in metrics
    assert "excess_return_5d" in metrics
    assert "excess_return_60d" in metrics
    assert "breadth_outperforming" in metrics
    assert "breadth_delta" in metrics


def test_evidence_contradicts_leading_but_narrowing():
    s = _snap(
        LeadershipState.LEADING,
        DiffusionState.NARROWING,
        group_excess_return=3.5,
        group_excess_return_5d=1.0,
        group_excess_return_60d=0.5,
        breadth_outperforming=40.0,
    )
    ev = build_group_evidence(s)
    # The integration-freeze contract emits ``leading_but_narrowing``
    # (from build_contradictions) rather than the legacy
    # ``leadership_vs_diffusion`` record.
    assert any(c.metric == "leading_but_narrowing" for c in ev.contradictions)


def test_evidence_contradicts_thin_breadth():
    s = _snap(
        LeadershipState.IMPROVING,
        DiffusionState.BROADENING,
        group_excess_return=-1.0,
        group_excess_return_5d=0.5,
        group_excess_return_60d=-2.0,
        breadth_outperforming=15.0,
    )
    ev = build_group_evidence(s)
    # The integration-freeze contract canonicalises on ``thin_breadth``;
    # the same key is also used by ``build_contradictions``.
    assert any(c.metric == "thin_breadth" for c in ev.contradictions)


def test_evidence_data_gaps_present():
    s = _snap(LeadershipState.LEADING, DiffusionState.STABLE)
    ev = build_group_evidence(s)
    # The integration-freeze contract requires structured DataGap objects
    # with explicit category and status, not free-form strings.
    assert ev.data_gaps
    for gap in ev.data_gaps:
        assert isinstance(gap, DataGap)
        assert isinstance(gap.category, DataGapCategory)
        assert isinstance(gap.status, DataGapStatus)
    categories = {gap.category for gap in ev.data_gaps}
    assert DataGapCategory.FOREIGN_FLOW in categories
    assert DataGapCategory.FUNDAMENTALS in categories


def test_evidence_uses_v2_diffusion_for_contradiction():
    s = _snap(
        LeadershipState.LEADING,
        DiffusionState.NARROWING,
        diffusion_state_v2=DiffusionStateV2.NARROWING_FRAGILE,
        group_excess_return=3.5,
        breadth_outperforming=40.0,
    )
    ev = build_group_evidence(s)
    contradiction = next(c for c in ev.contradictions if c.metric == "leading_but_narrowing")
    assert contradiction.label == "LEADING + NARROWING_FRAGILE"


def test_evidence_contradiction_is_structured():
    s = _snap(
        LeadershipState.LEADING,
        DiffusionState.NARROWING,
        group_excess_return=3.5,
        breadth_outperforming=40.0,
    )
    ev = build_group_evidence(s)
    for c in ev.contradictions:
        assert hasattr(c, "metric")
        assert hasattr(c, "label")
        assert hasattr(c, "severity")
        assert hasattr(c, "evidence")


def test_evidence_invalidation_is_structured():
    from idx_leadership.models import InvalidationCondition

    s = _snap(
        LeadershipState.LEADING,
        DiffusionState.BROADENING,
        group_excess_return=3.5,
        breadth_outperforming=70.0,
    )
    ev = build_group_evidence(s)
    assert ev.invalidation
    for inv in ev.invalidation:
        assert isinstance(inv, InvalidationCondition)
        assert inv.condition
        assert inv.rationale
