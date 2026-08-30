"""Build the research-events bundle.

Reads ``data/derived/research_events.json`` and validates each event
against the normalized schema. The output is a deterministic
``research_events.json`` consumed by the web frontend.

This script does not call any live API: the fixture contains
hand-curated, source-backed entries only.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from idx_leadership.events import (
    EventsBundle,
    ResearchEventError,
    normalize_event,
)
from idx_leadership.utils import project_root, get_logger

_log = get_logger(__name__)


def build_events_bundle(
    input_path: Path,
) -> EventsBundle:
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ResearchEventError("input must be a JSON object")
    raw_events = payload.get("events", [])
    events = [normalize_event(entry) for entry in raw_events]
    sources = payload.get("sources", [])
    return EventsBundle(
        schema_version=str(payload.get("schema_version", "research-events-v1")),
        provider_mode=str(payload.get("provider_mode", "PUBLIC_PROTOTYPE")),
        events=events,
        sources=list(sources),
        source_reconciliation=dict(payload.get("source_reconciliation") or {}),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="build_research_events")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/derived/research_events.json"),
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("data/derived/research_events.json"),
    )
    args = parser.parse_args(argv)

    project = project_root()
    input_path = project / args.input
    out_path = project / args.out

    try:
        bundle = build_events_bundle(input_path)
    except ResearchEventError as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 2
    payload: dict[str, Any] = bundle.to_dict()
    payload["sources"] = bundle.sources
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "schema_version": bundle.schema_version,
                "event_count": len(bundle.events),
                "out": str(out_path),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
