"""Minimal, credit-gated Sectors live validation for credential day.

The command is a dry run unless both ``--live`` and
``--allow-credit-spend`` are present. It validates at most one page per
endpoint by default and never expands to a market-wide refresh implicitly.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from idx_leadership.models import ProviderMode
from idx_leadership.providers.factory import build_provider_from_config
from idx_leadership.providers.ledger import RequestLedger
from idx_leadership.providers.sectors_contracts import validate_sectors_payload
from idx_leadership.utils import data_root
from idx_leadership.utils.errors import IDXError


_SENSITIVE_KEY_FRAGMENTS = (
    "authorization",
    "api_key",
    "apikey",
    "secret",
    "token",
    "cookie",
    "header",
)


def sanitize_payload(value: Any) -> Any:
    """Recursively strip credentials and cached headers from a response."""
    if isinstance(value, Mapping):
        clean: dict[str, Any] = {}
        for key, child in value.items():
            lowered = str(key).lower()
            if any(fragment in lowered for fragment in _SENSITIVE_KEY_FRAGMENTS):
                clean[str(key)] = "[REDACTED]"
            else:
                clean[str(key)] = sanitize_payload(child)
        return clean
    if isinstance(value, list):
        return [sanitize_payload(item) for item in value]
    return value


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )


def _fetch_pages(
    client: Any,
    endpoint: str,
    params: Mapping[str, Any],
    *,
    max_pages: int,
    force_refresh: bool,
    expected_date: date | None = None,
) -> tuple[list[Any], list[dict[str, Any]], list[Any]]:
    offset = 0
    pages: list[Any] = []
    reports: list[dict[str, Any]] = []
    rows: list[Any] = []
    for _ in range(max_pages):
        page_params = dict(params)
        page_params.update({"limit": 30, "offset": offset})
        response = client.get(
            endpoint, page_params, use_cache=not force_refresh
        )
        payload = response.payload
        contract = validate_sectors_payload(
            endpoint,
            payload,
            expected_date=expected_date,
            raise_on_error=True,
        )
        pages.append(payload)
        reports.append(contract.to_dict())
        if isinstance(payload, Mapping):
            page_rows = payload.get("results") or []
            if isinstance(page_rows, list):
                rows.extend(page_rows)
            pagination = payload.get("pagination") or {}
            if not isinstance(pagination, Mapping) or not pagination.get("has_next"):
                break
            next_offset = pagination.get("next_offset")
            offset = int(next_offset) if next_offset is not None else offset + 30
        elif isinstance(payload, list):
            rows.extend(payload)
            break
        else:
            break
    return pages, reports, rows


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="validate_sectors_live")
    parser.add_argument("--as-of", default=None, help="Market date YYYY-MM-DD")
    parser.add_argument("--config", default="config/providers.yaml")
    parser.add_argument("--out", default=None, help="Validation artifact directory")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Select SECTORS_LIVE. This flag alone never permits an HTTP call.",
    )
    parser.add_argument(
        "--allow-credit-spend",
        action="store_true",
        help="Required with --live before any Sectors HTTP request.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the call plan and make no HTTP requests (the default behavior).",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=1,
        help="Maximum pages per endpoint (default: 1).",
    )
    parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Ignore cached payloads after all live gates pass.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.max_pages < 1:
        print("BLOCKED --max-pages must be at least 1", file=sys.stderr)
        return 2
    as_of = date.fromisoformat(args.as_of) if args.as_of else date.today()
    call_plan = {
        "provider_mode": ProviderMode.SECTORS_LIVE.value,
        "dry_run": not (
            args.live and args.allow_credit_spend and not args.dry_run
        ),
        "as_of": as_of.isoformat(),
        "max_pages_per_endpoint": args.max_pages,
        "force_refresh": bool(args.force_refresh),
        "planned_endpoints": [
            {
                "endpoint": "/v2/companies/",
                "purpose": ["auth_probe", "taxonomy"],
            },
            {
                "endpoint": "/v2/close/",
                "purpose": ["market_close", "benchmark_probe"],
            },
        ],
        "market_wide_expansion": args.max_pages > 1,
        "credit_cost": "NOT ESTIMATED — observe the request ledger",
    }

    if not args.live or args.dry_run:
        print("DRY RUN — NO SECTORS HTTP REQUESTS")
        print(json.dumps(call_plan, indent=2))
        return 0
    if not args.allow_credit_spend:
        print(
            "BLOCKED SECTORS_LIVE requires --live and --allow-credit-spend",
            file=sys.stderr,
        )
        return 2

    api_key = os.environ.get("SECTORS_API_KEY", "").strip()
    if not api_key:
        print("BLOCKED SECTORS_API_KEY is unavailable", file=sys.stderr)
        return 2

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = (
        Path(args.out)
        if args.out
        else data_root() / "raw" / "sectors_validation" / f"{as_of.isoformat()}_{stamp}"
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    ledger = RequestLedger(path=out_dir / "request_ledger.jsonl")
    report: dict[str, Any] = {
        **call_plan,
        "dry_run": False,
        "live_validation_executed": True,
        "credential_present": True,
        "sanitized_captures": [],
        "checks": {},
        "errors": [],
    }

    try:
        provider = build_provider_from_config(
            args.config,
            mode=ProviderMode.SECTORS_LIVE,
            allow_live=True,
            max_pages=args.max_pages,
            force_refresh=args.force_refresh,
            ledger=ledger,
        )

        company_pages, company_contracts, company_rows = _fetch_pages(
            provider.client,
            "/v2/companies/",
            {},
            max_pages=args.max_pages,
            force_refresh=args.force_refresh,
        )
        report["checks"]["auth"] = {
            "status": "PASS",
            "evidence": "authenticated companies response",
        }
        report["checks"]["taxonomy"] = {
            "status": "PASS" if company_rows else "FAIL",
            "rows": len(company_rows),
            "contracts": company_contracts,
            "non_null_sector_rows": sum(
                1 for row in company_rows if isinstance(row, Mapping) and row.get("sector")
            ),
        }
        for index, payload in enumerate(company_pages, start=1):
            capture = out_dir / "sanitized_fixtures" / f"companies_page_{index:03d}.json"
            _write_json(
                capture,
                {
                    "capture_kind": "SANITIZED_LIVE_SECTORS_RESPONSE",
                    "provider_mode": ProviderMode.SECTORS_LIVE.value,
                    "captured_at": stamp,
                    "payload": sanitize_payload(payload),
                },
            )
            report["sanitized_captures"].append(str(capture.relative_to(out_dir)))

        close_pages, close_contracts, close_rows = _fetch_pages(
            provider.client,
            "/v2/close/",
            {"date": as_of.isoformat()},
            max_pages=args.max_pages,
            force_refresh=args.force_refresh,
            expected_date=as_of,
        )
        report["checks"]["market_close"] = {
            "status": "PASS" if close_rows else "FAIL",
            "rows": len(close_rows),
            "contracts": close_contracts,
        }
        benchmark_rows = [
            row
            for row in close_rows
            if isinstance(row, Mapping)
            and str(row.get("symbol", "")).upper() in {"IHSG", "IHSG.JK", "^JKSE"}
        ]
        report["checks"]["benchmark"] = {
            "status": "PASS" if benchmark_rows else "NOT_FOUND_IN_FETCHED_PAGES",
            "rows": len(benchmark_rows),
            "note": (
                None
                if benchmark_rows
                else "No IHSG row appeared within --max-pages; do not infer benchmark parity."
            ),
        }
        for index, payload in enumerate(close_pages, start=1):
            capture = out_dir / "sanitized_fixtures" / f"close_page_{index:03d}.json"
            _write_json(
                capture,
                {
                    "capture_kind": "SANITIZED_LIVE_SECTORS_RESPONSE",
                    "provider_mode": ProviderMode.SECTORS_LIVE.value,
                    "captured_at": stamp,
                    "payload": sanitize_payload(payload),
                },
            )
            report["sanitized_captures"].append(str(capture.relative_to(out_dir)))
    except (IDXError, ValueError) as exc:
        report["errors"].append({"type": type(exc).__name__, "message": str(exc)})
    finally:
        ledger.flush()

    report["request_ledger"] = "request_ledger.jsonl"
    report["status"] = "PASS" if not report["errors"] and all(
        check.get("status") == "PASS"
        for check in report["checks"].values()
    ) else "REVIEW_REQUIRED"
    report_path = out_dir / "validation_report.json"
    _write_json(report_path, report)
    print(f"wrote {report_path}")
    print(json.dumps(report, indent=2, default=str))
    return 0 if report["status"] == "PASS" else 2


if __name__ == "__main__":
    sys.exit(main())
