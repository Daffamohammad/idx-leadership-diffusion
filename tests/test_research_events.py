"""Tests for the normalized research-event schema."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from idx_leadership.events import (
    EventsBundle,
    ResearchEvent,
    ResearchEventError,
    events_by_ticker,
    normalize_event,
    normalize_events,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
EVENTS_PATH = REPO_ROOT / "data" / "derived" / "research_events.json"


def test_normalize_event_accepts_iso_date():
    event = normalize_event(
        {
            "event_id": "BBCA_TEST_2026-08-22",
            "event_date": "2026-08-22",
            "ticker": "BBCA.JK",
            "category": "dividend",
            "title": "Test event",
            "summary": "Test summary",
            "source_url": "https://example.com/test",
            "source_name": "Example",
        }
    )
    assert event.event_date == date(2026, 8, 22)
    assert event.ticker == "BBCA.JK"
    assert event.category == "dividend"


def test_normalize_event_rejects_unknown_category():
    with pytest.raises(ResearchEventError, match="category"):
        normalize_event(
            {
                "event_date": "2026-08-22",
                "ticker": "BBCA.JK",
                "category": "unsupported",
                "source_url": "x",
                "source_name": "x",
                "title": "t",
                "summary": "s",
            }
        )


def test_normalize_event_requires_ticker():
    with pytest.raises(ResearchEventError):
        normalize_event(
            {
                "event_date": "2026-08-22",
                "category": "dividend",
                "title": "t",
                "summary": "s",
                "source_url": "u",
                "source_name": "n",
            }
        )


def test_normalize_events_bulk_loads():
    events = normalize_events(
        [
            {
                "event_id": "A",
                "event_date": "2026-08-12",
                "ticker": "BBCA.JK",
                "category": "dividend",
                "title": "t",
                "summary": "s",
                "source_url": "u",
                "source_name": "n",
            },
            {
                "event_id": "B",
                "event_date": "2026-08-13",
                "ticker": "TLKM.JK",
                "category": "corporate_action",
                "title": "t2",
                "summary": "s2",
                "source_url": "u2",
                "source_name": "n2",
            },
        ]
    )
    assert len(events) == 2
    assert all(isinstance(e, ResearchEvent) for e in events)


def test_events_by_ticker_filters():
    events = normalize_events(
        [
            {
                "event_id": "A",
                "event_date": "2026-08-12",
                "ticker": "BBCA.JK",
                "category": "dividend",
                "title": "t",
                "summary": "s",
                "source_url": "u",
                "source_name": "n",
            },
            {
                "event_id": "B",
                "event_date": "2026-08-13",
                "ticker": "TLKM.JK",
                "category": "corporate_action",
                "title": "t2",
                "summary": "s2",
                "source_url": "u2",
                "source_name": "n2",
            },
        ]
    )
    matched = events_by_ticker(events, "BBCA.JK")
    assert len(matched) == 1
    assert matched[0].event_id == "A"


def test_published_bundle_roundtrip(tmp_path: Path):
    bundle = EventsBundle(
        schema_version="research-events-v1",
        provider_mode="PUBLIC_PROTOTYPE",
        events=normalize_events(
            [
                {
                    "event_id": "A",
                    "event_date": "2026-08-12",
                    "ticker": "BBCA.JK",
                    "category": "dividend",
                    "title": "t",
                    "summary": "s",
                    "source_url": "u",
                    "source_name": "n",
                }
            ]
        ),
        sources=[{"source_url": "u", "source_name": "n", "provider": "tavily"}],
    )
    payload = bundle.to_dict()
    target = tmp_path / "events.json"
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    loaded = json.loads(target.read_text(encoding="utf-8"))
    assert loaded["event_count"] == 1
    assert loaded["events"][0]["event_id"] == "A"


def test_research_events_fixture_is_valid():
    if not EVENTS_PATH.exists():
        pytest.skip("events fixture not present")
    payload = json.loads(EVENTS_PATH.read_text(encoding="utf-8"))
    events = normalize_events(payload["events"])
    assert events, "fixture must contain at least one event"
    for event in events:
        assert event.event_date is not None
        assert event.source_url.startswith("http")
        assert event.quantitative_use is False


def test_research_events_fixture_dates_are_source_reconciled():
    payload = json.loads(EVENTS_PATH.read_text(encoding="utf-8"))
    events = {event["event_id"]: event for event in payload["events"]}

    assert payload["source_reconciliation"]["status"] == "VERIFIED"
    assert events["BBCA_ex_dividend_2026-08-31"]["published_at"].startswith(
        "2026-08-20"
    )
    assert events["BBRI_buyback_start_2026-06-12"]["event_date"] == "2026-06-12"
    assert events["TLKM_mdi_review_2026-07-31"]["event_date"] == "2026-07-31"
    assert events["BUMI_foreign_net_sell_volume_2026-07-07"]["category"] == (
        "other_sourced_event"
    )
    assert events["BBCA_director_purchases_2026-03-25"]["published_at"].startswith(
        "2026-03-26"
    )
    assert all(event["provider"] == "direct_source_review" for event in events.values())
    assert all(event["quantitative_use"] is False for event in events.values())
