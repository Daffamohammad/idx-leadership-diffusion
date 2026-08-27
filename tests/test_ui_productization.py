"""UI presentation tests for the UI Productization pass.

These tests assert that the new derivations on the frozen
intelligence contract are exposed to the UI as pure presentation
data.  No analytics live in this file.
"""
from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from app.data_sources import load_demo_payload
from app.view_models import (
    BRIEF_SECTIONS,
    ContradictionRow,
    InvalidationRow,
    aggregate_data_gap_status,
    build_dashboard_view,
    data_gap_rollup,
    group_tape_rows,
    invalidation_rows_for,
)
from idx_leadership.intelligence.contract import (
    INTELLIGENCE_CONTRACT_VERSION,
)
from idx_leadership.models import DataGapCategory


# --- DashboardView exposes contradiction_rows and frozen contract version -----


def test_dashboard_view_carries_contradiction_rows():
    view = build_dashboard_view(load_demo_payload())
    assert view.contradiction_rows is not None
    # The DashboardView exposes two contract versions: the frozen
    # brief version (brief-v1) and the intelligence contract version
    # (intelligence-v1).  Both are pinned by the freeze.
    assert view.frozen_contract_version == "brief-v1"
    assert view.intelligence_version == "intelligence-v1"
    assert view.intelligence_version == INTELLIGENCE_CONTRACT_VERSION


def test_contradiction_rows_are_ranked_critical_before_warning():
    view = build_dashboard_view(load_demo_payload())
    if not view.contradiction_rows:
        pytest.skip("no contradictions in this demo")
    severities = [row.severity for row in view.contradiction_rows]
    # CRITICAL must appear before any WARNING.
    if "WARNING" in severities and "CRITICAL" in severities:
        first_warning = severities.index("WARNING")
        last_critical = max(
            index for index, value in enumerate(severities) if value == "CRITICAL"
        )
        assert last_critical < first_warning, (
            "CRITICAL must rank before WARNING in contradiction_rows"
        )


def test_contradiction_rows_have_sequential_ranks():
    view = build_dashboard_view(load_demo_payload())
    if not view.contradiction_rows:
        pytest.skip("no contradictions in this demo")
    ranks = [row.rank for row in view.contradiction_rows]
    assert ranks == list(range(1, len(ranks) + 1))


def test_contradiction_rows_carry_presentation_fields_only():
    view = build_dashboard_view(load_demo_payload())
    for row in view.contradiction_rows:
        assert isinstance(row, ContradictionRow)
        assert row.group_id
        assert row.group_name
        assert row.severity in {"CRITICAL", "WARNING"}
        assert row.label
        assert row.leadership
        assert row.diffusion
        # No analytics fields — these rows are pure presentation.
        assert not hasattr(row, "score")
        assert not hasattr(row, "value_score")


def test_contradiction_rows_are_deduped_by_group_and_metric():
    view = build_dashboard_view(load_demo_payload())
    keys = [(row.group_id, row.label) for row in view.contradiction_rows]
    assert len(keys) == len(set(keys)), "contradiction_rows must be unique by (group_id, label)"


# --- invalidation_rows_for is pure projection -------------------------------


def test_invalidation_rows_for_returns_structured_rows():
    view = build_dashboard_view(load_demo_payload())
    group = view.groups[0]
    rows = invalidation_rows_for(group)
    assert rows
    for row in rows:
        assert isinstance(row, InvalidationRow)
        assert row.condition
        assert row.rationale
        assert row.metric


def test_invalidation_rows_match_brief_contract():
    """The UI and the brief render the same conditions with the same
    thresholds.  The Markdown brief and the Streamlit block both
    consume ``InvalidationCondition.condition`` and
    ``InvalidationCondition.threshold``.
    """
    view = build_dashboard_view(load_demo_payload())
    group = view.groups[0]
    rows = invalidation_rows_for(group)
    assert len(rows) == len(group.invalidation)
    for row, view_invalidation in zip(rows, group.invalidation):
        assert row.condition == view_invalidation.condition
        assert row.threshold == view_invalidation.threshold
        assert row.rationale == view_invalidation.rationale
        assert row.metric == view_invalidation.metric


# --- data_gap_rollup + aggregate_data_gap_status -------------------------


def test_data_gap_rollup_uses_frozen_categories():
    view = build_dashboard_view(load_demo_payload())
    rollup = data_gap_rollup(view.groups)
    labels = {row["category"] for row in rollup}
    expected = {category.value for category in (
        DataGapCategory.FUNDAMENTALS,
        DataGapCategory.FOREIGN_FLOW,
        DataGapCategory.BROKER_ACTIVITY,
        DataGapCategory.FREE_FLOAT,
        DataGapCategory.TAXONOMY,
        DataGapCategory.CORPORATE_ACTIONS,
        DataGapCategory.BENCHMARK,
    )}
    assert labels == expected


def test_aggregate_data_gap_status_returns_worst_for_category():
    view = build_dashboard_view(load_demo_payload())
    # In demo mode, fundamentals are DATA_GAP, benchmark is READY.
    fundamentals = aggregate_data_gap_status(view.groups, DataGapCategory.FUNDAMENTALS)
    benchmark = aggregate_data_gap_status(view.groups, DataGapCategory.BENCHMARK)
    assert fundamentals == "DATA_GAP"
    assert benchmark == "READY"


def test_aggregate_data_gap_status_handles_missing_category():
    # If no group has a gap for a given category, the rollup returns
    # "READY" by convention.
    from app.view_models import aggregate_data_gap_status as fn

    assert fn([], DataGapCategory.FUNDAMENTALS) == "READY"


# --- Leadership Tape rows now expose Contradictions + Confirmation columns ---


def test_group_tape_rows_include_contradictions_and_confirmation():
    view = build_dashboard_view(load_demo_payload())
    rows = group_tape_rows(view.groups)
    assert rows
    for row in rows:
        assert "Contradictions" in row
        assert "Confirmation" in row
        # The confirmation column is the worst status from the frozen
        # data-gap categories; in demo mode it is either READY or
        # DATA_GAP (or NOT_APPLIED / NOT_INTEGRATED / PROTOTYPE).
        assert row["Confirmation"] in {
            "READY",
            "DATA_GAP",
            "NOT_INTEGRATED",
            "NOT_APPLIED",
            "PROTOTYPE",
            "STALE",
        }


def test_group_tape_rows_remove_legacy_unavailable_columns():
    """The freeze pass replaces the legacy ``Fundamentals: UNAVAILABLE``
    / ``Foreign Flow: UNAVAILABLE`` string columns with the
    structured ``Confirmation`` column derived from
    :class:`DataGapView`.
    """
    view = build_dashboard_view(load_demo_payload())
    rows = group_tape_rows(view.groups)
    sample = rows[0]
    assert "Fundamentals" not in sample
    assert "Foreign Flow" not in sample


def test_group_tape_rows_stable_columns_for_legacy_consumers():
    """Columns consumed by the existing tape test remain stable."""
    view = build_dashboard_view(load_demo_payload())
    rows = group_tape_rows(view.groups)
    expected_keys = {
        "Rank",
        "Group",
        "Leadership",
        "Diffusion",
        "20D Excess",
        "60D Excess",
        "Breadth",
        "Δ Breadth",
        "Concentration",
        "Persistence",
        "Contradictions",
        "Confirmation",
    }
    assert set(rows[0].keys()) == expected_keys


# --- Brief contract still frozen at v1 ---------------------------------


def test_brief_section_order_unchanged_after_ui_pass():
    assert BRIEF_SECTIONS == (
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
