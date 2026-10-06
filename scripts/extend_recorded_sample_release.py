"""Bind a completed, validated 66-stock Sectors recording to an offline candidate."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from idx_leadership.data.releases import canonical_json_bytes, calculate_release_id, validate_manifest_file


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def attach(*, manifest_path: Path, run_dir: Path) -> dict:
    manifest_path = manifest_path.resolve(strict=True)
    run_dir = run_dir.resolve(strict=True)
    verified = validate_manifest_file(manifest_path, candidate=True)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    parent_id = verified.release_id
    if any(row.get("file_id") == "sectors_recorded_sample" for row in manifest["additional_files"]):
        raise ValueError("candidate already contains a recorded Sectors sample")

    receipt_path = run_dir / "run_receipt.json"
    plan_path = run_dir / "recording_manifest.json"
    sample_path = run_dir / "sectors_recorded_sample.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    sample = json.loads(sample_path.read_text(encoding="utf-8"))
    if receipt.get("status") != "ACQUISITIONS_VALIDATED":
        raise ValueError("Sectors recording receipt is not complete and validated")
    if receipt.get("run_id") != plan.get("run_id") or receipt.get("plan_sha256") != plan.get("plan_sha256"):
        raise ValueError("recording receipt and frozen plan do not match")
    if receipt.get("sample_sha256") != _sha(sample_path.read_bytes()):
        raise ValueError("recorded sample hash does not match the persistent receipt")
    if plan.get("selection_release_id") != parent_id or plan.get("selection_release_manifest_sha256") != verified.manifest_sha256:
        raise ValueError("the frozen 66-stock plan does not belong to this selected release")
    budget = receipt.get("request_budget") or {}
    if budget.get("max_requests") != 450 or budget.get("max_credits") != 450 or budget.get("requests_reserved", 451) > 450 or budget.get("credits_reserved", 451) > 450:
        raise ValueError("recording exceeded the persistent 450-request or 450-credit ceiling")
    if sample.get("schema_version") != "sectors-recorded-sample-v1" or sample.get("validation", {}).get("status") != "PASS":
        raise ValueError("Sectors sample validation did not pass")
    if sample.get("selection", {}).get("membership_release_session") != manifest["target_session"]:
        raise ValueError("sample membership date differs from the offline release")
    if sample.get("sources", {}).get("market_release_source_sha256") != manifest["families"]["market"]["sha256"]:
        raise ValueError("sample selection did not use this release's market family")
    if sample.get("as_of") != receipt.get("session") or sample.get("as_of") != sample.get("validation", {}).get("observed_completed_session"):
        raise ValueError("recorded session differs between sample and receipt")
    validation = sample.get("validation", {})
    if validation.get("market_flow_unexpected_sessions"):
        raise ValueError("Sectors market flow includes dates outside the native IHSG calendar")
    flow = sample.get("foreign_flow", {})
    market_flow = flow.get("market_ytd", {})
    ytd_rows = market_flow.get("values", [])
    ytd_by_date = {row["date"]: row["net_foreign_inflow_idr"] for row in ytd_rows}
    if len(ytd_by_date) != len(ytd_rows):
        raise ValueError("Sectors YTD flow contains duplicate sessions")
    expected_ytd_dates = set(flow.get("expected_market_sessions", []))
    missing_ytd_dates = sorted(expected_ytd_dates - set(ytd_by_date))
    unexpected_ytd_dates = sorted(set(ytd_by_date) - expected_ytd_dates)
    if unexpected_ytd_dates or missing_ytd_dates != sorted(validation.get("market_flow_missing_sessions", [])):
        raise ValueError("Sectors YTD flow date inventory does not match its recorded validation")
    ytd_check = flow.get("session_check", {})
    diagnostic = market_flow.get("missing_date_diagnostic", {})
    if (ytd_check.get("missing_dates", []) != missing_ytd_dates
            or ytd_check.get("observed_sessions") != len(ytd_by_date)
            or ytd_check.get("expected_sessions") != len(expected_ytd_dates)
            or ytd_check.get("ytd_complete") != (not missing_ytd_dates)
            or sorted(diagnostic.get("dates_still_missing", [])) != missing_ytd_dates):
        raise ValueError("Sectors YTD omissions are not fully enumerated in the diagnostic evidence")
    if missing_ytd_dates and not diagnostic.get("source_sha256"):
        raise ValueError("Sectors YTD omissions require a hashed targeted reconciliation response")
    if validation.get("market_flow_complete_quarter", {}).get("status") != "PASS":
        raise ValueError("complete Sectors Q3 market-flow validation did not pass")
    if len(sample.get("stocks", [])) != 66 or any(count != 6 for count in sample.get("selection", {}).get("sector_counts", {}).values()) or len(sample.get("selection", {}).get("sector_counts", {})) != 11:
        raise ValueError("recorded sample must contain exactly six names in each of 11 sectors")

    foreign_path = verified.family_paths["foreign"]
    foreign = json.loads(foreign_path.read_text(encoding="utf-8"))
    official_rows = foreign.get("daily", [])
    sectors_rows = ytd_rows
    quarter = flow.get("complete_quarter", {})
    quarter_rows = quarter.get("values", [])
    sectors_q3_by_date = {row["date"]: row["net_foreign_inflow_idr"] for row in quarter_rows}
    if len(sectors_q3_by_date) != len(quarter_rows):
        raise ValueError("Sectors Q3 flow contains duplicate sessions")
    q3_start, q3_end = quarter.get("start"), quarter.get("end")
    expected_q3_dates = {
        row["date"] for row in sample.get("price_history", {}).get("ihsg", [])
        if q3_start <= row["date"] <= q3_end
    }
    q3_check = quarter.get("session_check", {})
    if (q3_check.get("status") != "PASS" or q3_check.get("missing") != 0
            or q3_check.get("duplicates") != 0
            or q3_check.get("expected_sessions") != len(expected_q3_dates)
            or q3_check.get("observed_sessions") != len(sectors_q3_by_date)
            or set(sectors_q3_by_date) != expected_q3_dates):
        raise ValueError("Sectors Q3 series is not complete on the native IHSG session calendar")
    official_by_date = {row["as_of"]: row["net_foreign_value_idr"] for row in official_rows}
    official_q3_by_date = {day: value for day, value in official_by_date.items() if q3_start <= day <= q3_end}
    if set(official_q3_by_date) != expected_q3_dates:
        raise ValueError("official IDX Q3 series does not cover the same 64 native IHSG sessions")
    q3_dates = sorted(expected_q3_dates)
    official_q3_total = sum(official_q3_by_date[day] for day in q3_dates)
    sectors_q3_total = sum(sectors_q3_by_date[day] for day in q3_dates)
    official_ytd = next((row.get("ytd_net_foreign_value_idr") for row in official_rows if row["as_of"] == sample["as_of"]), None)
    if official_ytd is None:
        raise ValueError("official IDX release does not contain a YTD value for the recorded session")
    sectors_known_ytd = sum(ytd_by_date.values())
    sample["foreign_reconciliation"] = {
        "schema_version": "foreign-flow-reconciliation-v1",
        "provider_series": ["Official IDX", "Sectors v2 IHSG"],
        "unit": "IDR net foreign flow; positive means net foreign buying",
        "official_source": {"sha256": manifest["families"]["foreign"]["sha256"], "observation_date": foreign["as_of"], "provider": "Indonesia Stock Exchange"},
        "sectors_source": {
            "market_flow_response_hashes": {
                path: digest
                for path, digest in sample["sources"]["raw_responses"].items()
                if path.startswith(("foreign_market/", "foreign_market_reconcile/"))
            },
            "observation_date": sample["as_of"],
            "provider": "Sectors v2 IHSG endpoint",
        },
        "official_ytd": {"as_of": sample["as_of"], "total_idr": official_ytd, "provider": "Indonesia Stock Exchange"},
        "sectors_ytd": {"start": market_flow.get("start"), "end": market_flow.get("end"), "known_value_sum_idr": sectors_known_ytd, "expected_sessions": len(expected_ytd_dates), "observed_sessions": len(ytd_by_date), "missing_dates": missing_ytd_dates, "status": "COMPLETE" if not missing_ytd_dates else "PARTIAL_EXPLICIT_DATES"},
        "complete_quarter": {"start": q3_start, "end": q3_end, "session_count": len(q3_dates), "official_sum_idr": official_q3_total, "sectors_sum_idr": sectors_q3_total, "difference_idr": sectors_q3_total - official_q3_total, "status": "MATCHED" if sectors_q3_total == official_q3_total else "UNRESOLVED_SOURCE_DIFFERENCE"},
        "reported_sectors_cumulative_values": [row.get("reported_cumulative_idr") for row in sectors_rows if row.get("reported_cumulative_idr") is not None],
        "limitations": ["Provider series are retained separately; only the exact complete Q3 trading dates are compared.", "The Sectors YTD endpoint omitted the listed sessions even after a targeted check; its partial sum is not compared with official full-period YTD.", "A Q3 difference is reported without normalization or imputation."],
    }
    sample["selection"]["membership_release_id"] = parent_id
    sample["selection"]["membership_release_manifest_sha256"] = verified.manifest_sha256
    sample["sources"]["official_foreign_source_sha256"] = manifest["families"]["foreign"]["sha256"]
    sample_raw = canonical_json_bytes(sample) + b"\n"
    sample_relative = "assets/context/sectors_recorded_sample.json"
    destination = manifest_path.parent / sample_relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_path = destination.with_name(f".{destination.name}.tmp")
    temp_path.write_bytes(sample_raw)
    temp_path.replace(destination)
    digest = _sha(sample_raw)
    manifest["additional_files"].append({
        "file_id": "sectors_recorded_sample", "family": "snapshot", "path": sample_relative,
        "sha256": digest, "bytes": len(sample_raw), "schema": "sectors-recorded-sample-v1",
        "observation_date": sample["as_of"],
    })
    manifest["additional_files"].sort(key=lambda row: row["file_id"])
    parent_id_digest = _sha(parent_id.encode("ascii"))
    manifest["analytical_contracts"]["recording_parent_release_id_sha256"] = parent_id_digest
    manifest["validation"]["contract_fingerprints"] = manifest["analytical_contracts"]
    manifest["validation"]["input_hashes"]["additional_files"] = {row["file_id"]: row["sha256"] for row in manifest["additional_files"]}
    manifest["release_id"] = ""
    manifest["release_id"] = calculate_release_id(manifest)
    manifest_path.write_bytes(canonical_json_bytes(manifest) + b"\n")
    result = validate_manifest_file(manifest_path, candidate=True)
    return {
        "status": "PASS", "parent_release_id": parent_id, "release_id": result.release_id,
        "manifest_sha256": result.manifest_sha256, "sample_sha256": digest,
        "session": sample["as_of"], "sample_count": len(sample["stocks"]),
        "request_budget": budget, "foreign_reconciliation": sample["foreign_reconciliation"]["complete_quarter"],
        "candidate_manifest": str(manifest_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-manifest", required=True, type=Path)
    parser.add_argument("--run-dir", required=True, type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(attach(manifest_path=args.candidate_manifest, run_dir=args.run_dir), sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"RECORDED_SAMPLE_REFUSED: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
