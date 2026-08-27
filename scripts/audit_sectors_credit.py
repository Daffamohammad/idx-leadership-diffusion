"""Observed Sectors credit audit with an explicit unavailable state."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from idx_leadership.utils import data_root


BALANCE_UNAVAILABLE = "BALANCE UNAVAILABLE"


def _load_ledger(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def build_credit_audit(
    entries: list[dict[str, Any]],
    *,
    request_category: str,
    before_balance: float | None = None,
    after_balance: float | None = None,
) -> dict[str, Any]:
    observed_delta = (
        before_balance - after_balance
        if before_balance is not None and after_balance is not None
        else None
    )
    matching = [
        row
        for row in entries
        if request_category == "ALL"
        or row.get("request_category") == request_category
        or request_category.lower() in str(row.get("endpoint", "")).lower()
    ]
    return {
        "provider_mode": "SECTORS_LIVE",
        "request_category": request_category,
        "before_balance": before_balance if before_balance is not None else BALANCE_UNAVAILABLE,
        "after_balance": after_balance if after_balance is not None else BALANCE_UNAVAILABLE,
        "observed_delta": observed_delta if observed_delta is not None else BALANCE_UNAVAILABLE,
        "balance_status": (
            "OBSERVED" if observed_delta is not None else BALANCE_UNAVAILABLE
        ),
        "ledger_entries": len(matching),
        "requests": sum(1 for row in matching if not row.get("cache_hit")),
        "cache_hits": sum(1 for row in matching if row.get("cache_hit")),
        "endpoints": sorted({str(row.get("endpoint", "UNKNOWN")) for row in matching}),
        "note": (
            "Observed delta is before minus after; no credit cost is inferred."
            if observed_delta is not None
            else "Balance source unavailable; ledger diagnostics remain valid."
        ),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="audit_sectors_credit")
    parser.add_argument("--ledger", default=None)
    parser.add_argument("--request-category", default="ALL")
    parser.add_argument("--before-balance", type=float, default=None)
    parser.add_argument("--after-balance", type=float, default=None)
    parser.add_argument("--out", default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    ledger_path = (
        Path(args.ledger)
        if args.ledger
        else data_root() / "raw" / "request_ledger.jsonl"
    )
    report = build_credit_audit(
        _load_ledger(ledger_path),
        request_category=args.request_category,
        before_balance=args.before_balance,
        after_balance=args.after_balance,
    )
    out_path = (
        Path(args.out)
        if args.out
        else data_root() / "normalized" / "sectors_credit_audit.json"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
