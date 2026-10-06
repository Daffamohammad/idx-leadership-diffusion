"""Attach the matched-cohort submission analysis to a staged release candidate."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from idx_leadership.data.releases import calculate_release_id, canonical_json_bytes, validate_manifest_file
from idx_leadership.providers.idx_stock_summary import read_stock_summary_frequencies, sha256
from scripts.build_submission_analysis import build as build_analysis
from scripts.build_market_breadth import build as build_breadth


def extend(*, manifest_path: Path, prices: Path, benchmark: Path, stock_summary: Path) -> dict:
    manifest_path = manifest_path.resolve(strict=True)
    root = manifest_path.parent
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != "idx-release-manifest-v1" or manifest.get("target_session") != "2026-10-02":
        raise ValueError("only the October 2 staged release can be extended")
    existing_analysis = next((row for row in manifest.get("additional_files", []) if row.get("file_id") == "historical_comparison"), None)
    if existing_analysis and existing_analysis.get("schema") not in {"historical-comparison-v1", "historical-comparison-v2"}:
        raise ValueError("candidate contains an unsupported historical-comparison schema")
    market_entry = manifest["families"]["market"]
    foreign_entry = manifest["families"]["foreign"]
    rotation_entry = manifest["families"]["rotation"]
    snapshot_entry = manifest["families"]["snapshot"]
    market_path = root / market_entry["path"]
    foreign_path = root / foreign_entry["path"]
    rotation_path = root / rotation_entry["path"]
    snapshot_path = root / snapshot_entry["path"]
    market = json.loads(market_path.read_text(encoding="utf-8"))
    summary_hash = (market.get("sources", {}).get("stock_summary") or {}).get("sha256")
    stock_summary = stock_summary.resolve(strict=True)
    if not summary_hash or sha256(stock_summary) != summary_hash:
        raise ValueError("official Stock Summary differs from the selected market release")
    frequencies = read_stock_summary_frequencies(stock_summary, as_of=market["as_of"])
    for row in market["records"]:
        row["frequency_trades"] = frequencies.get(row["ticker"])
    market["units"] = {"price": "IDR per share", "value": "IDR", "volume": "shares", "frequency": "trades", "foreign_net": "shares"}
    market_path.write_text(json.dumps(market, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n", encoding="utf-8")
    market_raw = market_path.read_bytes()
    market_entry["sha256"] = hashlib.sha256(market_raw).hexdigest()
    market_entry["bytes"] = len(market_raw)
    manifest["validation"]["input_hashes"]["families"]["market"] = market_entry["sha256"]
    analysis_path = root / "assets" / "context" / "historical_comparison.json"
    result = build_analysis(market_path=market_path, rotation_path=rotation_path, snapshot_path=snapshot_path,
                            prices_path=prices.resolve(strict=True), benchmark_path=benchmark.resolve(strict=True),
                            out=analysis_path)
    raw = analysis_path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    entry = {
        "file_id": "historical_comparison", "family": "snapshot",
        "path": "assets/context/historical_comparison.json", "sha256": digest,
        "bytes": len(raw), "schema": "historical-comparison-v2", "observation_date": result["as_of"],
    }
    if existing_analysis:
        manifest["additional_files"].remove(existing_analysis)
    manifest["additional_files"].append(entry)
    breadth_path = root / "assets" / "context" / "market_breadth.json"
    breadth_result = build_breadth(market_path=market_path, foreign_path=foreign_path,
                                   stock_summary_path=stock_summary,
                                   prices_path=prices.resolve(strict=True), benchmark_path=benchmark.resolve(strict=True),
                                   statistics_pdf_dir=root / "evidence",
                                   out=breadth_path)
    breadth_raw = breadth_path.read_bytes()
    breadth_digest = hashlib.sha256(breadth_raw).hexdigest()
    old_breadth = next((row for row in manifest.get("additional_files", []) if row.get("file_id") == "market_breadth"), None)
    if old_breadth:
        manifest["additional_files"].remove(old_breadth)
    manifest["additional_files"].append({
        "file_id": "market_breadth", "family": "snapshot",
        "path": "assets/context/market_breadth.json", "sha256": breadth_digest,
        "bytes": len(breadth_raw), "schema": "market-breadth-v1", "observation_date": breadth_result["as_of"],
    })
    manifest["additional_files"].sort(key=lambda row: row["file_id"])
    validation = manifest["validation"]
    validation["analytical_status"] = "OFFLINE_SUBMISSION_ANALYSIS_PASS"
    validation["input_hashes"]["additional_files"] = {
        row["file_id"]: row["sha256"] for row in manifest["additional_files"]
    }
    manifest["release_id"] = ""
    manifest["release_id"] = calculate_release_id(manifest)
    manifest_path.write_bytes(canonical_json_bytes(manifest) + b"\n")
    verified = validate_manifest_file(manifest_path, candidate=True)
    return {
        "status": "PASS", "release_id": verified.release_id,
        "manifest_sha256": verified.manifest_sha256,
        "historical_comparison_sha256": digest,
        "cohort_count": result["cohort"]["count"],
        "sector_count": len(result["weekly"][-1]["groups"]),
        "taxonomy_counts": {key: value["group_count"] for key, value in result["taxonomies"].items()},
        "comparison_dates": result["comparison_dates"],
        "basket_sessions": len(result["sector_baskets"]["series"]),
        "market_breadth_sha256": breadth_digest,
        "historical_price_cohort_count": breadth_result["historical_price_breadth"]["cohort_count"],
        "official_breadth": breadth_result["official_daily"]["breadth"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-manifest", required=True, type=Path)
    parser.add_argument("--prices", required=True, type=Path)
    parser.add_argument("--benchmark", required=True, type=Path)
    parser.add_argument("--stock-summary", required=True, type=Path)
    args = parser.parse_args()
    try:
        report = extend(manifest_path=args.candidate_manifest, prices=args.prices,
                        benchmark=args.benchmark, stock_summary=args.stock_summary)
        print(json.dumps(report, sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"SUBMISSION_RELEASE_REFUSED: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
