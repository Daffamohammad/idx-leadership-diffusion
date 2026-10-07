"""Read-only preflight and successor budget for shared-date Sectors YTD data."""
from __future__ import annotations

import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
import shutil
from typing import Any

from idx_leadership.data.releases import canonical_json_bytes, validate_manifest_file
from idx_leadership.providers.persistent_budget import PersistentRequestBudget
try:
    from scripts.build_sectors_analysis import _parse_actions
except ModuleNotFoundError:  # direct ``python scripts/...`` execution
    from build_sectors_analysis import _parse_actions


MAX_REQUESTS = 500
MAX_CREDITS = 500
PRICE_START = "2025-12-15"
PRICE_END = "2025-12-31"


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_base_release(path: Path):
    """Accept either a staged candidate manifest or its published form."""
    try:
        return validate_manifest_file(path, candidate=True)
    except (OSError, ValueError) as candidate_error:
        try:
            return validate_manifest_file(path, candidate=False)
        except (OSError, ValueError) as published_error:
            raise ValueError(
                "base release manifest is neither a valid candidate nor a published release: "
                f"{candidate_error}; {published_error}"
            ) from published_error


def _plan_hash(plan: dict[str, Any]) -> str:
    identity = dict(plan)
    identity.pop("run_id", None)
    declared = identity.pop("plan_sha256", None)
    actual = _sha(canonical_json_bytes(identity))
    if declared != actual:
        raise ValueError("original recording plan hash does not match its frozen contents")
    return actual


