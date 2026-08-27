"""Tests for transition engine and change digest."""
from __future__ import annotations

from datetime import date

import pytest

from idx_leadership.aggregation.groups import build_group_snapshots, rank_groups
from idx_leadership.features.relative_strength import compute_excess_returns
from idx_leadership.models import (
    DiffusionState,
    GroupSnapshot,
    LeadershipState,
    MaterialityLabel,
)
from idx_leadership.signals.change_digest import build_change_digest
from idx_leadership.signals.transitions import (
    build_transition_events,
    compute_transition,
    transition_label,
)


def _snap(group_id, date, lead, diff, br=None, br_delta=None, rs=None, rank=None):
    from idx_leadership.models import ConcentrationMetrics
    return GroupSnapshot(
        snapshot_date=date,
        group_id=group_id,
        leadership_state=lead,
        diffusion_state=diff,
        breadth_outperforming=br,
        breadth_delta=br_delta,
        relative_strength_level=rs,
        concentration=ConcentrationMetrics(),
        leadership_rank=rank,
    )


def test_transition_label_none_when_equal():
    assert transition_label(LeadershipState.LEADING, LeadershipState.LEADING) is None


def test_transition_label_formatted():
    s = transition_label(LeadershipState.IMPROVING, LeadershipState.LEADING)
    assert s == "IMPROVING -> LEADING"


def test_compute_transition_no_previous():
    cur = _snap("X", date(2026, 8, 20), LeadershipState.LEADING, DiffusionState.BROADENING, br=70.0)
    ev = compute_transition(current=cur, previous=None)
    assert ev.previous_date is None
    assert ev.materiality_label == MaterialityLabel.STABLE
    assert ev.materiality_reason == "no previous snapshot"


def test_compute_transition_new_leader():
    cur = _snap("X", date(2026, 8, 20), LeadershipState.LEADING, DiffusionState.BROADENING, br=70.0, rs=5.0)
    prev = _snap("X", date(2026, 8, 13), LeadershipState.LAGGING, DiffusionState.STABLE, br=30.0, rs=-2.0)
    ev = compute_transition(current=cur, previous=prev)
    assert ev.materiality_label == MaterialityLabel.NEW_LEADER


def test_compute_transition_loss_of_leadership():
    cur = _snap("X", date(2026, 8, 20), LeadershipState.LAGGING, DiffusionState.NARROWING, br=20.0, rs=-3.0)
    prev = _snap("X", date(2026, 8, 13), LeadershipState.LEADING, DiffusionState.BROADENING, br=70.0, rs=5.0)
    ev = compute_transition(current=cur, previous=prev)
    assert ev.materiality_label == MaterialityLabel.LOSS_OF_LEADERSHIP


def test_compute_transition_broadening():
    cur = _snap("X", date(2026, 8, 20), LeadershipState.LEADING, DiffusionState.BROADENING, br=80.0, br_delta=12.0, rs=5.0)
    prev = _snap("X", date(2026, 8, 13), LeadershipState.LEADING, DiffusionState.STABLE, br=68.0, br_delta=0.0, rs=5.0)
    ev = compute_transition(current=cur, previous=prev)
    assert ev.materiality_label == MaterialityLabel.BROADENING


def test_compute_transition_narrowing():
    cur = _snap("X", date(2026, 8, 20), LeadershipState.LEADING, DiffusionState.NARROWING, br=50.0, br_delta=-15.0, rs=5.0)
    prev = _snap("X", date(2026, 8, 13), LeadershipState.LEADING, DiffusionState.STABLE, br=65.0, br_delta=0.0, rs=5.0)
    ev = compute_transition(current=cur, previous=prev)
    assert ev.materiality_label == MaterialityLabel.NARROWING


def test_compute_transition_stable():
    cur = _snap("X", date(2026, 8, 20), LeadershipState.LEADING, DiffusionState.STABLE, br=70.0, br_delta=0.0, rs=5.0)
    prev = _snap("X", date(2026, 8, 13), LeadershipState.LEADING, DiffusionState.STABLE, br=70.0, br_delta=0.0, rs=5.0)
    ev = compute_transition(current=cur, previous=prev)
    assert ev.materiality_label == MaterialityLabel.STABLE


def test_build_transition_events_multi():
    cur1 = _snap("A", date(2026, 8, 20), LeadershipState.LEADING, DiffusionState.BROADENING, br=80.0, br_delta=12.0)
    cur2 = _snap("B", date(2026, 8, 20), LeadershipState.LAGGING, DiffusionState.STABLE, br=30.0)
    prev = {
        "A": _snap("A", date(2026, 8, 13), LeadershipState.LAGGING, DiffusionState.STABLE, br=68.0),
        "B": _snap("B", date(2026, 8, 13), LeadershipState.LEADING, DiffusionState.BROADENING, br=70.0),
    }
    events = build_transition_events(current=[cur1, cur2], previous_by_group=prev)
    assert len(events) == 2
    # cur1 -> NEW_LEADER; cur2 -> LOSS_OF_LEADERSHIP
    labels = sorted([e.materiality_label for e in events])
    assert MaterialityLabel.NEW_LEADER in labels
    assert MaterialityLabel.LOSS_OF_LEADERSHIP in labels


def test_change_digest_buckets_unique():
    cur = _snap("A", date(2026, 8, 20), LeadershipState.LEADING, DiffusionState.BROADENING, br=80.0, br_delta=12.0, rs=5.0)
    prev = _snap("A", date(2026, 8, 13), LeadershipState.LAGGING, DiffusionState.STABLE, br=68.0, rs=-2.0)
    ev = compute_transition(current=cur, previous=prev)
    digest = build_change_digest([ev], as_of="2026-08-20", previous="2026-08-13")
    d = digest.to_dict()
    # new_leaders should include the group; no other bucket should.
    assert len(d["new_leaders"]) == 1
    assert d["new_leaders"][0]["group_id"] == "A"
    assert d["upgrades"] == []
    assert d["downgrades"] == []
    assert d["broadening"] == []
    assert d["narrowing"] == []
    assert d["lost_leadership"] == []
    assert d["stable"] == []
