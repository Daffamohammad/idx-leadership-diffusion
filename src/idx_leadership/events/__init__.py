"""Research events normalization.

A research event is a dated, source-backed corporate-action or
market-context observation. Events are explicitly **context only**;
they never become quantitative signals.

Schema:

    event_id
    event_date
    published_at
    ticker
    sector_id
    konglo_id
    theme_ids
    category
    title
    summary
    source_url
    source_name
    provider
    quantitative_use
    status

Categories: earnings, dividend, rights_issue, stock_split, suspension,
index_inclusion, corporate_action, major_filing, other_sourced_event.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable, Mapping

VALID_CATEGORIES = frozenset(
    {
        "earnings",
        "dividend",
        "rights_issue",
        "stock_split",
        "suspension",
        "index_inclusion",
        "corporate_action",
        "major_filing",
        "other_sourced_event",
    }
)


@dataclass(frozen=True)
class ResearchEvent:
    event_id: str
    event_date: date
    published_at: str
    ticker: str
    sector_id: str | None
    konglo_id: str | None
    theme_ids: tuple[str, ...]
    category: str
    title: str
    summary: str
    source_url: str
    source_name: str
    provider: str = "tavily"
    quantitative_use: bool = False
    status: str = "PUBLISHED"

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_date": self.event_date.isoformat(),
            "published_at": self.published_at,
            "ticker": self.ticker,
            "sector_id": self.sector_id,
            "konglo_id": self.konglo_id,
            "theme_ids": list(self.theme_ids),
            "category": self.category,
            "title": self.title,
            "summary": self.summary,
            "source_url": self.source_url,
            "source_name": self.source_name,
            "provider": self.provider,
            "quantitative_use": self.quantitative_use,
            "status": self.status,
        }


class ResearchEventError(ValueError):
    """Raised when an event payload violates the normalized contract."""


def _coerce_date(value: Any) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    text = str(value or "").strip()
    if not text:
        raise ResearchEventError("event_date is required")
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y/%m/%d"):
        try:
            parsed = datetime.strptime(text, fmt)
            return parsed.date()
        except ValueError:
            continue
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed.date()
    except ValueError as exc:
        raise ResearchEventError(f"event_date not ISO date: {value!r}") from exc


def _coerce_ticker(value: Any) -> str:
    text = str(value or "").strip().upper()
    if not text:
        raise ResearchEventError("ticker is required")
    return text if text.endswith(".JK") else f"{text}.JK"


def _coerce_theme_ids(value: Any) -> tuple[str, ...]:
    if value is None or value == "":
        return ()
    if isinstance(value, str):
        return tuple(part.strip() for part in value.split(",") if part.strip())
    if isinstance(value, Iterable):
        return tuple(str(item).strip() for item in value if str(item).strip())
    raise ResearchEventError("theme_ids must be a list or comma-separated string")


def normalize_event(payload: Mapping[str, Any]) -> ResearchEvent:
    category = str(payload.get("category", "")).strip().lower()
    if category not in VALID_CATEGORIES:
        raise ResearchEventError(
            f"category {category!r} not in {sorted(VALID_CATEGORIES)}"
        )
    ticker = _coerce_ticker(payload.get("ticker"))
    event_date = _coerce_date(payload.get("event_date"))
    event_id = str(payload.get("event_id") or f"{ticker}_{event_date.isoformat()}_{category}").strip()
    return ResearchEvent(
        event_id=event_id,
        event_date=event_date,
        published_at=str(payload.get("published_at") or event_date.isoformat()),
        ticker=ticker,
        sector_id=payload.get("sector_id") or None,
        konglo_id=payload.get("konglo_id") or None,
        theme_ids=_coerce_theme_ids(payload.get("theme_ids")),
        category=category,
        title=str(payload.get("title") or "").strip(),
        summary=str(payload.get("summary") or "").strip(),
        source_url=str(payload.get("source_url") or "").strip(),
        source_name=str(payload.get("source_name") or "").strip(),
        provider=str(payload.get("provider") or "tavily").strip() or "tavily",
        quantitative_use=bool(payload.get("quantitative_use", False)),
        status=str(payload.get("status") or "PUBLISHED").strip() or "PUBLISHED",
    )


def normalize_events(payloads: Iterable[Mapping[str, Any]]) -> list[ResearchEvent]:
    return [normalize_event(p) for p in payloads]


@dataclass
class EventsBundle:
    schema_version: str
    provider_mode: str
    events: list[ResearchEvent]
    sources: list[dict[str, Any]] = field(default_factory=list)
    source_reconciliation: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "provider_mode": self.provider_mode,
            "event_count": len(self.events),
            "events": [event.to_dict() for event in self.events],
            "sources": list(self.sources),
            "source_reconciliation": dict(self.source_reconciliation),
        }


def write_events_bundle(
    bundle: EventsBundle, path: Path
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(bundle.to_dict(), indent=2), encoding="utf-8")
    return path


def load_events(path: Path) -> list[ResearchEvent]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    events_raw = payload.get("events", []) if isinstance(payload, Mapping) else []
    return normalize_events(events_raw)


def events_by_ticker(events: Iterable[ResearchEvent], ticker: str) -> list[ResearchEvent]:
    needle = ticker.upper()
    return [event for event in events if event.ticker.upper() == needle]


__all__ = [
    "EventsBundle",
    "ResearchEvent",
    "ResearchEventError",
    "VALID_CATEGORIES",
    "events_by_ticker",
    "load_events",
    "normalize_event",
    "normalize_events",
    "write_events_bundle",
]