def preflight(
    *,
    original_run_dir: Path,
    base_release_manifest: Path,
    selection_market_path: Path,
) -> dict[str, Any]:
    """Inspect inputs only. This function does not create or modify any file."""
    original_run_dir = original_run_dir.resolve(strict=True)
    base_release = _validate_base_release(base_release_manifest.resolve(strict=True))
    selection_market_path = selection_market_path.resolve(strict=True)
    plan_path = original_run_dir / "recording_manifest.json"
    receipt_path = original_run_dir / "run_receipt.json"
    budget_path = original_run_dir / "request_budget.json"
    ledger_path = original_run_dir / "request_ledger.jsonl"
    sample_path = original_run_dir / "sectors_recorded_sample.json"
    plan = _read(plan_path)
    receipt = _read(receipt_path)
    budget = _read(budget_path)
    sample = _read(sample_path)
    _plan_hash(plan)
    if receipt.get("status") != "ACQUISITIONS_VALIDATED":
        raise ValueError("original Sectors sample acquisition is not complete")
    if receipt.get("run_id") != plan.get("run_id") or receipt.get("plan_sha256") != plan.get("plan_sha256"):
        raise ValueError("original Sectors sample receipt and plan differ")
    if receipt.get("sample_sha256") != _sha(sample_path.read_bytes()):
        raise ValueError("original Sectors sample bytes differ from the receipt")
    reservations = budget.get("reservations")
    if not isinstance(reservations, list):
        raise ValueError("original persistent budget has no reservation inventory")
    reserved_count = int(budget.get("requests_reserved", -1))
    reserved_credits = float(budget.get("credits_reserved", -1))
    if (reserved_count != len(reservations)
            or abs(reserved_credits - sum(float(row.get("estimated_credits", 0)) for row in reservations)) > 1e-9
            or reserved_count > 450 or reserved_credits > 450):
        raise ValueError("original budget reservation inventory is inconsistent or exceeds 450")
    receipt_budget = receipt.get("request_budget") or {}
    if (receipt_budget.get("requests_reserved") != reserved_count
            or float(receipt_budget.get("credits_reserved", -1)) != reserved_credits):
        raise ValueError("original recording receipt does not include every reserved attempt")
    if not ledger_path.is_file():
        raise ValueError("original request ledger is missing")

    market_raw = selection_market_path.read_bytes()
    market_hash = _sha(market_raw)
    if market_hash != plan.get("market_release_source", {}).get("sha256"):
        raise ValueError("frozen selection source differs from the original recording plan")
    if market_hash != sample.get("sources", {}).get("market_release_source_sha256"):
        raise ValueError("frozen selection source differs from the recorded sample")
    if base_release.manifest["target_session"] != sample.get("as_of"):
        raise ValueError("base release and original Sectors sample have different target sessions")

    sample_end = str(sample["as_of"])
    stock_requests = []
    excluded = []
    for stock in sorted(sample.get("stocks", []), key=lambda row: str(row.get("ticker"))):
        ticker = str(stock.get("ticker") or "")
        actions = [row for row in _parse_actions(stock) if "2026-01-01" <= row["date"] <= sample_end]
        if actions:
            excluded.append({"ticker": ticker, "reason": "YTD window includes a listed mechanical corporate action", "actions": actions})
        else:
            stock_requests.append(ticker)
    # The first call discovers the final observed 2025 IHSG session. Stock
    # windows are issued only afterward and must match that date exactly.
    base_requests = 1 + len(stock_requests)
    total = reserved_count + base_requests
    if total > MAX_REQUESTS or reserved_credits + base_requests > MAX_CREDITS:
        raise ValueError("baseline requests plus inherited reservations exceed the 500 ceiling")
    ledger_raw = ledger_path.read_bytes()
    budget_raw = budget_path.read_bytes()
    return {
        "status": "PREFLIGHT_PASS",
        "read_only": True,
        "transport_initialized": False,
        "original_run_id": plan["run_id"],
        "original_plan_sha256": plan["plan_sha256"],
        "original_receipt_status": receipt["status"],
        "original_request_ledger_sha256": _sha(ledger_raw),
        "original_request_ledger_bytes": len(ledger_raw),
        "original_budget_sha256": _sha(budget_raw),
        "original_reservations": reserved_count,
        "original_estimated_credits": reserved_credits,
        "original_retry_attempts_included": reserved_count,
        "selection_market_sha256": market_hash,
        "base_release_id": base_release.release_id,
        "baseline_window": {"start": PRICE_START, "end": PRICE_END, "max_calendar_days": 90},
        "planned_requests": {"native_ihsg_baseline": 1, "eligible_stock_baselines": len(stock_requests),
                              "stock_tickers": stock_requests},
        "excluded_stock_windows": excluded,
        "planned_total_requests": total,
        "planned_total_estimated_credits": reserved_credits + base_requests,
        "remaining_request_reserve_for_retries": MAX_REQUESTS - total,
        "remaining_credit_reserve_for_retries": MAX_CREDITS - (reserved_credits + base_requests),
        "maximum_requests": MAX_REQUESTS,
        "maximum_estimated_credits": MAX_CREDITS,
        "calls_made": 0,
        "files_written": [],
    }


