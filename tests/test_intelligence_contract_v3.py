from __future__ import annotations

from datetime import date

from idx_leadership.evidence.builder import build_group_evidence
from idx_leadership.intelligence import build_group_read, build_market_read
from idx_leadership.models import (
    ConcentrationMetrics,
    DiffusionState,
    GroupSnapshot,
    LeadershipState,
    ProviderMode,
)
from idx_leadership.signals.change_digest import build_change_digest
from idx_leadership.signals.transitions import compute_transition


def _snapshot(*, day, leadership, diffusion, excess, breadth, delta, rank=1):
    return GroupSnapshot(
        snapshot_date=day,
        taxonomy_level="sector",
        taxonomy_path=["Energy", "Coal"],
        group_id="Coal",
        group_name="Coal",
        constituent_count=10,
        eligible_count=9,
        missing_count=1,
        breadth_total_count=10,
        breadth_eligible_count=9,
        breadth_missing_count=1,
        breadth_outperforming_count=6,
        leadership_state=leadership,
        diffusion_state=diffusion,
        group_excess_return=excess,
        group_excess_return_20d=excess,
        group_excess_return_60d=excess - 1.0,
        breadth_outperforming=breadth,
        breadth_delta=delta,
        leadership_rank=rank,
        leadership_persistence=4,
        diffusion_persistence=2,
        concentration=ConcentrationMetrics(
            top1_contribution_share=0.45,
            top3_contribution_share=0.72,
            hhi_contribution=0.28,
            status="DEFINED",
            signed_attribution_status="DEFINED",
        ),
        method_version="methodology-v3",
        feature_version="features-v3",
    )


def test_builder_emits_nested_ui_ready_contract():
    previous = _snapshot(
        day=date(2026, 8, 13),
        leadership=LeadershipState.IMPROVING,
        diffusion=DiffusionState.STABLE,
        excess=1.0,
        breadth=55.0,
        delta=0.0,
        rank=3,
    )
    current = _snapshot(
        day=date(2026, 8, 20),
        leadership=LeadershipState.LEADING,
        diffusion=DiffusionState.NARROWING,
        excess=4.0,
        breadth=40.0,
        delta=-15.0,
        rank=1,
    )
    evidence = build_group_evidence(
        current,
        previous=previous,
        provider_mode=ProviderMode.PUBLIC_PROTOTYPE,
    )
    payload = evidence.model_dump(mode="json")
    assert payload["group"] == "Coal"
    assert payload["taxonomy_path"] == ["Energy", "Coal"]
    assert payload["leadership"] == {
        "state": "LEADING",
        "previous_state": "IMPROVING",
        "persistence": 4,
    }
    assert payload["diffusion"]["numerator"] == 6
    assert payload["diffusion"]["eligible_denominator"] == 9
    assert payload["concentration"]["status"] == "DEFINED"
    assert payload["confirmation"]["fundamentals"] == "UNAVAILABLE"
    assert payload["invalidation"]


def test_group_and_market_reads_are_small_deterministic_templates():
    previous = _snapshot(
        day=date(2026, 8, 13),
        leadership=LeadershipState.IMPROVING,
        diffusion=DiffusionState.STABLE,
        excess=1.0,
        breadth=55.0,
        delta=0.0,
        rank=3,
    )
    current = _snapshot(
        day=date(2026, 8, 20),
        leadership=LeadershipState.LEADING,
        diffusion=DiffusionState.NARROWING,
        excess=4.0,
        breadth=40.0,
        delta=-15.0,
        rank=1,
    )
    evidence = build_group_evidence(current, previous=previous)
    group_read = build_group_read(evidence)
    assert group_read.interpretation == (
        "Headline leadership remains positive, but participation narrowed."
    )
    event = compute_transition(current=current, previous=previous)
    digest = build_change_digest([event], as_of="2026-08-20", previous="2026-08-13")
    market_read = build_market_read(digest)
    assert market_read.headline
    assert "Coal" in market_read.summary


def test_materiality_requires_quantitative_corroboration():
    previous = _snapshot(
        day=date(2026, 8, 13),
        leadership=LeadershipState.IMPROVING,
        diffusion=DiffusionState.STABLE,
        excess=1.0,
        breadth=55.0,
        delta=0.0,
        rank=1,
    )
    current = _snapshot(
        day=date(2026, 8, 20),
        leadership=LeadershipState.LEADING,
        diffusion=DiffusionState.STABLE,
        excess=1.2,
        breadth=55.0,
        delta=0.0,
        rank=1,
    )
    event = compute_transition(current=current, previous=previous)
    assert event.materiality_label.value == "STABLE"
    assert event.materiality_reason == "state changed without corroborating material move"

