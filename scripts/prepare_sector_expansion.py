"""Freeze a 132-stock Sectors expansion and its separate 221-credit ceiling."""
from __future__ import annotations

import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from idx_leadership.data.releases import canonical_json_bytes, validate_manifest_file
from idx_leadership.providers.persistent_budget import PersistentRequestBudget
from idx_leadership.providers.sectors import _plan_windows
from scripts.build_sectors_analysis import _replay_dates


SECTORS = (
    "Basic Materials", "Consumer Cyclicals", "Consumer Non-Cyclicals", "Energy",
    "Financials", "Healthcare", "Industrials", "Infrastructures",
    "Properties & Real Estate", "Technology", "Transportation & Logistic",
)
STOCKS_PER_SECTOR = 12
LEGACY_STOCKS_PER_SECTOR = 6
ADDED_STOCKS = len(SECTORS) * (STOCKS_PER_SECTOR - LEGACY_STOCKS_PER_SECTOR)
PRICE_WINDOWS_PER_STOCK = 2
CALLS_PER_ADDED_STOCK = PRICE_WINDOWS_PER_STOCK + 1  # price windows plus one action check
PLANNED_CALLS = ADDED_STOCKS * CALLS_PER_ADDED_STOCK
RETRY_RESERVE = 23
MAX_REQUESTS = 221
MAX_CREDITS = 221
MAX_WINDOW_DAYS = 90


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _eligible(row: dict[str, Any], *, as_of: str) -> bool:
    ticker = str(row.get("ticker") or "").upper()
    try:
        close = float(row.get("close") or 0)
        market_cap = float(row.get("market_cap") or 0)
    except (TypeError, ValueError):
        return False
    return bool(
        row.get("signal_eligible") is True
        and row.get("instrument_type") == "LISTED_STOCK"
        and row.get("traded") is True
        and row.get("last_trade_date") == as_of
        and close > 0
        and market_cap > 0
        and re.fullmatch(r"[A-Z]{4,6}\.JK", ticker)
    )


def _rank(row: dict[str, Any]) -> tuple[float, str]:
    return (-float(row["market_cap"]), str(row["ticker"]).upper())


