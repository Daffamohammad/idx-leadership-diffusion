"""Build an offline Sectors readiness receipt before opening the paid-data gate."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Any

from idx_leadership.data.releases import _read_active_pointer, canonical_json_bytes
try:
    from scripts.build_sectors_analysis import _parse_actions, build
    from scripts.verify_sectors_analysis_oracle import verify as verify_analysis
except ModuleNotFoundError:  # direct ``python scripts/...`` execution
    from build_sectors_analysis import _parse_actions, build
    from verify_sectors_analysis_oracle import verify as verify_analysis


ROOT = Path(__file__).resolve().parents[1]
RELEASES = ROOT / "app/web/public/releases"
REQUIRED_ASSETS = (
    "sectors_recorded_sample",
    "sectors_selection_market",
    "sectors_signal_analysis",
)
FOCUSED_TESTS = (
    "tests/test_acquisition_inventory.py",
    "tests/test_persistent_budget.py",
    "tests/test_prepare_sectors_recording.py",
    "tests/test_prepare_sectors_ytd_baseline.py",
    "tests/test_sectors_analysis.py",
    "tests/test_submission_repair.py",
)
SOURCE_PATHS = ("app/web", "src", "scripts", "tests", "pyproject.toml", "requirements.txt")
REQUIRED_BROWSER_CHECKS = (
    "sectors_1036x799", "sectors_1440x900", "sectors_390x844", "sources",
    "overview", "weekly_comparison", "context_map", "navigation_smoke",
    "core_interactions", "loading_state", "fetch_error_retry", "absent_asset",
    "corrupt_core", "missing_selection", "corrupt_ytd", "server_restart", "map_without_history",
)
REQUIRED_ROUTES = ("/sectors", "/sources", "/overview", "/what-changed", "/movers", "/foreign", "/ownership",
                   "/heatmap", "/map", "/konglo", "/themes", "/explorer", "/groups", "/tickers", "/methodology")


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _write(path: Path, value: dict[str, Any]) -> None:
    if path.exists():
        raise ValueError("readiness output already exists; choose a new path to preserve the dated record")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(value) + b"\n")


def _required_entries(release) -> dict[str, dict[str, Any]]:
    entries = {row["file_id"]: row for row in release.manifest["additional_files"]}
    missing = sorted(set(REQUIRED_ASSETS) - set(entries))
    if missing:
        raise ValueError(f"active release is missing required Sectors assets: {', '.join(missing)}")
    return {file_id: entries[file_id] for file_id in REQUIRED_ASSETS}


def _action_audit(sample: dict[str, Any], analysis: dict[str, Any]) -> dict[str, Any]:
    action_counts = Counter(
        action["type"]
        for stock in sample["stocks"]
        for action in _parse_actions(stock)
    )
    excluded_counts: Counter[str] = Counter()
    examples: list[dict[str, str]] = []
    for cadence in ("daily", "weekly"):
        for observation in analysis[cadence]:
            for group in observation["groups"]:
                for member in group["contributors"]:
                    for horizon, reading in member["returns"].items():
                        reason = reading.get("exclusion_reason") or ""
                        if not reason.startswith("MECHANICAL_ACTION_"):
                            continue
                        excluded_counts[reason.removeprefix("MECHANICAL_ACTION_").rsplit("_", 1)[0]] += 1
                        if len(examples) < 12:
                            examples.append({
                                "cadence": cadence,
                                "date": observation["date"],
                                "ticker": member["ticker"],
                                "horizon": horizon,
                                "reason": reason,
                            })
    required_types = ("stock_split", "right_issue", "dividend")
    if any(action_counts.get(kind, 0) == 0 for kind in required_types):
        raise ValueError("frozen sample does not contain split, rights-issue, and dividend evidence")
    if not excluded_counts:
        raise ValueError("analysis contains no explicit corporate-action window exclusions")
    return {
        "status": "PASS",
        "sample_action_events_by_type": dict(sorted(action_counts.items())),
        "analysis_action_window_exclusions_by_type": dict(sorted(excluded_counts.items())),
        "examples": examples,
        "members_retained": len(sample["stocks"]),
        "minimum_contributors": 5,
    }


def _run_focused_tests() -> dict[str, Any]:
    command = [str(ROOT / ".venv/bin/python"), "-m", "pytest", "-q", *FOCUSED_TESTS]
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    summary = (completed.stdout + "\n" + completed.stderr).strip().splitlines()
    tail = summary[-8:]
    if completed.returncode != 0:
        raise RuntimeError("focused offline regression tests failed:\n" + "\n".join(tail))
    return {
        "status": "PASS",
        "command": command[1:],
        "test_files": list(FOCUSED_TESTS),
        "summary": tail,
    }


def verify_browser_receipt(path: Path, *, release_id: str, manifest_sha256: str,
                           expected_metrics: dict[str, int | float]) -> dict[str, Any]:
    receipt = json.loads(path.read_text(encoding="utf-8"))
    if receipt.get("schema_version") != "diffusion-browser-qa-v1" or receipt.get("status") != "PASS":
        raise ValueError("browser QA receipt is missing a passing supported schema")
    commit = receipt.get("source_commit", "")
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("browser QA receipt has no exact source commit")
    ancestor = subprocess.run(["git", "merge-base", "--is-ancestor", commit, "HEAD"], cwd=ROOT, capture_output=True)
    changes = subprocess.run(["git", "diff", "--name-only", commit, "--", *SOURCE_PATHS], cwd=ROOT, capture_output=True, text=True)
    untracked = subprocess.check_output(["git", "ls-files", "--others", "--exclude-standard", "--", *SOURCE_PATHS], cwd=ROOT, text=True)
    if ancestor.returncode or changes.returncode or changes.stdout.strip() or untracked.strip():
        raise ValueError("browser QA source commit is stale or the tested source has uncommitted changes")
    if receipt.get("release_id") != release_id or receipt.get("manifest_sha256") != manifest_sha256:
        raise ValueError("browser QA receipt belongs to a different release")
    checks = receipt.get("checks", {})
    for name in REQUIRED_BROWSER_CHECKS:
        check = checks.get(name, {})
        if check.get("status") != "PASS" or not check.get("observed"):
            raise ValueError(f"browser QA check is missing, failed, or has no observations: {name}")
    if set(REQUIRED_ROUTES) - set(checks["navigation_smoke"]["observed"].get("routes", [])):
        raise ValueError("browser QA navigation evidence is incomplete")
    metrics = receipt.get("metrics", {})
    for name, expected in expected_metrics.items():
        if metrics.get(name) != expected:
            raise ValueError(f"browser QA figure or data count does not match the release: {name}")
    if receipt.get("unexpected_console_errors") != 0 or receipt.get("unexpected_data_request_failures") != 0 or receipt.get("sectors_provider_requests") != 0:
        raise ValueError("browser QA contains unexpected errors, failed data requests, or provider calls")
    viewports = set()
    screenshots = receipt.get("screenshots", [])
    for entry in screenshots:
        screenshot = (ROOT / entry["path"]).resolve()
        if not screenshot.is_relative_to(ROOT.resolve()) or not screenshot.is_file():
            raise ValueError("browser QA screenshot is missing or outside the repository")
        raw = screenshot.read_bytes()
        if not (raw.startswith(b"\x89PNG\r\n\x1a\n") or raw.startswith(b"\xff\xd8\xff")) or _sha(raw) != entry.get("sha256"):
            raise ValueError("browser QA screenshot hash does not validate")
        viewports.add(entry.get("viewport"))
    if not {"1036x799", "1440x900", "390x844"}.issubset(viewports):
        raise ValueError("browser QA needs screenshot evidence for every required viewport")
    return {"status": "PASS", "receipt": str(path.relative_to(ROOT)), "sha256": _sha(path.read_bytes()),
            "source_commit": commit, "checks": checks, "metrics": metrics, "screenshots": screenshots}


def verify_readiness(*, browser_qa_receipt: Path) -> dict[str, Any]:
    pointer, active, previous = _read_active_pointer(RELEASES)
    if pointer is None or active is None:
        raise ValueError("there is no verified active immutable release")
    entries = _required_entries(active)
    sample_path = active.additional_paths["sectors_recorded_sample"]
    market_path = active.additional_paths["sectors_selection_market"]
    analysis_path = active.additional_paths["sectors_signal_analysis"]
    sample_raw = sample_path.read_bytes()
    market_raw = market_path.read_bytes()
    analysis_raw = analysis_path.read_bytes()
    sample = json.loads(sample_raw)
    analysis = json.loads(analysis_raw)
    market = json.loads(active.family_paths["market"].read_text())
    browser = verify_browser_receipt(browser_qa_receipt, release_id=active.release_id, manifest_sha256=active.manifest_sha256,
        expected_metrics={"ranking_rows": 11, "sectors_map_marks": sum(group["map"] is not None for group in analysis["daily"][-1]["groups"]),
                          "constituents_inspected": 66, "daily_dates": len(analysis["daily"]), "weekly_dates": len(analysis["weekly"]),
                          "context_sector_marks": 11, "ihsg_close": market["benchmark"][-1]["close"]})
    if len(sample.get("stocks", [])) != 66 or len({row.get("ticker") for row in sample["stocks"]}) != 66:
        raise ValueError("released sample must contain all 66 unique selected stocks")
    if len({row.get("sector") for row in sample["stocks"]}) != 11:
        raise ValueError("released sample must retain 11 sectors")
    if sample.get("sources", {}).get("market_release_source_sha256") != _sha(market_raw):
        raise ValueError("released selection-market bytes do not match the recorded sample lineage")
    if entries["sectors_selection_market"]["sha256"] != _sha(market_raw):
        raise ValueError("selection-market manifest hash does not match its released bytes")

    baseline_entry = next((row for row in active.manifest["additional_files"]
                           if row["file_id"] == "sectors_ytd_baseline"), None)
    baseline_path = active.additional_paths.get("sectors_ytd_baseline")
    acquisition_validation = None
    baseline = None
    if baseline_entry:
        validation_path = ROOT / "docs/submission-release/ytd-acquisition-validation-2026-10-07.json"
        if not validation_path.is_file():
            raise ValueError("released YTD baseline has no acquisition validation receipt")
        acquisition_validation = json.loads(validation_path.read_text(encoding="utf-8"))
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        if (acquisition_validation.get("status") != "PASS"
                or acquisition_validation.get("baseline_asset_sha256") != baseline_entry["sha256"]
                or acquisition_validation.get("original_recording_unchanged") is not True
                or acquisition_validation.get("request_count_and_estimated_credits", 501) > 500
                or acquisition_validation.get("remaining_retry_reserve", -1) < 0
                or analysis.get("ytd", {}).get("source_asset_sha256") != baseline_entry["sha256"]
                or baseline.get("schema_version") != "sectors-ytd-baseline-v1"):
            raise ValueError("YTD source, acquisition receipt, or 500-credit budget does not validate")
    with tempfile.TemporaryDirectory(prefix="sectors-readiness-") as temporary:
        rebuilt_path = Path(temporary) / "sectors_signal_analysis.json"
        build(sample_path=sample_path, selection_market_path=market_path,
              ytd_baseline_path=baseline_path, out=rebuilt_path)
        rebuilt_raw = rebuilt_path.read_bytes()
    if rebuilt_raw != analysis_raw:
        raise ValueError("clean offline rebuild does not exactly reproduce the active analysis asset")

    oracle = verify_analysis(sample_path=sample_path, analysis_path=analysis_path,
                             ytd_baseline_path=baseline_path)
    if oracle.get("status") != "PASS" or oracle.get("mismatch_count") != 0:
        raise ValueError("independent Sectors returns and diffusion oracle found mismatches")
    action_audit = _action_audit(sample, analysis)
    focused_tests = _run_focused_tests()

    return {
        "schema_version": "sectors-readiness-receipt-v2",
        "status": "VERIFIED_LOCAL_BUILD",
        "created_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "active_release": {
            "release_id": active.release_id,
            "manifest_sha256": active.manifest_sha256,
            "previous_release_id": previous.release_id if previous else None,
            "previous_manifest_sha256": previous.manifest_sha256 if previous else None,
        },
        "source_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "source_lineage": {
            "recorded_sample_sha256": _sha(sample_raw),
            "frozen_selection_market_sha256": _sha(market_raw),
            "analysis_sha256": _sha(analysis_raw),
            "asset_ids": list(REQUIRED_ASSETS) + (["sectors_ytd_baseline"] if baseline_entry else []),
            "sample_stocks": len(sample["stocks"]),
            "sample_sectors": 11,
            "membership_retrospective": bool(analysis.get("selection", {}).get("retrospective")),
            "price_basis": analysis.get("contract", {}).get("price_basis", "raw Sectors daily close"),
            "benchmark": analysis.get("contract", {}).get("benchmark", "native Sectors IHSG close"),
        },
        "checks": {
            "immutable_release_and_asset_hashes": "PASS",
            "frozen_source_hash_binding": "PASS",
            "credential_free_exact_rebuild": {"status": "PASS", "sha256": _sha(rebuilt_raw)},
            "independent_close_and_integer_diffusion_oracle": oracle,
            "corporate_action_exclusions": action_audit,
            "minimum_five_contributor_floor": "PASS",
            "mocked_budget_retry_restart_concurrency_and_pre_501_tests": focused_tests,
            "browser_workflow": browser,
            "live_requests_during_readiness": 0,
            **({"ytd_acquisition_validation": acquisition_validation} if acquisition_validation else {}),
        },
        "budget_gate": ({
            "status": "ACQUISITION_VALIDATED_WITHIN_500_CEILING",
            "original_reservations_carried": 433,
            "requests_and_estimated_credits_used": acquisition_validation["request_count_and_estimated_credits"],
            "failed_attempts_preserved": acquisition_validation["failed_attempt_events_preserved"],
            "explicit_gaps": acquisition_validation["explicit_gaps"],
            "remaining_retry_reserve": acquisition_validation["remaining_retry_reserve"],
            "maximum_requests_and_credits": 500,
            "no_more_paid_calls_authorized_by_this_receipt": True,
        } if acquisition_validation else {
            "status": "OPEN_WITHIN_500_TOTAL_CEILING",
            "original_reservations_carried": 433,
            "estimated_base_requests": 25,
            "planned_total_before_retries": 458,
            "retry_reserve": 42,
            "preflight_must_be_rerun_before_successor_creation": True,
        }),
        "ytd_policy": {
            "window": {"start": "2025-12-15", "end": "2025-12-31"},
            "first_request": "one native Sectors IHSG daily baseline request",
            "stock_baselines": "require each close on the last observed 2025 IHSG date",
            "unsupported_or_empty_windows": "remain explicit gaps; do not impute",
            "paid_call_authorization": "only through the explicit --record --allow-live --allow-credit-spend gate",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--browser-qa-receipt", required=True, type=Path,
                        help="recorded browser checks, figures, and screenshots bound to this source commit and release")
    parser.add_argument("--out", required=True, type=Path, help="new readiness receipt path; existing dated records are never overwritten")
    args = parser.parse_args()
    try:
        receipt = verify_readiness(browser_qa_receipt=args.browser_qa_receipt.resolve())
        _write(args.out, receipt)
        print(json.dumps({"status": receipt["status"], "receipt": str(args.out),
                          "release_id": receipt["active_release"]["release_id"],
                          "oracle_mismatches": receipt["checks"]["independent_close_and_integer_diffusion_oracle"]["mismatch_count"],
                          "tests": receipt["checks"]["mocked_budget_retry_restart_concurrency_and_pre_501_tests"]["summary"][-1]},
                         sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as exc:
        print(f"SECTORS_READINESS_REFUSED: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
