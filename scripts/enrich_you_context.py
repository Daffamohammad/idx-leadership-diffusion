"""Attach bounded You.com research context to an existing snapshot.

This command intentionally does not rebuild market data and never calls the
Sectors API.  It searches the official IDX / OJK / KSEI domains via the
You.com web-search endpoint and, when ``--with-research`` is set, also
requests a multi-step research synthesis for each category.  All evidence
is stored in a separate ``you_context.json`` sidecar.  No web text is
converted into a numeric confirmation metric.

Example (explicitly bounded and paid-call gated)::

    .venv/bin/python -m scripts.enrich_you_context \\
        --snapshot-id snap_sectors_2026-08-27 \\
        --allow-live --allow-credit-spend --with-research
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Mapping
from urllib.parse import urlparse

from idx_leadership.data.snapshots import SnapshotReader, validate_snapshot_id
from idx_leadership.providers.ledger import RequestLedger
from idx_leadership.providers.you_client import YouClient, YouError
from idx_leadership.utils import data_root, load_project_env, project_root


MAX_CATEGORY_QUERIES = 3
DEFAULT_CREDIT_BUDGET = 5.0

CATEGORY_CONFIG: dict[str, dict[str, Any]] = {
    "foreign_flow": {
        "query": "Indonesia IDX foreign investor net buy net sell official market data",
        "domains": ["idx.co.id", "ojk.go.id", "ksei.co.id"],
        "research_question": (
            "Summarize the latest official Indonesia IDX foreign-investor "
            "net buy / net sell flow data published by IDX, OJK, or KSEI. "
            "Return only first-party figures with publication dates."
        ),
        "note": (
            "Market-level first-party flow context only; it is not normalized "
            "per ticker or group and does not change the confirmation metric."
        ),
    },
    "fundamentals": {
        "query": "Indonesia IDX listed company financial statements revenue earnings XBRL official",
        "domains": ["idx.co.id", "ojk.go.id"],
        "research_question": (
            "List the most recent IDX / OJK first-party references on listed "
            "company financial reporting, including XBRL or audited filing "
            "programs. Return publication pages only, no extracted metrics."
        ),
        "note": (
            "First-party filing and reporting context only; no revenue, earnings, "
            "or profitability value is extracted into the snapshot."
        ),
    },
    "events": {
        "query": "Indonesia IDX listed company corporate action announcement dividend rights issue official",
        "domains": ["idx.co.id", "ojk.go.id"],
        "research_question": (
            "Summarize the latest IDX / OJK official announcements about "
            "listed-company corporate actions (dividends, rights issues, "
            "stock splits, mergers). Cite first-party announcement pages only."
        ),
        "note": (
            "First-party announcement context only; events are not mapped to a "
            "group signal or treated as a catalyst score."
        ),
    },
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="enrich_you_context")
    parser.add_argument("--snapshot-id", default=None, help="Existing snapshot to enrich.")
    parser.add_argument(
        "--latest",
        action="store_true",
        help="Use the latest persisted SECTORS_LIVE snapshot.",
    )
    parser.add_argument(
        "--snapshot-root",
        default=None,
        help="Alternate snapshot root for isolated/offline runs.",
    )
    parser.add_argument(
        "--public-out",
        default=None,
        help="Optional public JSON output path; defaults to app/web/public/snapshots/<id>.json.",
    )
    parser.add_argument(
        "--allow-live",
        action="store_true",
        help="Enable You.com HTTP requests for this run.",
    )
    parser.add_argument(
        "--allow-credit-spend",
        action="store_true",
        help="Second explicit gate for paid You.com requests.",
    )
    parser.add_argument(
        "--max-queries",
        type=int,
        default=MAX_CATEGORY_QUERIES,
        help="Maximum category searches; capped at 3 (default: 3).",
    )
    parser.add_argument(
        "--with-research",
        action="store_true",
        help="Run one additional bounded research synthesis per category.",
    )
    parser.add_argument(
        "--research-effort",
        default="lite",
        choices=["lite", "standard", "deep", "exhaustive"],
        help="You.com research_effort parameter when --with-research is set (default: lite).",
    )
    parser.add_argument(
        "--max-credit-budget",
        type=float,
        default=DEFAULT_CREDIT_BUDGET,
        help="Maximum expected You.com requests for this command (default: 5).",
    )
    parser.add_argument(
        "--allow-outside-root",
        action="store_true",
        help="Acknowledge writing outputs outside the project root.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    # Root containment for --out/--output (export pattern): outputs must
    # stay within the project root — or the system temp dir used by
    # isolated/pytest harnesses — unless --allow-outside-root is set.
    _project_root = project_root()
    _temp_root = Path(tempfile.gettempdir()).resolve()
    for _label, _value in (("--public-out", args.public_out),):
        if _value:
            _resolved = Path(_value).resolve()
            _inside_root = True
            try:
                _resolved.relative_to(_project_root.resolve())
            except ValueError:
                _inside_root = False
            _inside_temp = True
            try:
                _resolved.relative_to(_temp_root)
            except ValueError:
                _inside_temp = False
            if not (_inside_root or _inside_temp) and not getattr(
                args, "allow_outside_root", False
            ):
                print(
                    f"refusing {_label} outside {_project_root} without --allow-outside-root",
                    file=sys.stderr,
                )
                return 2

    load_project_env()
    error = _validate_args(args)
    if error:
        print(error)
        return 2

    snapshot_root = Path(args.snapshot_root) if args.snapshot_root else data_root() / "snapshots"
    reader = SnapshotReader(root=snapshot_root)
    snapshot_id = _resolve_snapshot_id(reader, args.snapshot_id, args.latest)
    snapshot_dir = snapshot_root / snapshot_id
    loaded = reader.load(snapshot_id)
    as_of = _snapshot_as_of(loaded)

    expected_requests = int(args.max_queries) + (
        int(args.max_queries) if args.with_research else 0
    )
    if expected_requests > args.max_credit_budget:
        print(
            "BLOCKED expected You.com request reserve "
            f"{expected_requests} exceeds --max-credit-budget {args.max_credit_budget:g}"
        )
        return 2

    ledger_path = data_root() / "raw" / "you" / f"{snapshot_id}_context_ledger.jsonl"
    client = YouClient(
        allow_live=True,
        ledger=RequestLedger(path=ledger_path),
        # Fail-fast: a retry is another bounded HTTP attempt and should be
        # explicitly requested in a future command, not hidden in a refresh.
        max_retries=0,
        max_http_requests=expected_requests,
    )

    retrieved_at = datetime.now(timezone.utc).isoformat()
    responses: list[dict[str, Any]] = []
    request_records: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    categories: dict[str, dict[str, Any]] = {}

    for category, config in list(CATEGORY_CONFIG.items())[: args.max_queries]:
        category_records: list[dict[str, Any]] = []
        try:
            search_response = client.search(
                config["query"],
                count=5,
                include_domains=config["domains"],
                country="ID",
            )
            search_dict = search_response.to_dict()
            search_dict["category"] = category
            search_dict["quantitative_use"] = False
            responses.append(search_dict)
            category_records = _search_records(search_response, category)
            request_records.append(_request_record(search_response, category=category, kind="search"))
        except YouError as exc:
            errors.append(_error_record(exc, category=category, kind="search"))

        research_text: str | None = None
        if args.with_research:
            try:
                research_response = client.research(
                    config["research_question"],
                    research_effort=args.research_effort,
                    source_include_domains=config["domains"],
                    source_country="ID",
                )
                research_dict = research_response.to_dict()
                research_dict["category"] = category
                research_dict["quantitative_use"] = False
                responses.append(research_dict)
                research_text = research_response.answer
                request_records.append(
                    _request_record(research_response, category=category, kind="research")
                )
            except YouError as exc:
                errors.append(_error_record(exc, category=category, kind="research"))

        categories[category] = {
            "status": "READY_WITH_GAPS" if category_records else "DATA_GAP",
            "query": config["query"],
            "source_policy": list(config["domains"]),
            "source_count": len(category_records),
            "records": category_records,
            "research_answer": research_text,
            "note": config["note"],
        }

    client.ledger.flush()
    actual_costs = [
        float(record["actual_credit_cost"])
        for record in request_records
        if isinstance(record.get("actual_credit_cost"), (int, float))
    ]
    actual_cost = round(sum(actual_costs), 6)
    completion_status = (
        "READY_WITH_GAPS"
        if request_records and not errors
        else "PARTIAL"
        if request_records
        else "FAILED"
    )
    context = {
        # REQUESTED preserves the historical top-level meaning: You.com was
        # explicitly invoked. Detailed per-category readiness is below.
        "status": "REQUESTED",
        "completion_status": completion_status,
        "provider": "you",
        "as_of": as_of,
        "retrieved_at": retrieved_at,
        "quantitative_use": False,
        "scope": "qualitative_web_context_only",
        "source_policy": sorted(
            {domain for config in CATEGORY_CONFIG.values() for domain in config["domains"]}
        ),
        "categories": categories,
        "responses": responses,
        # ``records`` is a request/credit audit for parity with the Tavily
        # context contract. Evidence records live under categories.
        "records": request_records,
        "errors": errors,
        "credit_budget": {
            "max_credit_budget": args.max_credit_budget,
            "estimated_credit_cost": float(expected_requests),
            "actual_credit_cost": actual_cost,
            "actual_credit_cost_known": len(actual_costs) == len(request_records),
            "request_count": len(request_records),
            "http_requests_made": client.http_requests_made,
            "max_http_requests": client.max_http_requests,
        },
        "notes": (
            "You.com evidence is source-backed qualitative context only. It "
            "does not populate fundamentals, foreign-flow, event, leadership, "
            "breadth, diffusion, or confirmation metrics."
        ),
    }
    _atomic_write_json(snapshot_dir / "you_context.json", context)

    from scripts.export_snapshot_json import PUBLIC_DIR, export

    public_out = Path(args.public_out) if args.public_out else PUBLIC_DIR / f"{snapshot_id}.json"
    export(snapshot_id, public_out, snapshot_root=snapshot_root)
    print(
        json.dumps(
            {
                "snapshot_id": snapshot_id,
                "snapshot_as_of": as_of,
                "completion_status": completion_status,
                "category_source_counts": {
                    key: value["source_count"] for key, value in categories.items()
                },
                "request_count": len(request_records),
                "errors": len(errors),
                "public_out": str(public_out),
            },
            indent=2,
        )
    )
    return 0 if not errors else 1


def _validate_args(args: argparse.Namespace) -> str | None:
    if not args.snapshot_id and not args.latest:
        return "BLOCKED provide --snapshot-id or --latest"
    if args.snapshot_id and args.latest:
        return "BLOCKED use only one of --snapshot-id and --latest"
    if not args.allow_live:
        return "BLOCKED --allow-live is required; no You.com HTTP request was made"
    if not args.allow_credit_spend:
        return "BLOCKED --allow-credit-spend is required; no You.com HTTP request was made"
    if not 1 <= args.max_queries <= MAX_CATEGORY_QUERIES:
        return f"BLOCKED --max-queries must be between 1 and {MAX_CATEGORY_QUERIES}"
    if args.max_credit_budget <= 0:
        return "BLOCKED --max-credit-budget must be positive"
    if not os.environ.get("YOU_API_KEY", "").strip():
        return "BLOCKED YOU_API_KEY is unavailable (save it in .env or export it)"
    return None


def _resolve_snapshot_id(
    reader: SnapshotReader, snapshot_id: str | None, latest: bool
) -> str:
    if snapshot_id:
        validate_snapshot_id(snapshot_id)
        path = reader.root / snapshot_id
        if not (path / "manifest.json").exists():
            raise FileNotFoundError(f"snapshot manifest not found: {path / 'manifest.json'}")
        return snapshot_id
    candidates: list[tuple[str, str]] = []
    for path in reader.list_snapshots():
        try:
            manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        entries = manifest.get("entries") or []
        entry = entries[0] if entries and isinstance(entries[0], Mapping) else {}
        if (
            manifest.get("provider_mode") == "SECTORS_LIVE"
            or entry.get("provider_mode") == "SECTORS_LIVE"
        ):
            candidates.append(
                (str(entry.get("as_of") or manifest.get("latest_date") or ""), path.name)
            )
    if not latest or not candidates:
        raise FileNotFoundError("no persisted SECTORS_LIVE snapshot found")
    return sorted(candidates)[-1][1]


def _snapshot_as_of(snapshot: Mapping[str, Any]) -> str:
    entries = (snapshot.get("manifest") or {}).get("entries") or []
    entry = entries[0] if entries and isinstance(entries[0], Mapping) else {}
    return str(entry.get("as_of") or snapshot.get("as_of") or "")


def _search_records(response: Any, category: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for result in response.results:
        url = str(result.get("url") or "").strip()
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            continue
        content = (
            result.get("content")
            or result.get("markdown")
            or result.get("description")
            or ""
        )
        if isinstance(content, list):
            content = " ".join(str(item) for item in content if item)
        records.append(
            {
                "source_type": "WEB_CONTEXT",
                "category": category,
                "provider": "you",
                "url": url,
                "title": str(result.get("title") or url)[:300],
                "content": str(content)[:1200],
                "retrieved_at": response.retrieved_at,
                "request_id": response.request_id,
                "quantitative_use": False,
            }
        )
    return records


def _request_record(response: Any, *, category: str, kind: str) -> dict[str, Any]:
    # A cached payload retains the provider's original usage metadata, but
    # replaying it does not spend a credit in this run.
    cost = 0.0 if response.cache_hit else response.credits_used
    return {
        "provider": "you",
        "category": category,
        "kind": kind,
        "endpoint": response.endpoint,
        "request_id": response.request_id,
        "retrieved_at": response.retrieved_at,
        "cache_hit": response.cache_hit,
        "rows_returned": len(response.results),
        "actual_credit_cost": cost,
        "estimated_credit_cost": 0.0,
        "quantitative_use": False,
    }


def _error_record(exc: YouError, *, category: str, kind: str) -> dict[str, Any]:
    return {
        "category": category,
        "kind": kind,
        "code": exc.code,
        "status": exc.status,
        "endpoint": exc.endpoint,
        "message": str(exc),
    }


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False, default=str)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        Path(tmp_name).replace(path)
    finally:
        try:
            Path(tmp_name).unlink()
        except FileNotFoundError:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