def freeze_plan(*, base_manifest_path: Path, out_dir: Path) -> dict[str, Any]:
    base_manifest_path = base_manifest_path.resolve(strict=True)
    base_payload = _read(base_manifest_path)
    is_candidate = any("candidate_path" in row for row in base_payload.get("source_evidence", []))
    base = validate_manifest_file(base_manifest_path, candidate=is_candidate)
    entries = {row["file_id"]: row for row in base.manifest.get("additional_files", [])}
    required = {"sectors_recorded_sample", "sectors_selection_market", "sectors_ytd_baseline"}
    if missing := required - set(entries):
        raise ValueError(f"base release is missing required Sectors assets: {sorted(missing)}")

    sample_path = base.root / entries["sectors_recorded_sample"]["path"]
    market_path = base.root / entries["sectors_selection_market"]["path"]
    baseline_path = base.root / entries["sectors_ytd_baseline"]["path"]
    sample_raw, market_raw, baseline_raw = sample_path.read_bytes(), market_path.read_bytes(), baseline_path.read_bytes()
    sample, market = _read(sample_path), _read(market_path)
    market_hash = _sha(market_raw)
    if sample.get("schema_version") != "sectors-recorded-sample-v1" or len(sample.get("stocks", [])) != 66:
        raise ValueError("the base release must contain the original 66-stock Sectors set")
    if market.get("schema_version") != "market-workspace-v1" or market.get("as_of") != "2026-10-02":
        raise ValueError("the pinned market source must be the 2 October 2026 market data")
    if sample.get("sources", {}).get("market_release_source_sha256") != market_hash:
        raise ValueError("the base stock set does not use the supplied pinned market source")
    if entries["sectors_selection_market"]["sha256"] != market_hash:
        raise ValueError("the market source file hash differs from the base release manifest")
    if sample.get("as_of") != "2026-10-02" or sample.get("selection", {}).get("selected_market_cap_date") != "2026-10-02":
        raise ValueError("the base stock set is not aligned to the 2 October 2026 target")

    eligible_by_sector: dict[str, list[dict[str, Any]]] = {sector: [] for sector in SECTORS}
    for row in market.get("records", []):
        if not isinstance(row, dict) or not _eligible(row, as_of=market["as_of"]):
            continue
        sector = (row.get("taxonomy") or {}).get("sector")
        if sector in eligible_by_sector:
            eligible_by_sector[sector].append(row)

    original_by_sector: dict[str, set[str]] = {sector: set() for sector in SECTORS}
    for stock in sample["stocks"]:
        original_by_sector[str(stock["sector"])].add(str(stock["ticker"]).upper())
    if len({str(stock["ticker"]).upper() for stock in sample["stocks"]}) != 66:
        raise ValueError("the base stock set contains duplicate tickers")

    selection_rows: dict[str, dict[str, Any]] = {}
    additions: list[dict[str, str]] = []
    all_members: list[dict[str, str]] = []
    for sector in SECTORS:
        ranked = sorted(eligible_by_sector[sector], key=_rank)
        if len(ranked) < STOCKS_PER_SECTOR:
            raise ValueError(f"fewer than 12 eligible names in the pinned market source: {sector}")
        top_six = [str(row["ticker"]).upper() for row in ranked[:LEGACY_STOCKS_PER_SECTOR]]
        if original_by_sector[sector] != set(top_six):
            raise ValueError(f"the original six names no longer match the pinned market ranking: {sector}")
        next_six = [str(row["ticker"]).upper() for row in ranked[6:12]]
        combined = top_six + next_six
        selection_rows[sector] = {
            "original": top_six,
            "additions": next_six,
            "selected": combined,
            "market_cap_as_of": market["as_of"],
            "ranked_eligible_count": len(ranked),
        }
        additions.extend({"ticker": ticker, "sector": sector} for ticker in next_six)
        all_members.extend({"ticker": ticker, "sector": sector} for ticker in combined)
    if len(additions) != ADDED_STOCKS or len({row["ticker"] for row in all_members}) != 132:
        raise ValueError("the frozen expansion does not contain 132 unique names")

    benchmark = sample.get("price_history", {}).get("ihsg", [])
    benchmark_dates = sorted({date.fromisoformat(str(row["date"])) for row in benchmark if row.get("date")})
    replay_dates, weekly_dates = _replay_dates(
        __import__("pandas").DataFrame({"date": benchmark_dates}), sample["as_of"]
    )
    first_replay_index = benchmark_dates.index(replay_dates[0])
    if first_replay_index < 60:
        raise ValueError("native IHSG history does not provide a 60-session lead-in for the replay")
    price_start = benchmark_dates[first_replay_index - 60]
    price_end = date.fromisoformat(sample["as_of"])
    windows = _plan_windows(price_start, price_end, max_window_days=MAX_WINDOW_DAYS)
    if len(windows) != PRICE_WINDOWS_PER_STOCK:
        raise ValueError(f"the full replay needs {len(windows)} price windows, expected two")
    if any((end - start).days > MAX_WINDOW_DAYS for start, end in windows):
        raise ValueError("a planned price window exceeds the 90-calendar-day provider limit")

    plan: dict[str, Any] = {
        "schema_version": "sectors-expansion-plan-v1",
        "label": "132 stocks across 11 IDX sectors",
        "base_release": {
            "release_id": base.release_id,
            "manifest_path": str(base_manifest_path.resolve()),
            "manifest_sha256": base.manifest_sha256,
            "is_candidate": is_candidate,
            "sample_sha256": _sha(sample_raw),
            "ytd_baseline_sha256": _sha(baseline_raw),
        },
        "market_release_source": {
            "path": str(market_path.resolve()),
            "sha256": market_hash,
            "as_of": market["as_of"],
        },
        "selection_release_id": sample["selection"]["membership_release_id"],
        "selection_release_manifest_sha256": sample["selection"].get("membership_release_manifest_sha256"),
        "selections": selection_rows,
        "selection": {
            "basis": "Eligible listed common stocks ranked by 2 October 2026 market capitalization, descending; ticker ascending breaks ties.",
            "selected_market_cap_date": market["as_of"],
            "stock_count": 132,
            "stocks_per_sector": 12,
            "sectors": list(SECTORS),
            "selections": selection_rows,
            "members": all_members,
            "additions": additions,
        },
        "coverage": {
            "target_date": sample["as_of"],
            "daily_replay_dates": [row.isoformat() for row in replay_dates],
            "weekly_replay_dates": [row.isoformat() for row in weekly_dates],
            "first_replay_date": replay_dates[0].isoformat(),
            "first_required_price_date": price_start.isoformat(),
            "price_end_date": price_end.isoformat(),
            "price_windows": [[start.isoformat(), end.isoformat()] for start, end in windows],
            "maximum_calendar_days_per_window": MAX_WINDOW_DAYS,
            "ytd_stock_count": 66,
            "ytd_end_date": sample["as_of"],
            "company_flow_stock_count": 66,
            "company_flow_end_date": sample["as_of"],
        },
        "budget": {
            "planned_price_requests": ADDED_STOCKS * PRICE_WINDOWS_PER_STOCK,
            "planned_action_checks": ADDED_STOCKS,
            "planned_requests": PLANNED_CALLS,
            "planned_credits": PLANNED_CALLS,
            "retry_reserve": RETRY_RESERVE,
            "hard_request_ceiling": MAX_REQUESTS,
            "hard_credit_ceiling": MAX_CREDITS,
        },
        "request_plan": {
            ticker: {
                "sector": sector,
                "price_windows": [[start.isoformat(), end.isoformat()] for start, end in windows],
                "corporate_action_check": True,
            }
            for ticker, sector in ((row["ticker"], row["sector"]) for row in additions)
        },
        "provider": "Sectors API",
        "allow_live_default": False,
        "api_key_storage": "environment only",
        "activation": "Keep the 66-stock release active until a separate activation step.",
    }
    if PLANNED_CALLS + RETRY_RESERVE != MAX_REQUESTS or MAX_CREDITS != MAX_REQUESTS:
        raise ValueError("the 221-credit ceiling no longer matches the planned calls and retry reserve")
    plan_hash = _sha(canonical_json_bytes(plan))
    plan["plan_sha256"] = plan_hash
    run_id = f"sectors-expansion-{plan_hash[:16]}"
    plan["run_id"] = run_id

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=False)
    (out_dir / "expansion_plan.json").write_bytes(canonical_json_bytes(plan) + b"\n")
    budget = PersistentRequestBudget.create(
        out_dir / "request_budget.json",
        run_id=run_id,
        plan_sha256=plan_hash,
        max_requests=MAX_REQUESTS,
        max_credits=MAX_CREDITS,
    )
    return {
        "status": "PREFLIGHT_PASS",
        "run_id": run_id,
        "plan_sha256": plan_hash,
        "original_stocks": 66,
        "added_stocks": len(additions),
        "total_stocks": len(all_members),
        "sector_counts": {sector: len(record["selected"]) for sector, record in selection_rows.items()},
        "daily_dates": len(replay_dates),
        "weekly_dates": len(weekly_dates),
        "price_windows_per_added_stock": len(windows),
        "planned_credits": PLANNED_CALLS,
        "retry_reserve": RETRY_RESERVE,
        "hard_ceiling": MAX_CREDITS,
        "budget": budget.snapshot(),
        "plan_path": str(out_dir / "expansion_plan.json"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-manifest", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(freeze_plan(base_manifest_path=args.base_manifest, out_dir=args.out_dir), sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"SECTORS_EXPANSION_PREFLIGHT_REFUSED: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
