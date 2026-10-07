"""Validate YTD acquisition receipts, raw response hashes, shared dates, and budget."""
from __future__ import annotations

import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
from typing import Any

from idx_leadership.data.releases import canonical_json_bytes
from idx_leadership.providers.sectors_normalizers import normalize_daily_history, normalize_index_daily
try:
    from scripts.prepare_sectors_ytd_baseline import _plan_hash, preflight
except ModuleNotFoundError:  # direct ``python scripts/...`` execution
    from prepare_sectors_ytd_baseline import _plan_hash, preflight


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        for key in ("results", "data", "items", "rows"):
            value = payload.get(key)
            if isinstance(value, list):
                return [row for row in value if isinstance(row, dict)]
    return []


def validate(*, run_dir: Path, original_run_dir: Path,
             base_release_manifest: Path, selection_market_path: Path) -> dict[str, Any]:
    run_dir = run_dir.resolve(strict=True)
    original_run_dir = original_run_dir.resolve(strict=True)
    plan = _read(run_dir / "recording_manifest.json")
    receipt = _read(run_dir / "run_receipt.json")
    budget = _read(run_dir / "request_budget.json")
    baseline_path = run_dir / "sectors_ytd_baseline.json"
    baseline_raw = baseline_path.read_bytes()
    baseline = _read(baseline_path)
    original_sample = _read(original_run_dir / "sectors_recorded_sample.json")
    if plan.get("schema_version") != "sectors-ytd-baseline-plan-v1" or _plan_hash(plan) != plan.get("plan_sha256"):
        raise ValueError("successor YTD plan hash or schema is invalid")
    if receipt.get("run_id") != plan.get("run_id") or receipt.get("plan_sha256") != plan.get("plan_sha256"):
        raise ValueError("YTD receipt does not match its frozen plan")
    preflight_result = preflight(original_run_dir=original_run_dir,
                                base_release_manifest=base_release_manifest,
                                selection_market_path=selection_market_path)
    if (plan.get("created_from_release_id") != preflight_result["base_release_id"]
            or plan.get("source_budget_sha256") != preflight_result["original_budget_sha256"]
            or plan.get("source_request_ledger_sha256") != preflight_result["original_request_ledger_sha256"]
            or plan.get("selection_market_sha256") != preflight_result["selection_market_sha256"]):
        raise ValueError("successor plan does not bind to the unchanged source run and frozen selection market")
    parent_budget = _read(original_run_dir / "request_budget.json")
    reservations = budget.get("reservations")
    parent_reservations = parent_budget.get("reservations")
    request_count = len(reservations) if isinstance(reservations, list) else -1
    credit_total = sum(float(row.get("estimated_credits", 0)) for row in reservations) if isinstance(reservations, list) else -1
    if (budget.get("run_id") != plan.get("run_id") or budget.get("plan_sha256") != plan.get("plan_sha256")
            or budget.get("max_requests") != 500 or budget.get("max_credits") != 500.0
            or request_count > 500 or request_count != budget.get("requests_reserved")
            or abs(credit_total - float(budget.get("credits_reserved", -1))) > 1e-9
            or reservations[:433] != parent_reservations
            or receipt.get("request_budget") != {key: budget[key] for key in
                                                  ("requests_reserved", "credits_reserved", "max_requests", "max_credits")}):
        raise ValueError("YTD budget does not match its receipt, inherited reservations, or 500 ceiling")
    if receipt.get("request_budget", {}).get("requests_reserved", 501) > 500:
        raise ValueError("request 501 was reserved")
    if receipt.get("baseline_asset_sha256") != _sha(baseline_raw):
        raise ValueError("YTD baseline bytes differ from the final acquisition receipt")
    if baseline.get("schema_version") != "sectors-ytd-baseline-v1":
        raise ValueError("YTD baseline schema is invalid")
    if baseline.get("as_of") != original_sample.get("as_of"):
        raise ValueError("YTD baseline sample date differs from the selected release")
    if baseline.get("excluded_action_windows") != preflight_result["excluded_stock_windows"]:
        raise ValueError("YTD baseline action exclusions differ from the read-only preflight")

    attempts = receipt.get("attempts")
    if not isinstance(attempts, list):
        raise ValueError("YTD receipt has no attempt inventory")
    preserved_path = run_dir / "receipts/attempt-001-initial-host-resolution-failure.json"
    if not preserved_path.is_file():
        raise ValueError("initial failed-attempt receipt was not preserved")
    preserved = _read(preserved_path)
    if (not preserved.get("attempts") or preserved["attempts"][0].get("status") != "FAILED_AFTER_RETRIES"
            or not attempts or attempts[0] != preserved["attempts"][0]):
        raise ValueError("initial failed attempt is missing from the resumed receipt history")

    successful = [row for row in attempts if row.get("status") == "PASS" and row.get("response_path")]
    for attempt in successful:
        response_path = run_dir / str(attempt["response_path"])
        raw = response_path.read_bytes()
        payload = _read(response_path)
        if _sha(raw) != attempt.get("response_sha256") or len(_rows(payload)) != attempt.get("rows_returned"):
            raise ValueError(f"raw response receipt does not match {response_path.name}")

    index_successes = [row for row in successful if row.get("kind") == "native_ihsg_baseline"]
    if not index_successes:
        raise ValueError("no successful native IHSG baseline response is recorded")
    index_attempt = index_successes[-1]
    index_payload = _read(run_dir / index_attempt["response_path"])
    index_frame = normalize_index_daily(index_payload, benchmark_id="IHSG", source="sectors")
    index_frame = index_frame[(index_frame["date"] >= date(2025, 12, 15))
                              & (index_frame["date"] <= date(2025, 12, 31))]
    if index_frame.empty:
        raise ValueError("native IHSG response has no observed date in the requested baseline window")
    last_index_date = max(index_frame["date"])
    matching_index = index_frame[index_frame["date"] == last_index_date]
    ihsg = baseline.get("ihsg") or {}
    if (len(matching_index) != 1 or ihsg.get("date") != last_index_date.isoformat()
            or abs(float(ihsg.get("close", 0)) - float(matching_index.iloc[0]["close"])) > 1e-9):
        raise ValueError("recorded IHSG baseline is not the last observed close from the native response")

    stock_successes = [row for row in successful if row.get("kind") == "stock_baseline"]
    request_tickers = set(plan.get("stock_requests", []))
    if {row.get("ticker") for row in stock_successes} != request_tickers:
        raise ValueError("successful stock response inventory differs from the planned eligible request list")
    recorded_stocks = {row["ticker"]: row for row in baseline.get("stocks", [])}
    for attempt in stock_successes:
        ticker = str(attempt["ticker"])
        payload = _read(run_dir / attempt["response_path"])
        frame = normalize_daily_history(payload, source="sectors")
        frame = frame[(frame["ticker"] == ticker) & (frame["date"] == last_index_date)]
        recorded = recorded_stocks.get(ticker)
        if frame.empty:
            if recorded is not None or not any(gap.get("ticker") == ticker and
                                               gap.get("status") == "NO_MATCHING_STOCK_BASELINE_SESSION"
                                               for gap in baseline.get("gaps", [])):
                raise ValueError(f"empty or nonmatching stock response is not preserved as a gap: {ticker}")
        elif len(frame) != 1 or recorded is None:
            raise ValueError(f"stock baseline is duplicated or missing from the normalized asset: {ticker}")
        elif (recorded.get("date") != last_index_date.isoformat()
              or abs(float(recorded.get("close", 0)) - float(frame.iloc[0]["close"])) > 1e-9
              or recorded.get("source_response_sha256") != attempt.get("response_sha256")):
            raise ValueError(f"stock baseline differs from its raw Sectors response: {ticker}")

    if len(recorded_stocks) != receipt.get("stock_baseline_count"):
        raise ValueError("receipt stock baseline count differs from the normalized baseline asset")
    if receipt.get("status") not in {"ACQUISITIONS_VALIDATED", "PARTIAL_EXPLICIT_GAPS",
                                     "PARTIAL_NO_NATIVE_IHSG_BASELINE", "PARTIAL_BUDGET_STOP"}:
        raise ValueError("YTD acquisition has an unsupported final status")
    if not baseline.get("gaps"):
        raise ValueError("empty responses and action-affected windows must remain explicit gaps")
    preflight_receipt = _read(Path(__file__).resolve().parents[1]
                              / "docs/submission-release/budget-preflight-2026-10-07.json")
    original_inventory = []
    for path in sorted(original_run_dir.rglob("*")):
        if path.is_file():
            raw = path.read_bytes()
            original_inventory.append({"path": str(path.relative_to(original_run_dir)),
                                      "sha256": _sha(raw), "bytes": len(raw)})
    inventory_hash = _sha(canonical_json_bytes(original_inventory))
    if (len(original_inventory) != preflight_receipt.get("verification", {}).get("original_file_count")
            or inventory_hash != preflight_receipt.get("verification", {}).get("original_tree_inventory_sha256")):
        raise ValueError("original acquisition files differ from the preflight immutability receipt")
    return {
        "status": "PASS",
        "run_id": plan["run_id"],
        "plan_sha256": plan["plan_sha256"],
        "receipt_status": receipt["status"],
        "baseline_asset_sha256": _sha(baseline_raw),
        "native_ihsg_baseline_date": last_index_date.isoformat(),
        "eligible_stock_requests": len(request_tickers),
        "matched_stock_baselines": len(recorded_stocks),
        "explicit_gaps": len(baseline["gaps"]),
        "failed_attempt_events_preserved": sum(row.get("status") != "PASS" for row in attempts),
        "request_count_and_estimated_credits": request_count,
        "maximum_requests_and_credits": 500,
        "remaining_retry_reserve": min(500 - request_count, int(500 - credit_total)),
        "original_recording_unchanged": True,
        "original_recording_tree_inventory_sha256": inventory_hash,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--original-run-dir", required=True, type=Path)
    parser.add_argument("--base-release-manifest", required=True, type=Path)
    parser.add_argument("--selection-market", required=True, type=Path)
    args = parser.parse_args()
    try:
        report = validate(run_dir=args.run_dir, original_run_dir=args.original_run_dir,
                          base_release_manifest=args.base_release_manifest,
                          selection_market_path=args.selection_market)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"status": "REFUSED", "error": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
