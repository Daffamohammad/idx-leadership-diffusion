"""Tests for the analytics layer: persistence, contradictions, invalidation."""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from idx_leadership.analytics import (
    build_contradictions,
    build_invalidation_conditions,
    compute_persistence,
)
from idx_leadership.models import (
    ConcentrationMetrics,
    DiffusionState,
    GroupSnapshot,
    LeadershipState,
)


def _snap(
    group_id: str = "X",
    *,
    snapshot_date: date,
    leadership_state=LeadershipState.LEADING,
    diffusion_state=DiffusionState.BROADENING,
    group_excess_return=3.0,
    breadth_outperforming=70.0,
    top1=0.3,
) -> GroupSnapshot:
    return GroupSnapshot(
        snapshot_date=snapshot_date,
        group_id=group_id,
        leadership_state=leadership_state,
        diffusion_state=diffusion_state,
        group_excess_return=group_excess_return,
        group_excess_return_5d=group_excess_return,
        group_excess_return_20d=group_excess_return,
        group_excess_return_60d=group_excess_return,
        breadth_outperforming=breadth_outperforming,
        concentration=ConcentrationMetrics(top1_contribution_share=top1),
    )


def test_persistence_current_only():
    s = _snap(snapshot_date=date(2026, 8, 20))
    p = compute_persistence("X", s, [])
    assert p.leadership_persistence_snapshots == 1
    assert p.leadership_persistence_first_seen == date(2026, 8, 20)
    assert p.diffusion_persistence_snapshots == 1


def test_persistence_three_in_state():
    s = _snap(snapshot_date=date(2026, 8, 20))
    history = [
        _snap(snapshot_date=date(2026, 8, 6), leadership_state=LeadershipState.LEADING, diffusion_state=DiffusionState.BROADENING),
        _snap(snapshot_date=date(2026, 8, 13), leadership_state=LeadershipState.LEADING, diffusion_state=DiffusionState.BROADENING),
    ]
    p = compute_persistence("X", s, history)
    assert p.leadership_persistence_snapshots == 3
    assert p.leadership_persistence_first_seen == date(2026, 8, 6)
    assert p.broadening_persistence_snapshots == 3


def test_persistence_chain_broken_by_state_change():
    s = _snap(snapshot_date=date(2026, 8, 20), leadership_state=LeadershipState.LEADING)
    history = [
        _snap(snapshot_date=date(2026, 8, 6), leadership_state=LeadershipState.IMPROVING),
        _snap(snapshot_date=date(2026, 8, 13), leadership_state=LeadershipState.LEADING),
    ]
    p = compute_persistence("X", s, history)
    # Current plus latest prior (8-13) are LEADING; the 8-6 change breaks the run.
    assert p.leadership_persistence_snapshots == 2
    assert p.leadership_persistence_first_seen == date(2026, 8, 13)


def test_persistence_ignores_other_groups_duplicates_and_future_rows():
    current = _snap(snapshot_date=date(2026, 8, 20))
    history = [
        _snap("OTHER", snapshot_date=date(2026, 8, 6)),
        _snap(snapshot_date=date(2026, 8, 13)),
        _snap(snapshot_date=date(2026, 8, 13)),
        _snap(snapshot_date=date(2026, 8, 27)),
    ]
    persistence = compute_persistence("X", current, history)
    assert persistence.leadership_persistence_snapshots == 2
    assert persistence.leadership_persistence_first_seen == date(2026, 8, 13)


def test_contradiction_leading_narrowing():
    s = _snap(
        snapshot_date=date(2026, 8, 20),
        leadership_state=LeadershipState.LEADING,
        diffusion_state=DiffusionState.NARROWING,
    )
    cs = build_contradictions(s)
    metrics = [c.metric for c in cs]
    assert "leading_but_narrowing" in metrics


def test_contradiction_thin_breadth():
    s = _snap(snapshot_date=date(2026, 8, 20), breadth_outperforming=20.0)
    cs = build_contradictions(s)
    metrics = [c.metric for c in cs]
    assert "thin_breadth" in metrics


def test_contradiction_concentrated():
    s = _snap(snapshot_date=date(2026, 8, 20), top1=0.7)
    cs = build_contradictions(s)
    metrics = [c.metric for c in cs]
    assert "concentrated_top1" in metrics


def test_contradiction_no_contradictions_for_balanced_group():
    s = _snap(
        snapshot_date=date(2026, 8, 20),
        leadership_state=LeadershipState.LEADING,
        diffusion_state=DiffusionState.BROADENING,
        breadth_outperforming=70.0,
        top1=0.3,
    )
    cs = build_contradictions(s)
    # LEADING + BROADENING is not a contradiction.
    metrics = [c.metric for c in cs]
    assert "leading_but_narrowing" not in metrics
    assert "thin_breadth" not in metrics
    assert "concentrated_top1" not in metrics


def test_contradiction_improving_into_headwind():
    s = _snap(
        snapshot_date=date(2026, 8, 20),
        leadership_state=LeadershipState.IMPROVING,
        diffusion_state=DiffusionState.STABLE,
        group_excess_return=-1.0,
    )
    cs = build_contradictions(s)
    assert any(c.metric == "improving_into_headwind" for c in cs)


def test_invalidation_returns_multiple_conditions():
    s = _snap(snapshot_date=date(2026, 8, 20))
    inv = build_invalidation_conditions(s)
    metrics = [c.metric for c in inv]
    assert "weaken_if_20d_excess_turns_negative" in metrics
    assert "weaken_if_breadth_below_threshold" in metrics
    assert "weaken_if_diffusion_shifts" in metrics
    assert "weaken_if_persistence_broken" in metrics


def test_invalidation_for_negative_excess():
    s = _snap(
        snapshot_date=date(2026, 8, 20),
        group_excess_return=-2.0,
    )
    inv = build_invalidation_conditions(s)
    # The first condition flips to "strengthen if excess turns positive".
    assert any(c.metric == "strengthen_if_20d_excess_turns_positive" for c in inv)
