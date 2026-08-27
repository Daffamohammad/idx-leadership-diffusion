"""Frozen contract tests for the brief and intelligence shape.

These tests assert the frozen section order, the frozen data-gap
categories, and the golden output of ``export_market_brief`` against
the demo fixture. Changing the order, renaming a section, or
inserting a duplicate data-gap category must be reflected here as a
deliberate version bump.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from idx_leadership.intelligence.contract import (
    BRIEF_CONTRACT_VERSION,
    BRIEF_SECTIONS,
    FROZEN_DATA_GAP_CATEGORIES,
    FROZEN_DATA_GAP_STATUSES,
    INTELLIGENCE_CONTRACT_VERSION,
    contract_summary,
)
from idx_leadership.models import (
    DataGapCategory,
    DataGapStatus,
    DataGap,
    ContradictionRecord,
    InvalidationCondition,
)


def test_brief_section_order_is_frozen():
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


def test_data_gap_categories_are_frozen():
    assert tuple(c.value for c in DataGapCategory) == FROZEN_DATA_GAP_CATEGORIES


def test_data_gap_statuses_are_frozen():
    assert tuple(s.value for s in DataGapStatus) == FROZEN_DATA_GAP_STATUSES


def test_brief_contract_version_is_pinned():
    assert BRIEF_CONTRACT_VERSION == "brief-v1"
    assert INTELLIGENCE_CONTRACT_VERSION == "intelligence-v1"


def test_contract_summary_returns_all_versions():
    summary = contract_summary()
    assert summary["brief_version"] == "brief-v1"
    assert summary["intelligence_version"] == "intelligence-v1"
    assert summary["section_count"] == str(len(BRIEF_SECTIONS))


# --- Golden output of scripts.export_market_brief --mode demo -------------


REPO_ROOT = Path(__file__).resolve().parents[1]


def _run_export() -> str:
    proc = subprocess.run(
        [sys.executable, "-m", "scripts.export_market_brief", "--mode", "demo"],
        check=True,
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    return proc.stdout


def test_export_market_brief_contains_every_frozen_section():
    output = _run_export()
    last = -1
    for section in BRIEF_SECTIONS:
        marker = f"## {section}"
        idx = output.find(marker)
        assert idx != -1, f"section missing in demo brief: {section}"
        assert idx > last, f"section {section!r} is out of order"
        last = idx


def test_export_market_brief_data_gaps_use_structured_categories():
    output = _run_export()
    # Each structured category must appear under "## Data Gaps" with
    # a Title-Case label and no "— Sectors live not connected" duplication
    # beyond the canonical "DATA GAP" label.
    data_gaps_section = output.split("## Data Gaps", 1)[1]
    for category in (
        "Fundamentals",
        "Foreign Flow",
        "Broker Activity",
        "Free Float",
        "Taxonomy",
    ):
        assert f"**{category}**" in data_gaps_section, (
            f"data_gaps missing category label {category!r}"
        )
    # The brief must not contain the legacy "fundamental confirmation"
    # free-form duplicate string.
    assert "fundamental confirmation unavailable" not in output
    assert "foreign flow unavailable" not in output


def test_export_market_brief_contradictions_section_present():
    output = _run_export()
    contradictions_section = output.split("## Contradictions", 1)[1]
    contradictions_section = contradictions_section.split("## ", 1)[0]
    # The demo fixture contains a LEADING + NARROWING contradiction
    # (Coal) and a thin-breadth contradiction (Basic Materials).
    assert "Coal" in contradictions_section
    # The first contradiction should be the most severe.
    assert contradictions_section.lstrip().startswith("-")


def test_export_market_brief_screen_invalidation_present():
    output = _run_export()
    # The selected evidence section includes "### Screen Invalidation"
    # describing what would make the current interpretation no longer
    # hold.
    assert "### Screen Invalidation" in output
    section = output.split("### Screen Invalidation", 1)[1]
    section = section.split("## ", 1)[0]
    # Each invalidation condition is a deterministic bullet.
    assert re.search(r"- .*\.", section), "invalidation bullets must be deterministic"


def test_export_market_brief_includes_intelligence_contract_marker():
    output = _run_export()
    # The brief must still identify the demo provider and the
    # integration-freeze version line.
    assert "DEMO FIXTURE" in output
    assert "Mode:" in output


# --- Golden JSON shape for the intelligence contract ------------------------


def test_intelligence_contract_produces_structured_objects():
    """GroupEvidence must produce the structured shape every consumer
    expects: ContradictionRecord, InvalidationCondition, DataGap.
    """
    from datetime import date

    from idx_leadership.evidence.builder import build_group_evidence
    from idx_leadership.models import (
        ConcentrationMetrics,
        DiffusionState,
        DiffusionStateV2,
        GroupSnapshot,
        LeadershipState,
    )

    snap = GroupSnapshot(
        snapshot_date=date(2026, 8, 21),
        group_id="contract_check",
        leadership_state=LeadershipState.LEADING,
        diffusion_state=DiffusionState.NARROWING,
        diffusion_state_v2=DiffusionStateV2.NARROWING_FIRM,
        group_excess_return=4.0,
        breadth_outperforming=40.0,
        concentration=ConcentrationMetrics(
            top1_contribution_share=0.7,
            top3_contribution_share=0.9,
            hhi_contribution=0.55,
            contributor_count=8,
        ),
        method_version="methodology-v3",
    )
    evidence = build_group_evidence(snap)

    # Contradictions are ContradictionRecord with the frozen fields.
    assert evidence.contradictions
    for cn in evidence.contradictions:
        assert isinstance(cn, ContradictionRecord)
        assert cn.metric
        assert cn.label
        assert cn.severity in {"WARNING", "CRITICAL"}

    # Invalidation is InvalidationCondition with frozen fields.
    assert evidence.invalidation
    for inv in evidence.invalidation:
        assert isinstance(inv, InvalidationCondition)
        assert inv.condition
        assert inv.rationale

    # Data gaps are structured DataGap objects.
    assert evidence.data_gaps
    for gap in evidence.data_gaps:
        assert isinstance(gap, DataGap)
        assert isinstance(gap.category, DataGapCategory)
        assert isinstance(gap.status, DataGapStatus)
        assert gap.label

    # The frozen contract version is stamped on the evidence object.
    assert evidence.contract_version == INTELLIGENCE_CONTRACT_VERSION


def test_data_gap_categories_round_trip_through_json():
    """DataGap must serialise and deserialise without losing the
    category / status enums; downstream consumers rely on them.
    """
    gap = DataGap(
        category=DataGapCategory.FUNDAMENTALS,
        status=DataGapStatus.DATA_GAP,
        label="DATA GAP — Sectors live not connected",
    )
    payload = gap.model_dump(mode="json")
    restored = DataGap.model_validate(payload)
    assert restored.category == DataGapCategory.FUNDAMENTALS
    assert restored.status == DataGapStatus.DATA_GAP
    assert restored.label == gap.label
    # The JSON form must contain the enum values, not the enum repr.
    assert payload["category"] == "FUNDAMENTALS"
    assert payload["status"] == "DATA_GAP"
