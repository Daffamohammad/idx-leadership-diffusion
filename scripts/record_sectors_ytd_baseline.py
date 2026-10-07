"""Record a shared-date Sectors IHSG and stock baseline under a 500-call ceiling."""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any

from idx_leadership.data.releases import canonical_json_bytes
from idx_leadership.models import ProviderMode
from idx_leadership.providers.ledger import RequestLedger
from idx_leadership.providers.persistent_budget import PersistentRequestBudget
from idx_leadership.providers.sectors_client import SectorsClient
from idx_leadership.providers.sectors_normalizers import normalize_daily_history, normalize_index_daily
from idx_leadership.utils.errors import CreditBudgetExceeded
from idx_leadership.utils import load_project_env

try:
    from scripts.prepare_sectors_ytd_baseline import MAX_CREDITS, MAX_REQUESTS, _plan_hash, preflight
except ModuleNotFoundError:  # direct ``python scripts/...`` execution
    from prepare_sectors_ytd_baseline import MAX_CREDITS, MAX_REQUESTS, _plan_hash, preflight


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _write_json(path: Path, value: Any) -> str:
    raw = canonical_json_bytes(value) + b"\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return _sha(raw)


def _rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        for key in ("results", "data", "items", "rows"):
            rows = payload.get(key)
            if isinstance(rows, list):
                return [row for row in rows if isinstance(row, dict)]
    return []


def _safe_error(error: Exception) -> str:
    value = str(error)
    value = re.sub(r"(?i)(api[_-]?key|token|secret|password|authorization)\s*[:=]\s*[^\s,;]+", r"\1=[redacted]", value)
    value = re.sub(r"(?i)bearer\s+[A-Za-z0-9._~+/-]+=*", "Bearer [redacted]", value)
    return value[:500]


def _previous_attempts(receipt_path: Path, *, run_id: str, plan_sha256: str) -> list[dict[str, Any]]:
    """Retain attempts when an acquisition resumes after a failed process run."""
    if not receipt_path.exists():
        return []
    previous = json.loads(receipt_path.read_text(encoding="utf-8"))
    if (previous.get("schema_version") != "sectors-ytd-baseline-receipt-v1"
            or previous.get("run_id") != run_id
            or previous.get("plan_sha256") != plan_sha256):
        raise ValueError("existing YTD receipt does not belong to this successor plan")
    attempts = previous.get("attempts", [])
    if not isinstance(attempts, list) or any(not isinstance(row, dict) for row in attempts):
        raise ValueError("existing YTD receipt contains a malformed attempt history")
    return attempts


