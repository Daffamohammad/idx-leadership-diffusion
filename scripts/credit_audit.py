"""Credit audit rollup.

Reads the request ledger (JSONL) and produces per-endpoint and
per-refresh-kind cost summaries.

Only observed values are reported. Unknown is preserved as `null`
so the audit never invents numbers.
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any

from idx_leadership.utils import data_root, get_logger, project_root

_log = get_logger(__name__)


def _load_ledger(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def _classify_refresh(endpoint: str) -> str:
    """Map an endpoint to a refresh kind bucket."""
    if endpoint.endswith("/v2/close/"):
        return "core_close"
    if endpoint.endswith("/v2/companies/"):
        return "core_companies"
    if endpoint.endswith("/v2/free-float/"):
        return "core_free_float"
    if endpoint.endswith("/v2/suspensions/"):
        return "core_suspensions"
    if "/foreign-flow/" in endpoint:
        return "enrichment_foreign_flow"
    if "/corporate-actions/" in endpoint:
        return "enrichment_corporate_actions"
    if "/company/report/" in endpoint:
        return "enrichment_company_report"
    return "other"


def _classify_refresh_for_endpoint(endpoint: str, params: dict | None) -> str:
    """More specific classifier using the path only (params may vary)."""
    if "/v2/close/" in endpoint and (params or {}).get("date"):
        return "core_close"
    if "/v2/close/" in endpoint:
        return "core_close"
    return _classify_refresh(endpoint)


def summarize(entries: list[dict[str, Any]]) -> dict[str, Any]:
    by_endpoint: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "requests": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "rows": 0,
            "estimated_credit_cost": 0.0,
            "observed_credit_delta_sum": 0.0,
            "mean_elapsed_ms": 0.0,
            "_elapsed_acc": 0.0,
        }
    )
    for e in entries:
        ep = e.get("endpoint", "UNKNOWN")
        b = by_endpoint[ep]
        b["requests"] += 1
        if e.get("cache_hit"):
            b["cache_hits"] += 1
        else:
            b["cache_misses"] += 1
        b["rows"] += int(e.get("rows_returned") or 0)
        b["estimated_credit_cost"] += float(e.get("estimated_credit_cost") or 0.0)
        b["_elapsed_acc"] += float(e.get("elapsed_ms") or 0.0)
        delta = e.get("actual_credit_cost")
        if delta is not None:
            b["observed_credit_delta_sum"] += float(delta)
    for b in by_endpoint.values():
        if b["requests"]:
            b["mean_elapsed_ms"] = round(b["_elapsed_acc"] / b["requests"], 2)
        del b["_elapsed_acc"]
    by_kind: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"requests": 0, "estimated_credit_cost": 0.0, "rows": 0}
    )
    for e in entries:
        kind = _classify_refresh_for_endpoint(e.get("endpoint", ""), e.get("parameters", {}))
        b = by_kind[kind]
        b["requests"] += 1
        b["estimated_credit_cost"] += float(e.get("estimated_credit_cost") or 0.0)
        b["rows"] += int(e.get("rows_returned") or 0)
    return {
        "by_endpoint": dict(by_endpoint),
        "by_refresh_kind": dict(by_kind),
        "totals": {
            "requests": sum(b["requests"] for b in by_endpoint.values()),
            "rows": sum(b["rows"] for b in by_endpoint.values()),
            "estimated_credit_cost": round(
                sum(b["estimated_credit_cost"] for b in by_endpoint.values()), 4
            ),
            "cache_hits": sum(b["cache_hits"] for b in by_endpoint.values()),
            "cache_misses": sum(b["cache_misses"] for b in by_endpoint.values()),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(prog="credit_audit")
    parser.add_argument(
        "--ledger",
        default=None,
        help="Path to the request ledger JSONL (default: data/raw/request_ledger.jsonl).",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Output JSON path (default: data/normalized/credit_audit.json).",
    )
    parser.add_argument(
        "--allow-outside-root",
        action="store_true",
        help="Acknowledge writing outputs outside the project root.",
    )
    args = parser.parse_args()
    # Root containment for --out/--output (export pattern): outputs must
    # stay within the project root — or the system temp dir used by
    # isolated/pytest harnesses — unless --allow-outside-root is set.
    _project_root = project_root()
    _temp_root = Path(tempfile.gettempdir()).resolve()
    for _label, _value in (("--out", args.out),):
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


    ledger_path = Path(args.ledger) if args.ledger else (data_root() / "raw" / "request_ledger.jsonl")
    out_path = Path(args.out) if args.out else (data_root() / "normalized" / "credit_audit.json")

    entries = _load_ledger(ledger_path)
    summary = summarize(entries)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    print(f"wrote credit audit to {out_path}")
    print(f"entries={len(entries)}  endpoints={len(summary['by_endpoint'])}  kinds={list(summary['by_refresh_kind'].keys())}")
    if not entries:
        print("NOTE: ledger is empty or missing — only refresh_kind bucket structure is reported.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
