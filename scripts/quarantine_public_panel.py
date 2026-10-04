"""Derive a replay panel excluding explicitly failed official comparisons.

The fetched panel and its FAIL report remain immutable. The derived panel
must be independently validated before export; this command never claims PASS.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd

from scripts.validate_public_panel import _check_panel_integrity


def derive_panel(panel_dir: Path, report_path: Path, out_dir: Path) -> dict[str, Any]:
    if out_dir.exists():
        raise ValueError("Derived output already exists; preserve immutable source artifacts")
    manifest = json.loads((panel_dir / "source_manifest.json").read_text())
    report = json.loads(report_path.read_text())
    prices = pd.read_csv(panel_dir / "prices.csv", parse_dates=["date"])
    benchmark = pd.read_csv(panel_dir / "benchmark.csv", parse_dates=["date"])
    for frame in (prices, benchmark):
        frame["date"] = frame["date"].dt.date
    integrity = _check_panel_integrity(prices, benchmark, manifest, panel_dir)
    if integrity["status"] != "PASS":
        raise ValueError("Source panel failed integrity; it cannot be repaired by dropping securities")
    checks = report["checks"]
    if any(checks[name]["status"] != "PASS" for name in ("panel_integrity", "benchmark_vs_official_workbook", "benchmark_vs_daily_statistics_pdfs")):
        raise ValueError("Only per-security official close conflicts may be quarantined")
    comparison = checks["stocks_vs_official_stock_summary"]
    bad = comparison.get("mismatched", [])
    if not bad or comparison.get("not_in_official") or not comparison.get("official_date_matches_panel"):
        raise ValueError("Report has no isolated, date-aligned official price conflicts")
    if report["panel_window"] != manifest["window"]:
        raise ValueError("Validation report window does not match the source panel")
    latest = prices[prices["date"] == max(prices["date"])].set_index("ticker")
    for row in bad:
        ticker = row["ticker"]
        if row.get("status") != "MISMATCH" or ticker not in latest.index:
            raise ValueError("Invalid quarantine record")
        if abs(float(latest.loc[ticker, "close"]) - float(row["panel_raw_close"])) > 0.011:
            raise ValueError("Quarantine report is stale for the source quote")
    tickers = sorted({row["ticker"] for row in bad})
    retained = prices[~prices["ticker"].isin(tickers)].copy()
    if retained.empty:
        raise ValueError("Quarantine would remove the entire panel")
    original_counts = dict(manifest["counts"])
    out_dir.mkdir(parents=True)
    retained.to_csv(out_dir / "prices.csv", index=False)
    (out_dir / "benchmark.csv").write_bytes((panel_dir / "benchmark.csv").read_bytes())
    provenance = {
        "source_manifest_sha256": hashlib.sha256((panel_dir / "source_manifest.json").read_bytes()).hexdigest(),
        "source_files": copy.deepcopy(manifest["files"]),
        "validation_report_sha256": hashlib.sha256(report_path.read_bytes()).hexdigest(),
        "acquisition_counts": original_counts,
        "quarantined": bad,
        "note": "No price substituted; whole conflicting histories excluded. Revalidate this derived panel independently.",
    }
    manifest["kind"] = "DERIVED_QUARANTINED_PUBLIC_PRICE_PANEL"
    manifest["reconciliation"] = provenance
    groups = retained.groupby("ticker")["date"].agg(["min", "max", "count"])
    baseline = manifest["sessions"]["ytd_baseline_date"]
    manifest["counts"].update({
        "downloaded": len(groups),
        "quarantined": len(tickers),
        "usable_ge_60_sessions": int((groups["count"] >= 60).sum()),
        "ytd_baseline_present": int((retained["date"].astype(str) == baseline).sum()),
        "rows": len(retained),
    })
    manifest["sessions"]["per_ticker"] = {
        t: {"first": r["min"].isoformat(), "last": r["max"].isoformat(), "sessions": int(r["count"])}
        for t, r in groups.iterrows()
    }
    manifest["diagnostics"]["quarantined_symbols"] = tickers
    for name in ("prices.csv", "benchmark.csv"):
        manifest["files"][name] = {
            "sha256": hashlib.sha256((out_dir / name).read_bytes()).hexdigest(),
            "rows": len(retained) if name == "prices.csv" else len(benchmark),
        }
    (out_dir / "source_manifest.json").write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n")
    return provenance


def main() -> int:
    parser = argparse.ArgumentParser(prog="quarantine_public_panel")
    parser.add_argument("--panel-dir", required=True)
    parser.add_argument("--validation-report", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()
    try:
        result = derive_panel(Path(args.panel_dir), Path(args.validation_report), Path(args.out_dir))
        print(json.dumps(result, indent=2))
        return 0
    except (OSError, ValueError, KeyError) as exc:
        print(f"Cannot derive panel: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