def record_baseline(
    *,
    run_dir: Path,
    original_run_dir: Path,
    base_release_manifest: Path,
    selection_market_path: Path,
    allow_live: bool,
    allow_credit_spend: bool,
) -> dict[str, Any]:
    """Make paid requests only when both explicit CLI gates are provided."""
    run_dir = run_dir.resolve(strict=True)
    original_run_dir = original_run_dir.resolve(strict=True)
    if not allow_live or not allow_credit_spend:
        raise ValueError("live acquisition requires both --allow-live and --allow-credit-spend")
    plan_path = run_dir / "recording_manifest.json"
    receipt_path = run_dir / "run_receipt.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan_digest = _plan_hash(plan)
    if plan.get("schema_version") != "sectors-ytd-baseline-plan-v1":
        raise ValueError("successor YTD plan has an unsupported schema")
    previous_attempts = _previous_attempts(
        receipt_path, run_id=plan["run_id"], plan_sha256=plan["plan_sha256"]
    )
    source_check = preflight(original_run_dir=original_run_dir,
                             base_release_manifest=base_release_manifest,
                             selection_market_path=selection_market_path)
    if (source_check["original_budget_sha256"] != plan.get("source_budget_sha256")
            or source_check["original_request_ledger_sha256"] != plan.get("source_request_ledger_sha256")
            or source_check["original_plan_sha256"] != plan.get("source_recording_plan_sha256")):
        raise ValueError("original recording or ledger changed after the successor budget was prepared")
    if plan.get("created_from_release_id") != source_check["base_release_id"]:
        raise ValueError("successor YTD plan belongs to another immutable release")
    budget = PersistentRequestBudget(run_dir / "request_budget.json", run_id=plan["run_id"], plan_sha256=plan_digest)
    initial_budget = budget.snapshot()
    parent_budget = json.loads((original_run_dir / "request_budget.json").read_text(encoding="utf-8"))
    current_budget = json.loads((run_dir / "request_budget.json").read_text(encoding="utf-8"))
    reservations = current_budget.get("reservations")
    parent_reservations = parent_budget.get("reservations")
    inherited_count = int(plan.get("inherited_requests_reserved", -1))
    inherited_credits = float(plan.get("inherited_estimated_credits", -1))
    if (initial_budget["max_requests"] != MAX_REQUESTS or initial_budget["max_credits"] != MAX_CREDITS
            or not isinstance(reservations, list) or not isinstance(parent_reservations, list)
            or reservations[:inherited_count] != parent_reservations
            or len(reservations) != initial_budget["requests_reserved"]
            or abs(sum(float(row.get("estimated_credits", 0)) for row in reservations)
                   - initial_budget["credits_reserved"]) > 1e-9
            or initial_budget["requests_reserved"] < inherited_count
            or initial_budget["credits_reserved"] + 1e-9 < inherited_credits
            or initial_budget["requests_reserved"] > MAX_REQUESTS
            or initial_budget["credits_reserved"] > MAX_CREDITS):
        raise ValueError("successor persistent budget does not preserve the inherited prefix or 500 ceiling")
    prior_receipt_budget = {"requests_reserved": inherited_count,
                            "credits_reserved": inherited_credits}
    if receipt_path.is_file():
        prior_receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        prior_receipt_budget = prior_receipt.get("request_budget") or {}
        if (int(prior_receipt_budget.get("requests_reserved", -1)) > initial_budget["requests_reserved"]
                or float(prior_receipt_budget.get("credits_reserved", -1)) > initial_budget["credits_reserved"]):
            raise ValueError("successor receipt is ahead of its durable persistent budget")
    known_requests = int(prior_receipt_budget.get("requests_reserved", inherited_count))
    if not inherited_count <= known_requests <= initial_budget["requests_reserved"]:
        raise ValueError("successor receipt reservation count is outside the inherited budget")
    known_credits = sum(float(row.get("estimated_credits", 0)) for row in reservations[:known_requests])
    if abs(known_credits - float(prior_receipt_budget.get("credits_reserved", -1))) > 1e-9:
        raise ValueError("successor receipt and persistent reservations differ")
    # A crash may occur after a durable reservation but before its receipt is
    # flushed. Preserve such rows explicitly with an unknown outcome on resume.
    recovered_attempts = [
        {"kind": "recovered_reserved_attempt", "status": "OUTCOME_UNKNOWN_AFTER_RESERVATION",
         "sequence": row.get("sequence"), "endpoint": row.get("endpoint"),
         "estimated_credits": row.get("estimated_credits")}
        for row in reservations[known_requests:]
    ]
    previous_attempts.extend(recovered_attempts)
    remaining_requests = MAX_REQUESTS - initial_budget["requests_reserved"]
    remaining_credits = MAX_CREDITS - initial_budget["credits_reserved"]

    load_project_env()
    api_key = os.environ.get("SECTORS_API_KEY", "")
    if not api_key.strip():
        receipt = {
            "schema_version": "sectors-ytd-baseline-receipt-v1",
            "status": "BLOCKED_NO_CREDENTIALS",
            "run_id": plan["run_id"],
            "plan_sha256": plan["plan_sha256"],
            "request_budget": budget.snapshot(),
            "attempts": previous_attempts,
            "error": "SECTORS_API_KEY is not configured; no transport was initialized.",
        }
        _write_json(receipt_path, receipt)
        return receipt

    ledger = RequestLedger(path=run_dir / "request_ledger.jsonl")
    client = SectorsClient(
        api_key=api_key,
        allow_live=True,
        mode=ProviderMode.SECTORS_LIVE,
        ledger=ledger,
        force_refresh=True,
        max_retries=2,
        backoff_seconds=1.5,
        min_request_interval_seconds=2.2,
        max_estimated_credits=remaining_credits,
        max_http_requests=remaining_requests,
        budget_reserver=budget.reserve,
    )
    sample = json.loads((original_run_dir / "sectors_recorded_sample.json").read_text(encoding="utf-8"))
    attempts: list[dict[str, Any]] = list(previous_attempts)
    stocks: list[dict[str, Any]] = []
    gaps = [
        {"ticker": item["ticker"], "status": "SKIPPED_ACTION_AFFECTED_YTD_WINDOW",
         "reason": item["reason"], "actions": item["actions"]}
        for item in source_check["excluded_stock_windows"]
    ]
    index_row = None
    baseline_date = None
    stop_reason = None

    def record_parse_failure(kind: str, error: Exception, ticker: str | None = None) -> None:
        if attempts and attempts[-1].get("kind") == kind and attempts[-1].get("ticker") == ticker:
            attempts[-1].update({"status": "PAYLOAD_PARSE_FAILED", "error": _safe_error(error)})
        status = "MALFORMED_NATIVE_BASELINE_RESPONSE" if kind == "native_ihsg_baseline" else "MALFORMED_STOCK_BASELINE_RESPONSE"
        gaps.append({"ticker": ticker or "IHSG", "status": status, "reason": _safe_error(error)})

    def persist(status: str, *, extra: dict[str, Any] | None = None) -> None:
        receipt = {
            "schema_version": "sectors-ytd-baseline-receipt-v1",
            "status": status,
            "run_id": plan["run_id"],
            "plan_sha256": plan["plan_sha256"],
            "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "base_release_id": plan["created_from_release_id"],
            "original_run_id": plan["source_recording_run_id"],
            "original_request_ledger_sha256": plan["source_request_ledger_sha256"],
            "request_budget": budget.snapshot(),
            "attempts": attempts,
            "baseline_date": baseline_date,
            "stock_baseline_count": len(stocks),
            "gap_count": len(gaps),
            "stop_reason": stop_reason,
        }
        if extra:
            receipt.update(extra)
        _write_json(receipt_path, receipt)

    def request(endpoint: str, params: dict[str, str], relative: str, kind: str, ticker: str | None = None):
        nonlocal stop_reason
        event: dict[str, Any] = {"kind": kind, "ticker": ticker, "endpoint": endpoint, "parameters": params}
        try:
            response = client.get(endpoint, params, use_cache=False)
            payload = response.payload
            response_hash = _write_json(run_dir / "responses" / relative, payload)
            event.update({"status": "PASS", "response_sha256": response_hash,
                          "response_path": f"responses/{relative}", "rows_returned": len(_rows(payload))})
            attempts.append(event)
            return payload
        except CreditBudgetExceeded as exc:
            event.update({"status": "BLOCKED_BEFORE_TRANSPORT", "error": _safe_error(exc)})
            attempts.append(event)
            stop_reason = "PERSISTENT_BUDGET_LIMIT"
            return None
        except Exception as exc:  # failed calls and their retries remain in the budget and ledger
            event.update({"status": "FAILED_AFTER_RETRIES", "error": _safe_error(exc)})
            attempts.append(event)
            return None
        finally:
            ledger.flush()
            persist("IN_PROGRESS")

    try:
        index_payload = request(
            "/v2/index-daily/ihsg/",
            {"start": "2025-12-15", "end": "2025-12-31"},
            "index/ihsg_2025-12-15_2025-12-31.json",
            "native_ihsg_baseline",
        )
        if index_payload is not None:
            try:
                frame = normalize_index_daily(index_payload, benchmark_id="IHSG", source="sectors")
                frame = frame[
                    (frame["date"] >= date(2025, 12, 15)) & (frame["date"] <= date(2025, 12, 31))
                ]
                if not frame.empty:
                    last_date = max(frame["date"])
                    date_rows = frame[frame["date"] == last_date]
                    if len(date_rows) == 1:
                        baseline_date = last_date.isoformat()
                        index_row = {"date": baseline_date, "close": float(date_rows.iloc[0]["close"]),
                                     "price_basis": "close"}
                    else:
                        gaps.append({"ticker": "IHSG", "status": "DUPLICATE_NATIVE_BASELINE_DATE",
                                     "date": last_date.isoformat(), "rows": len(date_rows)})
                if baseline_date is None:
                    gaps.append({"ticker": "IHSG", "status": "NO_OBSERVED_2025_BASELINE",
                                 "reason": "Native Sectors index response contains no unique 2025 close in the requested window."})
            except (ValueError, TypeError, KeyError) as exc:
                record_parse_failure("native_ihsg_baseline", exc)
        else:
            gaps.append({"ticker": "IHSG", "status": "NO_NATIVE_IHSG_BASELINE_RESPONSE",
                         "reason": "The native IHSG request failed after its reserved attempts."})

        if baseline_date is not None and stop_reason is None:
            for ticker in plan["stock_requests"]:
                relative = f"prices/{ticker.replace('.', '_')}_2025-12-15_2025-12-31.json"
                payload = request(
                    f"/v2/daily/{ticker}/",
                    {"start": "2025-12-15", "end": "2025-12-31"},
                    relative,
                    "stock_baseline",
                    ticker,
                )
                if payload is None:
                    gaps.append({"ticker": ticker, "status": "REQUEST_FAILED_OR_BUDGET_BLOCKED",
                                 "reason": "No matching stock baseline was recorded; inspect the attempt receipt."})
                    if stop_reason:
                        break
                    continue
                try:
                    frame = normalize_daily_history(payload, source="sectors")
                    frame = frame[frame["ticker"] == ticker]
                except (ValueError, TypeError, KeyError) as exc:
                    record_parse_failure("stock_baseline", exc, ticker)
                    continue
                if any(day < date(2025, 12, 15) or day > date(2025, 12, 31) for day in frame["date"]):
                    gaps.append({"ticker": ticker, "status": "UNEXPECTED_RESPONSE_DATE",
                                 "reason": "Response contains a session outside the requested date range."})
                    continue
                matching = frame[frame["date"] == date.fromisoformat(baseline_date)]
                if len(matching) == 1:
                    event = attempts[-1]
                    stocks.append({"ticker": ticker, "date": baseline_date,
                                   "close": float(matching.iloc[0]["close"]),
                                   "source_response_sha256": event["response_sha256"]})
                elif len(matching) > 1:
                    gaps.append({"ticker": ticker, "status": "DUPLICATE_STOCK_BASELINE_DATE",
                                 "date": baseline_date, "rows": len(matching)})
                else:
                    gaps.append({"ticker": ticker, "status": "NO_MATCHING_STOCK_BASELINE_SESSION",
                                 "baseline_date": baseline_date,
                                 "response_rows": len(frame)})
    finally:
        ledger.flush()

    baseline_asset = {
        "schema_version": "sectors-ytd-baseline-v1",
        "as_of": sample["as_of"],
        "status": "PASS" if index_row else "PARTIAL_EXPLICIT_GAPS",
        "baseline_date": baseline_date,
        "ihsg": index_row,
        "stocks": sorted(stocks, key=lambda row: row["ticker"]),
        "gaps": sorted(gaps, key=lambda row: (str(row.get("ticker")), str(row.get("status")))),
        "excluded_action_windows": source_check["excluded_stock_windows"],
        "source": {
            "provider": "Sectors API v2",
            "index_endpoint": "/v2/index-daily/ihsg/",
            "stock_endpoint": "/v2/daily/{symbol}/",
            "request_window": {"start": "2025-12-15", "end": "2025-12-31"},
        },
        "request_attempts": attempts,
        "request_budget": budget.snapshot(),
        "limitations": [
            "YTD uses only a stock close observed on the same date as the final observed 2025 native IHSG close.",
            "Empty responses, missing baseline dates, and action-affected windows remain explicit gaps.",
            "One estimated credit is reserved before every HTTP attempt, including retries and failed attempts.",
        ],
    }
    asset_sha = _write_json(run_dir / "sectors_ytd_baseline.json", baseline_asset)
    if stop_reason:
        status = "PARTIAL_BUDGET_STOP"
    elif not index_row:
        status = "PARTIAL_NO_NATIVE_IHSG_BASELINE"
    elif any(event["status"] != "PASS" for event in attempts):
        status = "PARTIAL_EXPLICIT_GAPS"
    else:
        status = "ACQUISITIONS_VALIDATED"
    final = {
        "schema_version": "sectors-ytd-baseline-receipt-v1",
        "status": status,
        "run_id": plan["run_id"],
        "plan_sha256": plan["plan_sha256"],
        "base_release_id": plan["created_from_release_id"],
        "original_run_id": plan["source_recording_run_id"],
        "original_request_ledger_sha256": plan["source_request_ledger_sha256"],
        "request_budget": budget.snapshot(),
        "baseline_date": baseline_date,
        "native_ihsg_baseline": index_row,
        "stock_baseline_count": len(stocks),
        "gap_count": len(baseline_asset["gaps"]),
        "attempts": attempts,
        "baseline_asset": "sectors_ytd_baseline.json",
        "baseline_asset_sha256": asset_sha,
        "stop_reason": stop_reason,
    }
    _write_json(receipt_path, final)
    return final


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--original-run-dir", required=True, type=Path)
    parser.add_argument("--base-release-manifest", required=True, type=Path)
    parser.add_argument("--selection-market", required=True, type=Path)
    parser.add_argument("--record", action="store_true")
    parser.add_argument("--allow-live", action="store_true")
    parser.add_argument("--allow-credit-spend", action="store_true")
    args = parser.parse_args()
    try:
        if not args.record:
            raise ValueError("pass --record to start the explicitly gated acquisition")
        report = record_baseline(run_dir=args.run_dir,
                                 original_run_dir=args.original_run_dir,
                                 base_release_manifest=args.base_release_manifest,
                                 selection_market_path=args.selection_market,
                                 allow_live=args.allow_live,
                                 allow_credit_spend=args.allow_credit_spend)
        print(json.dumps(report, sort_keys=True))
        return 0 if report["status"] in {"ACQUISITIONS_VALIDATED", "PARTIAL_EXPLICIT_GAPS",
                                         "PARTIAL_NO_NATIVE_IHSG_BASELINE", "PARTIAL_BUDGET_STOP"} else 1
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"SECTORS_YTD_RECORDING_REFUSED: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
