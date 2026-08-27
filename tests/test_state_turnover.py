"""Regression tests for state churn, reversals, durations, and exports."""
from __future__ import annotations

import json

import pandas as pd
import pytest

from idx_leadership.analytics.turnover import (
    analyze_state_turnover,
    write_turnover_outputs,
)


def _history() -> pd.DataFrame:
    dates = pd.date_range("2026-07-03", periods=7, freq="7D")
    leadership = {
        "A": [
            "LEADING",
            "IMPROVING",
            "LEADING",
            "LEADING",
            "WEAKENING",
            "WEAKENING",
            "LEADING",
        ],
        "B": ["LAGGING"] * 7,
    }
    diffusion = {
        "A": [
            "BROADENING",
            "NARROWING",
            "BROADENING",
            "STABLE",
            "STABLE",
            "NARROWING",
            "NARROWING",
        ],
        "B": ["STABLE"] * 7,
    }
    return pd.DataFrame(
        [
            {
                "snapshot_date": snapshot_date,
                "group_id": group_id,
                "leadership_state": leadership[group_id][index],
                "diffusion_state": diffusion[group_id][index],
            }
            for group_id in ("A", "B")
            for index, snapshot_date in enumerate(dates)
        ]
    )


def test_turnover_metrics_have_explicit_reversal_denominators():
    report = analyze_state_turnover(_history())
    leadership = report.leadership

    assert report.snapshot_count == 7
    assert report.group_count == 2
    assert leadership.comparable_pairs == 12
    assert leadership.change_count == 4
    assert leadership.change_pct == pytest.approx(33.3333)
    assert leadership.one_period_reversal_candidates == 3
    assert leadership.one_period_reversal_count == 1
    assert leadership.one_period_reversal_rate == pytest.approx(1 / 3, abs=1e-6)
    assert leadership.two_period_reversal_candidates == 3
    assert leadership.two_period_reversal_count == 1
    assert leadership.two_period_reversal_rate == pytest.approx(1 / 3, abs=1e-6)

    diffusion = report.diffusion
    assert diffusion.change_count == 4
    assert diffusion.change_pct == pytest.approx(33.3333)
    assert diffusion.one_period_reversal_count == 1
    assert diffusion.one_period_reversal_candidates == 4
    assert diffusion.two_period_reversal_count == 0
    assert diffusion.two_period_reversal_candidates == 3
    assert "EXTREME_STATE_JUMPS_REVIEW:2" in diffusion.flags


def test_transition_matrix_and_state_durations_are_complete():
    report = analyze_state_turnover(_history())
    leadership = report.leadership

    assert leadership.transition_counts["LEADING"]["IMPROVING"] == 1
    assert leadership.transition_counts["LEADING"]["WEAKENING"] == 1
    assert leadership.transition_counts["LAGGING"]["LAGGING"] == 6
    assert leadership.transition_rates["LAGGING"]["LAGGING"] == 1.0
    assert leadership.state_run_count == 6
    assert leadership.median_state_duration == 1.5
    assert leadership.mean_state_duration == pytest.approx(14 / 6, abs=1e-4)


def test_missing_state_is_explicitly_unconfirmed_and_duplicate_date_is_deduped():
    frame = _history()
    duplicate = frame.iloc[[0]].copy()
    duplicate["leadership_state"] = None
    report = analyze_state_turnover(pd.concat([frame, duplicate], ignore_index=True))
    assert report.observation_count == 14
    assert report.leadership.transition_counts["UNCONFIRMED"]["IMPROVING"] == 1


def test_turnover_writer_outputs_json_csv_and_markdown(tmp_path):
    report = analyze_state_turnover(_history())
    paths = write_turnover_outputs(report, output_dir=tmp_path, prefix="turnover")

    assert set(paths) == {
        "json",
        "markdown",
        "summary_csv",
        "transitions_csv",
        "durations_csv",
        "per_group_csv",
        "per_period_csv",
    }
    assert all(path.exists() for path in paths.values())
    payload = json.loads(paths["json"].read_text())
    assert payload["definitions"]["one_period_reversal"].startswith("A-B-A")
    assert "Transition matrix" in paths["markdown"].read_text()
    transitions = pd.read_csv(paths["transitions_csv"])
    assert {"dimension", "from_state", "to_state", "count", "row_rate"}.issubset(
        transitions.columns
    )
