"""Freeze the 66-stock Sectors recording sample and its durable call budget."""
from __future__ import annotations

import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
import re

from idx_leadership.data.releases import canonical_json_bytes, validate_manifest_file
from idx_leadership.providers.persistent_budget import PersistentRequestBudget


SECTORS = (
    "Basic Materials", "Consumer Cyclicals", "Consumer Non-Cyclicals", "Energy",
    "Financials", "Healthcare", "Industrials", "Infrastructures",
    "Properties & Real Estate", "Technology", "Transportation & Logistic",
)
PRICE_START = date(2025, 12, 31)
FOREIGN_START = date(2026, 1, 1)
MAX_WINDOWS = 4
MAX_SUSPENSION_PAGES = 15
RETRY_AND_REPLACEMENT_RESERVE = 30
MAX_CALLS = 450
MAX_CREDITS = 450


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _ticker_order(row: dict) -> tuple[float, str]:
    return (-float(row["market_cap"]), str(row["ticker"]).upper())


def _eligible(row: dict, *, as_of: str) -> bool:
    ticker = str(row.get("ticker") or "").upper()
    return bool(
        row.get("signal_eligible") is True
        and row.get("instrument_type") == "LISTED_STOCK"
        and row.get("traded") is True
        and row.get("last_trade_date") == as_of
        and float(row.get("close") or 0) > 0
        and float(row.get("market_cap") or 0) > 0
        and re.fullmatch(r"[A-Z]{4,6}\.JK", ticker)
    )


def freeze_plan(*, market_path: Path, out_dir: Path, release_manifest: Path) -> dict:
    market_path = market_path.resolve(strict=True)
    release = validate_manifest_file(release_manifest.resolve(strict=True), candidate=True)
    market_family = release.manifest["families"]["market"]
    market_raw = market_path.read_bytes()
    if hashlib.sha256(market_raw).hexdigest() != market_family["sha256"]:
        raise ValueError("market file does not belong to the selected immutable release")
    market = json.loads(market_raw)
    as_of = str(market.get("as_of") or "")
    date.fromisoformat(as_of)
    eligible = [row for row in market.get("records", []) if _eligible(row, as_of=as_of)]
    ordered: dict[str, list[dict]] = {name: [] for name in SECTORS}
    for row in eligible:
        sector = (row.get("taxonomy") or {}).get("sector")
        if sector in ordered:
            ordered[sector].append(row)
    missing = {sector: len(ordered[sector]) for sector in SECTORS if len(ordered[sector]) < 6}
    if missing:
        raise ValueError(f"fewer than six eligible names in one or more sectors: {missing}")
    selections = {}
    for sector in SECTORS:
        ranked = sorted(ordered[sector], key=_ticker_order)
        selections[sector] = {
            "selected": [row["ticker"] for row in ranked[:6]],
            "replacement_order": [row["ticker"] for row in ranked[6:]],
            "market_cap_as_of": as_of,
        }
    window_schedule = {
        "price_start": PRICE_START.isoformat(),
        "foreign_start": FOREIGN_START.isoformat(),
        "end_session": "resolved once at run start from latest Sectors close",
        "maximum_windows_per_series": MAX_WINDOWS,
        "maximum_calendar_days_per_window": 90,
    }
    calls = {
        "price_windows_66_stocks": 66 * MAX_WINDOWS,
        "native_ihsg_price_windows": MAX_WINDOWS,
        "stock_foreign_flow": 66,
        "market_ytd_foreign_flow_windows": MAX_WINDOWS,
        "corporate_action_checks": 66,
        "session_probe": 1,
        "suspension_pages_allowance": MAX_SUSPENSION_PAGES,
        "metadata_pages": 0,
        "retry_and_replacement_reserve": RETRY_AND_REPLACEMENT_RESERVE,
    }
    planned_with_reserve = sum(calls.values())
    if planned_with_reserve > MAX_CALLS:
        raise ValueError(f"planned call ceiling {planned_with_reserve} exceeds {MAX_CALLS}")
    plan = {
        "schema_version": "sectors-recording-plan-v1",
        "label": "Recorded Sectors sample · 66 stocks",
        "prepared_from_release_session": as_of,
        "selection_release_id": release.release_id,
        "selection_release_manifest_sha256": release.manifest_sha256,
        "market_release_source": {"path": str(market_path), "sha256": _sha(market_raw)},
        "selection_basis": "Eligible common stocks from the selected market release, ranked by captured market capitalization descending and ticker ascending; six per sector.",
        "selection_market_cap_date": as_of,
        "membership_as_of": max(
            str((row.get("classification_as_of") or as_of)) for row in eligible
        ),
        "sectors": list(SECTORS),
        "stocks_per_sector": 6,
        "selections": selections,
        "window_schedule": window_schedule,
        "endpoints": {
            "session": "/v2/close/ (one page)",
            "price": "/v2/daily/{symbol}/",
            "benchmark": "/v2/index-daily/ihsg/",
            "stock_and_market_foreign_flow": "/v2/foreign-flow/{symbol}/ (IHSG is market-wide)",
            "corporate_actions": "/v2/company/corporate-actions/{symbol}/",
            "suspensions": "/v2/suspensions/",
        },
        "documented_cost_basis": "One credit per daily-price, native index, foreign-flow, corporate-actions, suspension, and paginated close request; retry attempts reserve again.",
        "calls": calls,
        "preflight_maximum_requests": MAX_CALLS,
        "preflight_maximum_estimated_credits": MAX_CREDITS,
        "allow_live_default": False,
        "api_key_storage": "environment only; never written to the run directory or browser bundle",
        "source_documentation": [
            "https://docs.sectors.app/api-references/v2/indonesia/transaction/daily",
            "https://docs.sectors.app/api-references/v2/indonesia/brokers/foreign-flow-by-symbol",
        ],
        "submission_release_effect": "No active-release change until every planned acquisition validates and a candidate passes the existing manifest validator.",
    }
    encoded = canonical_json_bytes(plan)
    plan_hash = _sha(encoded)
    plan["plan_sha256"] = plan_hash
    run_id = f"sectors-sample-{plan_hash[:16]}"
    plan["run_id"] = run_id
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=False)
    manifest_path = out_dir / "recording_manifest.json"
    manifest_path.write_bytes(canonical_json_bytes(plan) + b"\n")
    budget = PersistentRequestBudget.create(
        out_dir / "request_budget.json",
        run_id=run_id,
        plan_sha256=plan_hash,
        max_requests=MAX_CALLS,
        max_credits=MAX_CREDITS,
    )
    return {"status": "PREFLIGHT_PASS", "run_id": run_id, "plan_sha256": plan_hash,
            "selected_stocks": sum(len(row["selected"]) for row in selections.values()),
            "sector_counts": {sector: len(row["selected"]) for sector, row in selections.items()},
            "planned_with_reserve": planned_with_reserve, "budget": budget.snapshot(),
            "manifest": str(manifest_path)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--market-file", required=True, type=Path)
    parser.add_argument("--release-manifest", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(freeze_plan(market_path=args.market_file, release_manifest=args.release_manifest, out_dir=args.out_dir), sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"SECTORS_SAMPLE_PREFLIGHT_REFUSED: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