def prepare_successor(
    *,
    original_run_dir: Path,
    base_release_manifest: Path,
    selection_market_path: Path,
    out_dir: Path,
) -> dict[str, Any]:
    """Write a distinct, seeded successor plan and budget after preflight."""
    report = preflight(original_run_dir=original_run_dir,
                       base_release_manifest=base_release_manifest,
                       selection_market_path=selection_market_path)
    original_run_dir = original_run_dir.resolve(strict=True)
    out_dir = Path(out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=False)
    parent_plan = _read(original_run_dir / "recording_manifest.json")
    prior_budget_raw = (original_run_dir / "request_budget.json").read_bytes()
    prior_budget = json.loads(prior_budget_raw)
    original_ledger_raw = (original_run_dir / "request_ledger.jsonl").read_bytes()
    plan = {
        "schema_version": "sectors-ytd-baseline-plan-v1",
        "label": "Sectors shared-date YTD baseline · successor acquisition",
        "created_from_release_id": report["base_release_id"],
        "source_recording_run_id": parent_plan["run_id"],
        "source_recording_plan_sha256": parent_plan["plan_sha256"],
        "source_recording_receipt_sha256": _sha((original_run_dir / "run_receipt.json").read_bytes()),
        "source_budget_sha256": report["original_budget_sha256"],
        "source_request_ledger_sha256": report["original_request_ledger_sha256"],
        "inherited_requests_reserved": report["original_reservations"],
        "inherited_estimated_credits": report["original_estimated_credits"],
        "selection_market_sha256": report["selection_market_sha256"],
        "baseline_window": report["baseline_window"],
        "first_request": "Native IHSG daily close; choose last observed 2025 session from its response.",
        "stock_requests": report["planned_requests"]["stock_tickers"],
        "stock_window_rule": "Request 2025-12-15 through 2025-12-31, then require a close on the exact last observed 2025 IHSG date; empty and nonmatching rows remain explicit gaps.",
        "documented_cost_basis": "One estimated credit per HTTP attempt; each retry reserves another request and credit before transport.",
        "maximum_requests": MAX_REQUESTS,
        "maximum_estimated_credits": MAX_CREDITS,
        "planned_base_requests": report["planned_requests"]["native_ihsg_baseline"] + report["planned_requests"]["eligible_stock_baselines"],
        "retry_reserve_requests": report["remaining_request_reserve_for_retries"],
        "retry_reserve_estimated_credits": report["remaining_credit_reserve_for_retries"],
        "allow_live_default": False,
        "recording_policy": "Failed calls and every retry consume the persistent 500-request/credit ceiling. Original sample files and original ledger are read-only.",
        "submission_release_effect": "No release change until the resulting baseline and successor analysis validate.",
    }
    plan_hash = _sha(canonical_json_bytes(plan))
    run_id = f"sectors-ytd-{plan_hash[:16]}"
    plan["plan_sha256"] = plan_hash
    plan["run_id"] = run_id
    plan_path = out_dir / "recording_manifest.json"
    plan_path.write_bytes(canonical_json_bytes(plan) + b"\n")
    inherited_source = {
        "run_id": prior_budget["run_id"],
        "plan_sha256": prior_budget["plan_sha256"],
        "budget_sha256": report["original_budget_sha256"],
        "request_ledger_sha256": report["original_request_ledger_sha256"],
        "requests_reserved": report["original_reservations"],
        "credits_reserved": report["original_estimated_credits"],
    }
    budget = PersistentRequestBudget.create(
        out_dir / "request_budget.json",
        run_id=run_id,
        plan_sha256=plan_hash,
        max_requests=MAX_REQUESTS,
        max_credits=MAX_CREDITS,
        initial_reservations=prior_budget["reservations"],
        inherited_budget=inherited_source,
    )
    (out_dir / "parent_request_ledger.jsonl").write_bytes(original_ledger_raw)
    return {
        **report,
        "status": "SUCCESSOR_PLAN_READY",
        "run_id": run_id,
        "plan_sha256": plan_hash,
        "successor_budget": budget.snapshot(),
        "successor_plan": str(plan_path),
        "successor_budget_path": str(out_dir / "request_budget.json"),
        "inherited_ledger_copy": str(out_dir / "parent_request_ledger.jsonl"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--preflight", action="store_true", help="read-only validation; writes no files and makes no calls")
    modes.add_argument("--prepare-successor", action="store_true", help="write a separate plan and seeded budget")
    parser.add_argument("--original-run-dir", type=Path, required=True)
    parser.add_argument("--base-release-manifest", type=Path, required=True)
    parser.add_argument("--selection-market", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path)
    args = parser.parse_args()
    try:
        if args.prepare_successor and args.out_dir is None:
            raise ValueError("--prepare-successor requires --out-dir")
        result = (preflight(original_run_dir=args.original_run_dir,
                            base_release_manifest=args.base_release_manifest,
                            selection_market_path=args.selection_market)
                  if args.preflight else
                  prepare_successor(original_run_dir=args.original_run_dir,
                                    base_release_manifest=args.base_release_manifest,
                                    selection_market_path=args.selection_market,
                                    out_dir=args.out_dir))
        print(json.dumps(result, sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"SECTORS_YTD_PREFLIGHT_REFUSED: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
