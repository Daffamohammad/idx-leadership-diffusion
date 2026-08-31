"""Tests verifying the snapshot exporter embeds new sections."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from idx_leadership.events import normalize_events


REPO_ROOT = Path(__file__).resolve().parents[1]
PUBLIC_DIR = REPO_ROOT / "app" / "web" / "public" / "snapshots"


def _load_snapshot(snapshot_id: str) -> dict:
    candidates = [
        PUBLIC_DIR / f"{snapshot_id}.json",
        REPO_ROOT / "data" / "snapshots" / snapshot_id,
    ]
    for candidate in candidates:
        if candidate.is_file():
            return json.loads(candidate.read_text(encoding="utf-8"))
    pytest.skip(f"snapshot {snapshot_id} not generated")


def test_embedded_taxonomy_views_present():
    snapshot = _load_snapshot("snap_2026-08-28")
    views = snapshot.get("taxonomy_views", {})
    assert "sector" in views
    assert "konglo" in views
    assert "themes" in views
    for view in views.values():
        assert view["source_snapshot_id"] == snapshot["snapshot_id"]
        assert view["as_of"] == snapshot["as_of"]
        assert view["snapshot_provider_mode"] == snapshot["manifest"]["entries"][0][
            "provider_mode"
        ]


def test_konglo_view_carries_required_metadata():
    snapshot = _load_snapshot("snap_2026-08-28")
    konglo = snapshot["taxonomy_views"]["konglo"]
    assert konglo["taxonomy_kind"] == "KONGLO"
    assert konglo["source_kind"] == "ANALYST_DEFINED"
    assert konglo["taxonomy_version"]
    assert konglo["groups"]
    sample = konglo["groups"][0]
    assert {"taxonomy_group_id", "taxonomy_group_name", "constituent_count"}.issubset(sample)


def test_themes_view_has_multi_theme_groups():
    snapshot = _load_snapshot("snap_2026-08-28")
    themes = snapshot["taxonomy_views"]["themes"]
    assert themes["taxonomy_kind"] == "THEMES"
    group_ids = {group["taxonomy_group_id"] for group in themes["groups"]}
    # At least five themes with prototype status.
    assert len(group_ids) >= 5
    assert themes.get("provider_mode") == "PUBLIC_PROTOTYPE"


def test_foreign_flow_sample_is_embedded_with_coverage_signals():
    snapshot = _load_snapshot("snap_2026-08-28")
    sample = snapshot.get("foreign_flow_sample")
    assert sample is not None
    assert sample["schema_version"] == "foreign-flow-sample-v2"
    coverage = sample["coverage"]
    assert coverage["market_day_count"] >= 5
    assert coverage["company_observation_count"] >= 30
    # Multi-date breadth is computed.
    breadth = sample["breadth_observed"]
    assert breadth["market_positive_day_count"] + breadth["market_negative_day_count"] >= 2
    # Signal eligibility is explicit and may be False if mapped coverage
    # hasn't yet met the 80% threshold — that's honest, not a failure.
    assert isinstance(sample["signal_eligibility"]["signal_eligible"], bool)
    assert sample["signal_eligibility"]["signal_eligible"] is False
    assert sample["signal_eligibility"]["full_universe_coverage_met"] is False
    assert sample["context_compatibility"]["used_in_leadership_or_diffusion"] is False


def test_research_events_payload_normalises():
    snapshot = _load_snapshot("snap_2026-08-28")
    bundle = snapshot.get("research_events")
    assert bundle is not None
    assert bundle["schema_version"] == "research-events-v1"
    events = normalize_events(bundle["events"])
    assert events, "research events bundle must contain at least one event"
    for event in events:
        assert event.event_date is not None
        assert event.source_url.startswith("http")
        assert event.quantitative_use is False
        assert event.published_at[:10] <= snapshot["as_of"]


def test_live_snapshot_never_embeds_stale_public_taxonomy_view():
    snapshot = _load_snapshot("snap_sectors_2026-08-27")
    assert snapshot["manifest"]["entries"][0]["provider_mode"] == "SECTORS_LIVE"
    for view in snapshot["taxonomy_views"].values():
        assert view["source_snapshot_id"] == "snap_sectors_2026-08-27"
        assert view["as_of"] == "2026-08-27"
        assert view["snapshot_provider_mode"] == "SECTORS_LIVE"
    assert snapshot["taxonomy_views"]["sector"]["provider_mode"] == "SECTORS_LIVE"


def test_ticker_history_is_persisted_and_benchmark_aligned():
    snapshot = _load_snapshot("yf_harness_2026-08-28_adj")
    history = snapshot["ticker_price_history"]["BBCA.JK"]
    assert len(history) > 20
    assert history[0]["value"] == pytest.approx(100.0)
    assert history[0]["benchmark"] == pytest.approx(100.0)
    assert all(point["benchmark"] is not None for point in history)
