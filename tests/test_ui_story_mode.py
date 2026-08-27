"""Tests for the story-mode and data-quality UI modules."""
from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from app.data_quality import (
    EndpointQuality,
    EndpointStatus,
    human_readable_status,
    overall_rollup,
    render_endpoint_status,
)
from app.story_mode import build_story_card, render_what_changed
from idx_leadership.models import (
    ConcentrationMetrics,
    DiffusionState,
    EvidenceRecord,
    GroupEvidence,
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


def test_build_story_card_with_no_history():
    cur = _snap(snapshot_date=date(2026, 8, 20))
    ev = GroupEvidence(
        group_id="X",
        as_of=date(2026, 8, 20),
        leadership_state=cur.leadership_state,
        diffusion_state=cur.diffusion_state,
        evidence=[
            EvidenceRecord(metric="excess_return_20d", value=3.0, unit="%", direction="positive"),
        ],
    )
    card = build_story_card(cur, None, ev)
    assert card.group_id == "X"
    assert card.leadership == "LEADING"
    assert card.diffusion == "BROADENING"
    assert card.leadership_transition is None
    assert card.diffusion_transition is None
    assert card.persistence_snapshots == 0
    assert "excess_return_20d" in [e["metric"] for e in card.key_evidence]


def test_build_story_card_with_transition():
    cur = _snap(snapshot_date=date(2026, 8, 20), leadership_state=LeadershipState.LEADING)
    prev = _snap(snapshot_date=date(2026, 8, 13), leadership_state=LeadershipState.IMPROVING)
    ev = GroupEvidence(
        group_id="X",
        as_of=date(2026, 8, 20),
        leadership_state=cur.leadership_state,
        diffusion_state=cur.diffusion_state,
    )
    card = build_story_card(cur, prev, ev)
    assert card.leadership_transition == "IMPROVING -> LEADING"
    assert "->" in card.headline


def test_build_story_card_persistence():
    cur = _snap(snapshot_date=date(2026, 8, 20))
    history = [
        _snap(snapshot_date=date(2026, 8, 6)),
        _snap(snapshot_date=date(2026, 8, 13)),
    ]
    ev = GroupEvidence(
        group_id="X",
        as_of=date(2026, 8, 20),
        leadership_state=cur.leadership_state,
        diffusion_state=cur.diffusion_state,
    )
    card = build_story_card(cur, None, ev, persistence_history=history)
    # Persistence is an observation count and includes the current snapshot.
    assert card.persistence_snapshots == 3


def test_build_story_card_contradictions_surface():
    cur = _snap(
        snapshot_date=date(2026, 8, 20),
        leadership_state=LeadershipState.LEADING,
        diffusion_state=DiffusionState.NARROWING,
    )
    ev = GroupEvidence(
        group_id="X",
        as_of=date(2026, 8, 20),
        leadership_state=cur.leadership_state,
        diffusion_state=cur.diffusion_state,
    )
    card = build_story_card(cur, None, ev)
    metrics = [c["metric"] for c in card.contradictions]
    assert "leading_but_narrowing" in metrics


def test_render_what_changed_markdown():
    cur = _snap(snapshot_date=date(2026, 8, 20), group_id="Energy")
    prev = _snap(snapshot_date=date(2026, 8, 13), group_id="Energy", leadership_state=LeadershipState.IMPROVING)
    ev = GroupEvidence(
        group_id="Energy",
        as_of=date(2026, 8, 20),
        leadership_state=cur.leadership_state,
        diffusion_state=cur.diffusion_state,
        evidence=[EvidenceRecord(metric="excess_return_20d", value=5.0, unit="%", direction="positive")],
    )
    card = build_story_card(cur, prev, ev)
    md = render_what_changed([card])
    assert "# What Changed" in md
    assert "Energy" in md
    assert "IMPROVING -> LEADING" in md


def test_render_endpoint_status_dataframe():
    eqs = [
        EndpointQuality(name="close", status=EndpointStatus.READY, rows=900, expected_rows=900, provider="sectors"),
        EndpointQuality(name="free_float", status=EndpointStatus.READY_WITH_GAPS, rows=850, expected_rows=900, provider="sectors"),
    ]
    df = render_endpoint_status(eqs)
    assert not df.empty
    assert set(df.columns) == {"name", "status", "rows", "expected_rows", "reasons", "last_run", "provider"}


def test_overall_rollup_function():
    eqs = [EndpointQuality(name="close", status=EndpointStatus.READY)]
    assert overall_rollup(eqs) == "READY"
    eqs.append(EndpointQuality(name="free_float", status=EndpointStatus.FAILED))
    assert overall_rollup(eqs) == "FAILED"


def test_human_readable_status():
    assert human_readable_status("READY_WITH_GAPS") == "Ready With Gaps"
    assert human_readable_status("FAILED") == "Failed"
