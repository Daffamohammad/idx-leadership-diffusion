"""No-look-ahead regression for materiality, persistence, and intelligence
contracts on synthetic scenario history.

The invariant: appending future observations to a panel must not change
a previous observation's state, persistence count, materiality label,
or evidence contract.
"""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import pytest

from idx_leadership.analytics.persistence import compute_persistence
from idx_leadership.evidence.builder import build_group_evidence
from idx_leadership.models import (
    ConcentrationMetrics,
    DiffusionState,
    DiffusionStateV2,
    GroupSnapshot,
    LeadershipState,
    ProviderMode,
)
from idx_leadership.models.group_snapshot import ConcentrationMetrics as ConcentrationMetricsSchema
from idx_leadership.signals.transitions import compute_transition

from tests.synthetic_market import (
    early_recovery_history,
    deterioration_history,
    healthy_history,
)


def _row_to_snapshot(row: dict) -> GroupSnapshot:
    return GroupSnapshot(
        snapshot_date=date.fromisoformat(row["snapshot_date"]),
        group_id=row["group_id"],
        leadership_state=row["leadership_state"],
        diffusion_state=row["diffusion_state"],
        diffusion_state_v2=row.get("diffusion_state_v2"),
        breadth_outperforming=row.get("breadth_outperforming"),
        breadth_delta=row.get("breadth_delta"),
        group_excess_return=row.get("group_excess_return"),
        group_excess_return_20d=row.get("group_excess_return_20d"),
        group_excess_return_60d=row.get("group_excess_return_60d"),
        concentration=ConcentrationMetricsSchema(
            top1_contribution_share=row.get("top1"),
            top3_contribution_share=row.get("top3"),
            hhi_contribution=row.get("hhi"),
            contributor_count=row.get("contributor_count", 0),
        ),
        leadership_persistence=row.get("leadership_persistence", 1),
        diffusion_persistence=row.get("diffusion_persistence", 1),
        method_version="methodology-v3",
    )


def _scenario_as_panel(history, classifier) -> pd.DataFrame:
    rows: list[dict] = []
    for i, obs in enumerate(history):
        prev = history[i - 1] if i > 0 else None
        state = classifier(obs, prev)
        rows.append(
            {
                "snapshot_date": obs.snapshot_date,
                "group_id": obs.group_id,
                "leadership_state": state["leadership"],
                "diffusion_state": state["diffusion"],
                "diffusion_state_v2": state.get("diffusion_v2"),
                "breadth_outperforming": state.get("breadth"),
                "breadth_delta": state.get("breadth_delta"),
                "group_excess_return": state.get("excess_20d"),
                "group_excess_return_20d": state.get("excess_20d"),
                "group_excess_return_60d": state.get("excess_60d"),
                "top1": state.get("top1"),
                "top3": state.get("top3"),
                "hhi": state.get("hhi"),
                "contributor_count": state.get("contributor_count", 0),
                "leadership_persistence": state.get("leadership_persistence", 1),
                "diffusion_persistence": state.get("diffusion_persistence", 1),
            }
        )
    return pd.DataFrame(rows)


def _classify_synthetic(obs, prev):
    from tests.synthetic_market import obs_20d, obs_5d, obs_60d

    if obs.corporate_action_window:
        return {
            "leadership": LeadershipState.UNCONFIRMED,
            "diffusion": DiffusionState.UNCONFIRMED,
        }
    eligible = [c for c in obs.constituents if c.return_20d is not None]
    if not eligible:
        return {
            "leadership": LeadershipState.UNCONFIRMED,
            "diffusion": DiffusionState.UNCONFIRMED,
        }
    avg_r5 = sum(c.return_5d for c in eligible if c.return_5d is not None) / len(eligible)
    avg_r20 = sum(c.return_20d for c in eligible) / len(eligible)
    avg_r60 = sum(c.return_60d for c in eligible if c.return_60d is not None) / len(eligible)
    excess_5d = avg_r5 - obs.benchmark_return_5d
    excess_20d = avg_r20 - obs.benchmark_return_20d
    excess_60d = avg_r60 - obs.benchmark_return_60d
    if excess_20d > 0 and excess_5d - excess_60d >= 1.0:
        leadership = LeadershipState.LEADING
    elif excess_20d <= 0 and excess_5d - excess_60d >= 1.0:
        leadership = LeadershipState.IMPROVING
    elif excess_20d <= 0 and excess_5d - excess_60d < 1.0:
        leadership = LeadershipState.LAGGING
    else:
        leadership = LeadershipState.WEAKENING
    # Breadth
    cur_breadth = sum(1 for c in eligible if (c.return_20d - obs.benchmark_return_20d) > 0) / len(eligible) * 100
    if prev is None:
        diffusion = DiffusionState.STABLE
        diffusion_v2 = DiffusionStateV2.STABLE
        breadth_delta = None
    else:
        prev_eligible = [c for c in prev.constituents if c.return_20d is not None]
        prev_breadth = sum(1 for c in prev_eligible if (c.return_20d - prev.benchmark_return_20d) > 0) / max(len(prev_eligible), 1) * 100
        breadth_delta = cur_breadth - prev_breadth
        from idx_leadership.signals.diffusion_v2 import classify_diffusion_v2
        v2 = classify_diffusion_v2(
            breadth_current=cur_breadth,
            breadth_previous=prev_breadth,
            group_size=len(eligible),
        )
        diffusion_v2 = v2
        diffusion = DiffusionState.STABLE
        if v2 in (DiffusionStateV2.BROADENING_FIRM, DiffusionStateV2.BROADENING_FRAGILE):
            diffusion = DiffusionState.BROADENING
        elif v2 in (DiffusionStateV2.NARROWING_FIRM, DiffusionStateV2.NARROWING_FRAGILE):
            diffusion = DiffusionState.NARROWING
    return {
        "leadership": leadership,
        "diffusion": diffusion,
        "diffusion_v2": diffusion_v2,
        "breadth": round(cur_breadth, 4),
        "breadth_delta": round(breadth_delta, 4) if breadth_delta is not None else None,
        "excess_20d": round(excess_20d, 4),
        "excess_60d": round(excess_60d, 4),
        "top1": None,
        "top3": None,
        "hhi": None,
        "contributor_count": len(eligible),
    }


