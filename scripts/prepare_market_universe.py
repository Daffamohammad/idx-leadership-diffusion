"""Prepare the full public universe from an official, locally cached close file."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import yaml

from idx_leadership.providers.idx_stock_summary import normalize_stock_summary, read_stock_summary, sha256


def structural_versions(records: list[dict]) -> tuple[str, str]:
    """Fingerprint listing eligibility and classification facts, without dates or quotes."""
    universe_facts = []
    classification_facts = []
    for row in records:
        ticker = str(row.get("ticker") or "").upper()
        instrument_type = row.get("instrument_type")
        if not ticker:
            raise ValueError("structural version input contains a missing ticker")
        universe_facts.append({
            "ticker": ticker,
            "instrument_type": instrument_type,
            "analysis_requested": bool(row.get("analysis_requested")),
            "listing_board": row.get("listing_board"),
        })
        if row.get("analysis_requested"):
            taxonomy = row.get("taxonomy") or {}
            classification_facts.append({
                "ticker": ticker,
                "sector": taxonomy.get("sector"),
                "subsector": taxonomy.get("subsector"),
                "industry": taxonomy.get("industry"),
                "subindustry": taxonomy.get("subindustry"),
            })
    canonical = lambda value: json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    universe_hash = hashlib.sha256(canonical({"policy": "idx-analysis-eligibility-v1", "records": sorted(universe_facts, key=lambda row: row["ticker"])}).encode()).hexdigest()[:16]
    taxonomy_hash = hashlib.sha256(canonical({"policy": "captured-idxic-v1", "records": sorted(classification_facts, key=lambda row: row["ticker"])}).encode()).hexdigest()[:16]
    return f"idx-universe-{universe_hash}-v1", f"captured-idxic-{taxonomy_hash}-v1"


def main() -> int:
    parser = argparse.ArgumentParser(prog="prepare_market_universe")
    parser.add_argument("--stock-summary", required=True)
    parser.add_argument("--classification-bundle", required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--universe-out", required=True)
    parser.add_argument("--daily-out", required=True)
    args = parser.parse_args()
    summary_path = Path(args.stock_summary)
    reference_path = Path(args.classification_bundle)
    try:
        reference = json.loads(reference_path.read_text())
        registry = reference["listing_registry"]
        if registry.get("full_accessible_universe_listed") is not True:
            raise ValueError("Classification reference is not a complete captured listing")
        daily = normalize_stock_summary(read_stock_summary(summary_path), as_of=args.as_of, classifications=registry["records"])
        provenance = {
            "stock_summary": {"file": summary_path.name, "sha256": sha256(summary_path), "as_of": args.as_of},
            "classification": {"snapshot_id": reference["snapshot_id"], "sha256": sha256(reference_path), "as_of": reference["as_of"], "source": "Previously captured registry; no live provider request"},
        }
        daily["sources"] = provenance
        universe_version, taxonomy_version = structural_versions(daily["records"])
        universe = {
            "benchmark": "^JKSE",
            "benchmark_name": "IHSG",
            "universe_version": universe_version,
            "taxonomy_version": taxonomy_version,
            "sources": provenance,
            "excluded_listings": [{"ticker": r["ticker"], "reason": r["instrument_type"]} for r in daily["records"] if not r["analysis_requested"]],
            "universe": [
                {"ticker": r["ticker"], "company_name": r["company_name"],
                 "sectors": r["taxonomy"].get("sector") or "Unclassified",
                 "sub_sectors": r["taxonomy"].get("subsector"),
                 "industry": r["taxonomy"].get("industry"),
                 "subindustry": r["taxonomy"].get("subindustry"),
                 "market_cap": r["market_cap"], "listing_board": r["listing_board"],
                 "source_as_of": args.as_of, "classification_as_of": r["classification_as_of"]}
                for r in daily["records"] if r["analysis_requested"]
            ],
        }
        # Validate all inputs before publishing either artifact.
        for path, content in (
            (Path(args.universe_out), yaml.safe_dump(universe, sort_keys=False)),
            (Path(args.daily_out), json.dumps(daily, indent=2, allow_nan=False)),
        ):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content.rstrip("\n") + "\n")
        print(json.dumps({k: daily[k] for k in ("as_of", "listed_count", "observed_price_count", "classification_count", "breadth")}))
        return 0
    except (OSError, ValueError, KeyError) as exc:
        print(f"SOURCE_UNAVAILABLE: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
