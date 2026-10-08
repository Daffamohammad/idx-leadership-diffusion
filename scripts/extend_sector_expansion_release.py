"""Build a staged 132-stock release without changing the active release."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import tempfile
from typing import Any

from idx_leadership.data.releases import (
    calculate_release_id,
    canonical_json_bytes,
    validate_manifest_file,
)
from scripts.build_sectors_analysis import HORIZONS, MINIMUM_CONTRIBUTORS, SCHEMA, build


ROOT = Path(__file__).resolve().parents[1]
MAX_REQUESTS = 221
MAX_CREDITS = 221


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _write_atomic(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _link_or_copy(source: str, destination: str) -> str:
    try:
        os.link(source, destination)
        return destination
    except OSError:
        shutil.copy2(source, destination)
        return destination


def _copy_candidate(base: Path, destination: Path) -> None:
    if destination.exists():
        raise FileExistsError(f"candidate destination already exists: {destination}")
    shutil.copytree(base, destination, copy_function=_link_or_copy)
    for path in (destination, *destination.rglob("*")):
        if path.is_dir() and not path.is_symlink():
            path.chmod(path.stat().st_mode | stat.S_IWUSR | stat.S_IXUSR)


def _entry(file_id: str, path: str, raw: bytes, schema: str, as_of: str) -> dict[str, Any]:
    return {
        "file_id": file_id,
        "family": "snapshot",
        "path": path,
        "sha256": _sha(raw),
        "bytes": len(raw),
        "schema": schema,
        "observation_date": as_of,
    }


def _bind_candidate_sources(manifest: dict[str, Any], destination: Path) -> None:
    wanted = {row["sha256"] for row in manifest["source_evidence"]}
    found: dict[str, Path] = {}
    for directory in (ROOT / "docs/submission-release", ROOT / "data"):
        for path in sorted(directory.rglob("*")):
            if not path.is_file() or path.is_symlink():
                continue
            try:
                digest = _sha(path.read_bytes())
            except OSError:
                continue
            if digest in wanted:
                found.setdefault(digest, path)
    missing = [row["source_id"] for row in manifest["source_evidence"] if row["sha256"] not in found]
    if missing:
        raise ValueError(f"saved source files are incomplete for this candidate: {missing}")
    for row in manifest["source_evidence"]:
        relative = Path("evidence") / "original-sources" / row["source_id"] / row["file_name"]
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(found[row["sha256"]], target)
        row["candidate_path"] = relative.as_posix()


def extend(*, base_manifest_path: Path, run_dir: Path, out_dir: Path) -> dict[str, Any]:
    base_manifest_path = base_manifest_path.resolve(strict=True)
    base_payload = _read(base_manifest_path)
    base_is_candidate = any("candidate_path" in row for row in base_payload.get("source_evidence", []))
    base = validate_manifest_file(base_manifest_path, candidate=base_is_candidate)
    run_dir = run_dir.resolve(strict=True)
    plan_path = run_dir / "expansion_plan.json"
    acquisition_path = run_dir / "sectors_expansion_acquisition.json"
    receipt_path = run_dir / "expansion_receipt.json"
    plan, acquisition, receipt = _read(plan_path), _read(acquisition_path), _read(receipt_path)
    plan_body = dict(plan)
    declared_plan_hash = plan_body.pop("plan_sha256", None)
    run_id = plan_body.pop("run_id", None)
    plan_hash = _sha(canonical_json_bytes(plan_body))
    if declared_plan_hash != plan_hash or run_id != f"sectors-expansion-{plan_hash[:16]}":
        raise ValueError("frozen expansion plan hash is invalid")
    if (plan.get("base_release", {}).get("release_id") != base.release_id
            or plan.get("base_release", {}).get("manifest_sha256") != base.manifest_sha256
            or plan.get("base_release", {}).get("is_candidate") != base_is_candidate):
        raise ValueError("candidate base release differs from the pinned plan")
    if receipt.get("status") != "ACQUISITION_VALIDATED" or receipt.get("run_id") != run_id or receipt.get("plan_sha256") != plan_hash:
        raise ValueError("the expansion receipt does not show a complete, validated acquisition")
    acquisition_raw = acquisition_path.read_bytes()
    if receipt.get("acquisition_sha256") != _sha(acquisition_raw) or acquisition.get("plan_sha256") != plan_hash:
        raise ValueError("the expansion data does not match its durable receipt and frozen plan")
    if acquisition.get("schema_version") != "sectors-expansion-acquisition-v1" or acquisition.get("validation", {}).get("status") != "PASS":
        raise ValueError("the added price and action data did not pass acquisition checks")
    budget = receipt.get("request_budget") or {}
    if (budget.get("max_requests") != MAX_REQUESTS or budget.get("max_credits") != MAX_CREDITS
            or budget.get("requests_reserved", MAX_REQUESTS + 1) > MAX_REQUESTS
            or budget.get("credits_reserved", MAX_CREDITS + 1) > MAX_CREDITS):
        raise ValueError("the separate 221-request or 221-credit ceiling was exceeded")
    if plan.get("budget", {}).get("planned_credits") != 198 or plan.get("budget", {}).get("retry_reserve") != 23:
        raise ValueError("the pinned plan no longer holds 23 credits beyond the 198 planned calls")

    entries = {row["file_id"]: row for row in base.manifest.get("additional_files", [])}
    required = {"sectors_recorded_sample", "sectors_selection_market", "sectors_ytd_baseline", "sectors_signal_analysis"}
    if missing := required - set(entries):
        raise ValueError(f"base release is missing required Sectors assets: {sorted(missing)}")
    original_sample_path = base.root / entries["sectors_recorded_sample"]["path"]
    original_sample_raw = original_sample_path.read_bytes()
    original_sample = _read(original_sample_path)
    market_path = base.root / entries["sectors_selection_market"]["path"]
    market_raw = market_path.read_bytes()
    market = _read(market_path)
    baseline_path = base.root / entries["sectors_ytd_baseline"]["path"]
    baseline_raw = baseline_path.read_bytes()
    baseline = _read(baseline_path)
    if _sha(original_sample_raw) != plan["base_release"]["sample_sha256"]:
        raise ValueError("the original 66-stock asset changed after preflight")
    if _sha(market_raw) != plan["market_release_source"]["sha256"]:
        raise ValueError("the pinned market source changed after preflight")
    if _sha(baseline_raw) != plan["base_release"]["ytd_baseline_sha256"]:
        raise ValueError("the existing YTD baseline changed after preflight")
    if original_sample.get("schema_version") != "sectors-recorded-sample-v1" or len(original_sample.get("stocks", [])) != 66:
        raise ValueError("the rollback source must remain the original 66-stock version")

    additions = acquisition.get("stocks", [])
    planned = {row["ticker"]: row["sector"] for row in plan["selection"]["additions"]}
    market_by_ticker = {str(row.get("ticker", "")).upper(): row for row in market.get("records", [])}
    by_ticker = {str(row.get("ticker", "")).upper(): row for row in additions}
    if set(by_ticker) != set(planned) or len(by_ticker) != 66:
        raise ValueError("acquired names do not exactly match the 66 hash-bound additions")
    for ticker, stock in by_ticker.items():
        expected_sector = planned[ticker]
        source_row = market_by_ticker.get(ticker)
        if (stock.get("sector") != expected_sector or source_row is None
                or (source_row.get("taxonomy") or {}).get("sector") != expected_sector):
            raise ValueError(f"added membership is inconsistent with the pinned ranking source: {ticker}")
        coverage = stock.get("history_coverage", {})
        expected_windows = plan["request_plan"][ticker]["price_windows"]
        if coverage.get("requested_start") != expected_windows[0][0] or coverage.get("requested_end") != expected_windows[-1][1]:
            raise ValueError(f"price coverage dates differ from the pinned windows: {ticker}")
        if len(coverage.get("price_windows", [])) != 2 or coverage.get("window_count") != 2:
            raise ValueError(f"two price windows are not documented for {ticker}")
        for source in coverage["price_windows"]:
            response_path = run_dir / "responses" / source["path"]
            if not response_path.is_file() or _sha(response_path.read_bytes()) != source.get("sha256"):
                raise ValueError(f"a price response hash does not match for {ticker}")
        action_source = (stock.get("corporate_actions") or {}).get("source", {})
        action_path = run_dir / "responses" / str(action_source.get("path", ""))
        if not action_path.is_file() or _sha(action_path.read_bytes()) != action_source.get("sha256"):
            raise ValueError(f"a corporate-action response hash does not match for {ticker}")

    destination = Path(out_dir).resolve()
    _copy_candidate(base.root, destination)
    manifest_path = destination / "manifest.json"
    manifest = _read(manifest_path)
    destination_sample_path = destination / entries["sectors_recorded_sample"]["path"]
    sample = json.loads(json.dumps(original_sample))
    original_by_ticker = {str(row["ticker"]).upper(): row for row in original_sample["stocks"]}
    member_order = [row["ticker"] for row in plan["selection"]["members"]]
    for ticker in member_order:
        if ticker in original_by_ticker:
            continue
        row = by_ticker.get(ticker)
        if row is None:
            raise ValueError(f"pinned 132-stock membership is missing {ticker}")
    combined_stocks = []
    market_cap_rank = {
        str(row["ticker"]).upper(): float(row["market_cap"])
        for row in market.get("records", []) if row.get("market_cap") is not None
    }
    for member in plan["selection"]["members"]:
        ticker = str(member["ticker"]).upper()
        stock = original_by_ticker.get(ticker) or by_ticker[ticker]
        combined_stocks.append(stock)
    sector_order = {sector: index for index, sector in enumerate(plan["selection"]["sectors"])}
    combined_stocks.sort(key=lambda row: (
        sector_order[str(row["sector"])],
        -market_cap_rank.get(str(row["ticker"]).upper(), 0.0),
        str(row["ticker"]).upper(),
    ))

    per_stock_coverage: dict[str, dict[str, Any]] = {}
    for stock in combined_stocks:
        ticker = str(stock["ticker"]).upper()
        prices = stock.get("prices", [])
        dates = sorted(str(row["date"]) for row in prices if row.get("date"))
        if ticker in by_ticker:
            per_stock_coverage[ticker] = dict(stock["history_coverage"])
        else:
            per_stock_coverage[ticker] = {
                "requested_start": original_sample["price_history"]["start"],
                "requested_end": original_sample["price_history"]["end"],
                "observed_start": dates[0] if dates else None,
                "observed_end": dates[-1] if dates else None,
                "window_count": len(stock.get("price_sources", [])),
                "price_windows": stock.get("price_sources", []),
            }
    original_tickers = sorted(original_by_ticker)
    old_flow_start = str(original_sample.get("foreign_flow", {}).get("stock_recent_start") or "")
    if not old_flow_start:
        raise ValueError("original company-flow start date is unavailable")
    sector_counts = {sector: 12 for sector in plan["selection"]["sectors"]}
    sample.update({
        "schema_version": "sectors-expanded-universe-v1",
        "label": "132 stocks across 11 IDX sectors",
        "scope": "Twelve eligible listed stocks per IDX sector, ranked by market capitalization on 2 October 2026. Price readings are equal-weighted; this is not the full market.",
        "selection": {
            **sample["selection"],
            "basis": plan["selection"]["basis"],
            "stocks_per_sector": 12,
            "stock_count": 132,
            "sector_counts": sector_counts,
            "expansion_plan_sha256": plan_hash,
            "ytd_tickers": original_tickers,
        },
        "coverage": {
            "price_history": {
                "stock_count": 132,
                "stocks_per_sector": 12,
                "first_replay_date": plan["coverage"]["first_replay_date"],
                "first_required_price_date": plan["coverage"]["first_required_price_date"],
                "end_date": plan["coverage"]["price_end_date"],
                "daily_dates": plan["coverage"]["daily_replay_dates"],
                "weekly_dates": plan["coverage"]["weekly_replay_dates"],
                "per_stock": per_stock_coverage,
            },
            "ytd": {
                "stock_count": 66,
                "tickers": original_tickers,
                "baseline_date": baseline.get("baseline_date"),
                "end_date": original_sample["as_of"],
                "baseline_asset_sha256": _sha(baseline_raw),
            },
            "company_flow": {
                "stock_count": 66,
                "tickers": original_tickers,
                "start_date": old_flow_start,
                "end_date": original_sample["as_of"],
            },
        },
        "stocks": combined_stocks,
    })
    sample["price_history"]["start"] = min(
        str(sample["price_history"]["start"]), plan["coverage"]["first_required_price_date"]
    )
    sample["foreign_flow"]["company_flow_coverage"] = sample["coverage"]["company_flow"]
    previous_validation = dict(sample.get("validation", {}))
    previous_validation.pop("six_per_sector", None)
    sample["validation"] = {
        **previous_validation,
        "status": "PASS",
        "stock_count": 132,
        "sector_count": 11,
        "twelve_per_sector": True,
        "unique_tickers": len({row["ticker"] for row in combined_stocks}) == 132,
        "market_cap_ranking_unchanged": True,
        "all_replay_dates_covered_by_requested_windows": True,
        "price_window_count_per_added_stock": 2,
        "corporate_action_checks_for_additions": 66,
        "historical_ytd_stock_count": 66,
        "company_flow_stock_count": 66,
        "hard_credit_ceiling": MAX_CREDITS,
        "credits_reserved": budget["credits_reserved"],
        "requests_reserved": budget["requests_reserved"],
    }
    old_sources = sample.get("sources", {})
    merged_responses = dict(old_sources.get("raw_responses", {}))
    merged_responses.update(acquisition.get("sources", {}).get("raw_response_hashes", {}))
    sample["sources"] = {
        **old_sources,
        "expansion_plan_sha256": plan_hash,
        "expansion_acquisition_sha256": _sha(acquisition_raw),
        "raw_responses": dict(sorted(merged_responses.items())),
        "expansion_request_ledger_sha256": acquisition.get("sources", {}).get("request_ledger_sha256"),
    }
    sample["limitations"] = [
        "Coverage includes 12 listed stocks in each sector, not every company on the exchange.",
        "Market-cap rankings are fixed to 2 October 2026 and applied retrospectively.",
        "Raw closes are not adjusted for corporate actions; affected return windows are excluded.",
        "YTD readings and company-level Sectors flow cover the original 66 stocks through 2 October 2026.",
        "Price history for the 66 added stocks begins on the date shown for each stock; earlier readings are unavailable.",
    ]
    sample_raw = canonical_json_bytes(sample) + b"\n"
    _write_atomic(destination_sample_path, sample_raw)

    with tempfile.TemporaryDirectory(prefix="sectors-expansion-analysis-") as temporary:
        analysis_work_path = Path(temporary) / "sectors_signal_analysis.json"
        analysis_result = build(
            sample_path=destination_sample_path,
            selection_market_path=destination / entries["sectors_selection_market"]["path"],
            selection_plan_path=plan_path,
            ytd_baseline_path=destination / entries["sectors_ytd_baseline"]["path"],
            out=analysis_work_path,
        )
        analysis_raw = analysis_work_path.read_bytes()

    analysis_entry = entries["sectors_signal_analysis"]
    _write_atomic(destination / analysis_entry["path"], analysis_raw)
    updated_entries = []
    for row in manifest["additional_files"]:
        if row["file_id"] == "sectors_recorded_sample":
            updated_entries.append(_entry(row["file_id"], row["path"], sample_raw,
                                          "sectors-expanded-universe-v1", sample["as_of"]))
        elif row["file_id"] == "sectors_signal_analysis":
            updated_entries.append(_entry(row["file_id"], row["path"], analysis_raw,
                                          SCHEMA, sample["as_of"]))
        else:
            updated_entries.append(row)
    manifest["additional_files"] = sorted(updated_entries, key=lambda row: row["file_id"])

    analysis_contract = {
        "schema": SCHEMA,
        "horizons_sessions": HORIZONS,
        "minimum_contributors": MINIMUM_CONTRIBUTORS,
        "stock_count": 132,
        "stocks_per_sector": 12,
        "price_basis": "raw Sectors daily close",
        "benchmark": "native Sectors IHSG close",
        "comparison": "paired-date intersection of valid members from the fixed 132-name set",
        "ytd_stock_count": 66,
        "company_flow_stock_count": 66,
        "actions": sorted({"split", "rights_issue", "bonus", "dividend", "other mechanical price changes"}),
    }
    manifest["analytical_contracts"]["sectors_signal_analysis"] = _sha(canonical_json_bytes(analysis_contract))
    manifest["analytical_contracts"]["sectors_expanded_universe"] = _sha(canonical_json_bytes({
        "schema": "sectors-expanded-universe-v1",
        "stock_count": 132,
        "stocks_per_sector": 12,
        "history_coverage_dates": "per stock, requested and observed start and end dates",
        "ytd_stock_count": 66,
        "company_flow_stock_count": 66,
        "hard_credit_ceiling": 221,
    }))
    manifest["validation"]["contract_fingerprints"] = manifest["analytical_contracts"]
    manifest["validation"]["input_hashes"]["additional_files"] = {
        row["file_id"]: row["sha256"] for row in manifest["additional_files"]
    }
    manifest["validation"]["analytical_status"] = "SECTORS_EXPANDED_ANALYSIS_PASS"
    manifest["release_id"] = ""
    manifest["release_id"] = calculate_release_id(manifest)
    _write_atomic(destination / "manifest.json", canonical_json_bytes(manifest) + b"\n")
    _bind_candidate_sources(manifest, destination)
    _write_atomic(destination / "manifest.json", canonical_json_bytes(manifest) + b"\n")
    verified = validate_manifest_file(destination / "manifest.json", candidate=True)
    return {
        "status": "PASS",
        "parent_release_id": base.release_id,
        "release_id": verified.release_id,
        "manifest_sha256": verified.manifest_sha256,
        "expanded_universe_sha256": _sha(sample_raw),
        "analysis_sha256": _sha(analysis_raw),
        "analysis_summary": analysis_result,
        "credits_reserved": budget["credits_reserved"],
        "credit_ceiling": MAX_CREDITS,
        "ytd_coverage": {"stock_count": 66, "baseline_date": baseline.get("baseline_date"), "end_date": sample["as_of"]},
        "company_flow_coverage": {"stock_count": 66, "start_date": old_flow_start, "end_date": sample["as_of"]},
        "candidate_manifest": str(destination / "manifest.json"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-manifest", required=True, type=Path)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(extend(base_manifest_path=args.base_manifest, run_dir=args.run_dir,
                                out_dir=args.out_dir), sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"SECTORS_EXPANSION_RELEASE_REFUSED: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