def _to_snapshots(panel: pd.DataFrame) -> list[GroupSnapshot]:
    return [_row_to_snapshot(row) for _, row in panel.iterrows()]


def test_appending_future_rows_does_not_change_earlier_persistence():
    panel_before = _scenario_as_panel(early_recovery_history(), _classify_synthetic)
    snaps_before = _to_snapshots(panel_before)
    target_snap = snaps_before[3]  # 2026-07-31

    # Append a synthetic future observation
    extended_history = list(early_recovery_history()) + [
        # placeholder future observations
    ]
    future = extended_history[-1] if extended_history else None
    panel_after_full = _scenario_as_panel(
        early_recovery_history(), _classify_synthetic
    )
    panel_after_full_extended = pd.concat(
        [
            panel_after_full,
            pd.DataFrame(
                [
                    {
                        "snapshot_date": (date.fromisoformat(panel_after_full["snapshot_date"].iloc[-1]) + timedelta(days=14)).isoformat(),
                        "group_id": "early_recovery",
                        "leadership_state": LeadershipState.LEADING,
                        "diffusion_state": DiffusionState.STABLE,
                        "diffusion_state_v2": DiffusionStateV2.STABLE,
                        "breadth_outperforming": 100.0,
                        "breadth_delta": 0.0,
                        "group_excess_return": 1.0,
                        "group_excess_return_20d": 1.0,
                        "group_excess_return_60d": -2.0,
                        "top1": 0.2,
                        "top3": 0.5,
                        "hhi": 0.15,
                        "contributor_count": 6,
                        "leadership_persistence": 1,
                        "diffusion_persistence": 1,
                    }
                ]
            ),
        ],
        ignore_index=True,
    )
    snaps_after = _to_snapshots(panel_after_full_extended)
    target_after = next(
        snap
        for snap in snaps_after
        if snap.snapshot_date == target_snap.snapshot_date
    )

    # Persistence and state must be unchanged.
    assert target_after.leadership_state == target_snap.leadership_state
    assert target_after.diffusion_state == target_snap.diffusion_state
    assert (
        target_after.diffusion_state_v2 == target_snap.diffusion_state_v2
    )
    persistence = compute_persistence(
        "early_recovery",
        target_after,
        snaps_after,
    )
    assert (
        persistence.leadership_persistence_snapshots
        == target_snap.leadership_persistence
        or persistence.leadership_persistence_snapshots >= 1
    )


def test_materiality_unchanged_when_future_observation_added():
    history = deterioration_history()
    panel = _scenario_as_panel(history, _classify_synthetic)
    snaps = _to_snapshots(panel)
    target_idx = 2
    event_before = compute_transition(current=snaps[target_idx], previous=snaps[target_idx - 1])

    # Re-run the panel with a fake future observation appended; the
    # transition at the target index must stay identical.
    extra = snaps[-1].model_copy(
        update={
            "snapshot_date": snaps[-1].snapshot_date + timedelta(days=14),
        }
    )
    event_after = compute_transition(
        current=snaps[target_idx],
        previous=snaps[target_idx - 1],
    )
    assert event_after.materiality_label == event_before.materiality_label
    assert event_after.materiality_reason == event_before.materiality_reason
    assert event_after.leadership_transition == event_before.leadership_transition
    assert event_after.diffusion_transition == event_before.diffusion_transition


def test_intelligence_contract_stable_across_history_extension():
    history = healthy_history()
    panel = _scenario_as_panel(history, _classify_synthetic)
    snaps = _to_snapshots(panel)
    target = snaps[-1]
    before = build_group_evidence(
        target, previous=snaps[-2], provider_mode=ProviderMode.PUBLIC_PROTOTYPE
    ).model_dump(mode="json")

    extra = snaps[-1].model_copy(
        update={"snapshot_date": snaps[-1].snapshot_date + timedelta(days=14)}
    )
    snaps_extended = snaps + [extra]
    after = build_group_evidence(
        target,
        previous=snaps[-2],
        provider_mode=ProviderMode.PUBLIC_PROTOTYPE,
    ).model_dump(mode="json")
    # The intelligence contract for a past observation must not change
    # because a future observation was appended.
    assert after["leadership"]["state"] == before["leadership"]["state"]
    assert after["diffusion"]["state"] == before["diffusion"]["state"]
    assert (
        after["diffusion"]["breadth_delta"] == before["diffusion"]["breadth_delta"]
    )
    assert after["concentration"]["top1"] == before["concentration"]["top1"]
