"""Validate the public price panel against official IDX sources.

Offline cross-checks (no network) of ``data/raw/public/panel_*``:

1. benchmark vs the official Composite Stock Price Index workbook
   (all overlapping sessions; expected match within 0.01 index points),
2. benchmark vs the IHSG close parsed from each cached IDX Daily
   Statistics PDF page 1 (Prev + change, cross-checked against the
   printed IHSG value),
3. stocks: raw ``close`` vs the official Stock Summary workbook for the
   snapshot date (universe intersection; per-ticker diffs reported),
4. coverage reconciliation: official codes vs sectors registry vs
   universe vs downloaded/usable/ytd-baseline counts (never merged),
5. panel integrity: ordering, duplicates, positivity, units, basis,
   and the explicit YTD baseline session (<= 2025-12-31).

Writes ``data/normalized/public_panel_validation.json`` and a trimmed
copy for tests at ``tests/fixtures/public_panel_validation.json``.

CLI::

    .venv/bin/python -m scripts.validate_public_panel            # system python w/ openpyxl+pdfplumber
    python3 -m scripts.validate_public_panel
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
import warnings
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

warnings.filterwarnings("ignore", message="Workbook contains no default style")

PROJECT_ROOT = Path(__file__).resolve().parents[1]

BENCHMARK_TOL = 0.01          # index points
STOCK_TOL_IDR = 1.0           # rupiah per share (Yahoo rounding)
STOCK_MATCH_RATE_MIN = 0.95
YTD_BASELINE = date(2025, 12, 30)

DS_RE = re.compile(r"ds_(\d{2})(\d{2})(\d{2})\.pdf$")
CHANGE_RE = re.compile(r"([+-]\d[\d,]*\.\d+)\s+\(\s*[+-]?\d[\d.]*%\)")
FLOAT_RE = re.compile(r"^[\d,]+\.\d+$")


def _latest_panel(panel_root: Path) -> Path:
    dirs = sorted(
        (d for d in panel_root.glob("panel_*") if (d / "prices.csv").is_file()),
        key=lambda d: d.name,
    )
    if not dirs:
        raise SystemExit(f"no panel_* directory with prices.csv under {panel_root}")
    return dirs[-1]


def _num(text: str) -> float:
    return float(text.replace(",", ""))


def _load_composite_workbook(path: Path) -> dict[date, float]:
    import openpyxl

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    ws.reset_dimensions()
    out: dict[date, float] = {}
    date_i = close_i = None
    for row in ws.iter_rows(values_only=True):
        if not row:
            continue
        if "Date" in row[:5] and "Close" in row[:10]:
            date_i = list(row[:5]).index("Date")
            close_i = list(row[:10]).index("Close")
            continue
        if date_i is None or close_i is None or not isinstance(row[1], int):
            continue
        raw_date, close = row[date_i], row[close_i]
        if not isinstance(raw_date, str) or close is None:
            continue
        mm, dd, yyyy = raw_date.split("/")
        out[date(int(yyyy), int(mm), int(dd))] = float(close)
    return out


def _load_stock_summary(path: Path) -> dict[str, float]:
    import openpyxl

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    rows = ws.iter_rows(values_only=True)
    header = list(next(rows))
    code_i = header.index("Stock Code")
    close_i = header.index("Close")
    date_i = header.index("Last Trading Date")
    out: dict[str, float] = {}
    trade_dates: set[str] = set()
    for row in rows:
        if not row or row[code_i] is None:
            continue
        out[str(row[code_i]).strip().upper()] = float(row[close_i])
        trade_dates.add(str(row[date_i]))
    out["_trade_dates"] = trade_dates  # type: ignore[assignment]
    return out  # type: ignore[return-value]


def _parse_ds_pdf(path: Path) -> tuple[date, float, float, float]:
    """Return (session, previous, change, printed_close) from page 1."""
    import pdfplumber

    with pdfplumber.open(path) as pdf:
        text = pdf.pages[0].extract_text() or ""
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    prev = None
    for i, line in enumerate(lines):
        if line.replace(" ", "") == "PreviousHighestLowest":
            candidates = [_num(x) for x in lines[i + 1].split() if FLOAT_RE.match(x)]
            if len(candidates) >= 3:
                prev = candidates[0]
            break

    change = None
    printed = None
    for i, line in enumerate(lines):
        if "IDX Composite Index (IHSG)" in line:
            for j in range(i + 1, min(i + 8, len(lines))):
                match = CHANGE_RE.search(lines[j])
                if match and change is None:
                    change = _num(match.group(1))
                if lines[j] == "(million shares)" and j + 1 < len(lines):
                    nxt = lines[j + 1].replace(",", "")
                    if FLOAT_RE.match(lines[j + 1]):
                        printed = _num(nxt)
            break

    match = DS_RE.search(path.name)
    if not match:
        raise ValueError(f"cannot parse session from {path.name}")
    yy, mm, dd = match.groups()
    session = date(2000 + int(yy), int(mm), int(dd))
    if prev is None or change is None:
        raise ValueError(f"cannot parse IHSG prev/change from {path.name}")
    return session, prev, change, printed if printed is not None else float("nan")


def _display_path(path: Path) -> str:
    """Repo-relative when possible, absolute otherwise (temp panels, etc.)."""
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def _check_panel_integrity(
    prices: "pd.DataFrame",
    benchmark: "pd.DataFrame",
    panel_manifest: dict[str, Any],
    panel_dir: Path,
) -> dict[str, Any]:
    """Structural, finiteness and provenance checks for the panel itself.

    Used twice: once as an early gate (so a corrupt panel never reaches the
    official comparisons) and once inside the full report.
    """
    import pandas as pd

    counts = panel_manifest.get("counts", {})
    dupes = int(prices.duplicated(subset=["ticker", "date"]).sum())
    price_matrix = prices[["close", "adjusted_close"]].to_numpy(dtype=float)
    nonfinite = int(sum(1 for value in price_matrix.ravel() if not math.isfinite(value)))
    nonpositive = int((prices[["close", "adjusted_close"]] <= 0).any(axis=1).sum())
    bench_values = benchmark["close"].to_numpy(dtype=float)
    bench_nonfinite = int(sum(1 for value in bench_values if not math.isfinite(value)))
    bench_nonpositive = int((benchmark["close"] <= 0).sum())

    # The panel must still be the artifact that was fetched: verify the file
    # hashes recorded in source_manifest.json before trusting any of its values.
    recorded_files = panel_manifest.get("files") or {}
    hash_mismatches = []
    missing_hash_records = []
    for name in ("prices.csv", "benchmark.csv"):
        recorded = (recorded_files.get(name) or {}).get("sha256")
        if not recorded:
            missing_hash_records.append(name)
            continue
        actual = hashlib.sha256((panel_dir / name).read_bytes()).hexdigest()
        if actual != recorded:
            hash_mismatches.append(
                {"file": name, "recorded_sha256": recorded, "actual_sha256": actual}
            )

    latest_session = max(prices["date"])
    baseline_rows = prices[prices["date"] == YTD_BASELINE]
    baseline_invalid = int(
        (
            ~baseline_rows["close"].map(math.isfinite)
            | ~baseline_rows["adjusted_close"].map(math.isfinite)
            | (baseline_rows["close"] <= 0)
            | (baseline_rows["adjusted_close"] <= 0)
        ).sum()
    )
    bench = dict(zip(benchmark["date"], benchmark["close"]))
    expected_latest = ((panel_manifest.get("sessions") or {}).get("latest_session")) or ""
    ok = (
        dupes == 0
        and nonpositive == 0
        and nonfinite == 0
        and bench_nonfinite == 0
        and bench_nonpositive == 0
        and baseline_invalid == 0
        and not hash_mismatches
        and not missing_hash_records
        and len(baseline_rows) == counts.get("ytd_baseline_present")
        and expected_latest == latest_session.isoformat()
    )
    return {
        "rows": int(len(prices)),
        "benchmark_rows": int(len(benchmark)),
        "duplicate_ticker_date_rows": dupes,
        "nonpositive_price_rows": nonpositive,
        "nonfinite_price_rows": nonfinite,
        "benchmark_nonfinite_rows": bench_nonfinite,
        "benchmark_nonpositive_rows": bench_nonpositive,
        "ytd_baseline_invalid_rows": baseline_invalid,
        "panel_file_hashes_verified": not hash_mismatches and not missing_hash_records,
        "panel_file_hash_mismatches": hash_mismatches,
        "panel_files_without_recorded_hash": missing_hash_records,
        "units": panel_manifest.get("units"),
        "price_basis": panel_manifest.get("price_basis"),
        "ytd_baseline_date": YTD_BASELINE.isoformat(),
        "ytd_baseline_tickers": int(len(baseline_rows)),
        "ytd_baseline_benchmark_close": bench.get(YTD_BASELINE),
        "latest_session": latest_session.isoformat(),
        "benchmark_latest_session": max(benchmark["date"]).isoformat(),
        "status": "PASS" if ok else "FAIL",
    }


def main() -> int:
    parser = argparse.ArgumentParser(prog="validate_public_panel")
    parser.add_argument("--panel-dir", default=None)
    parser.add_argument(
        "--out", default=str(PROJECT_ROOT / "data" / "normalized" / "public_panel_validation.json")
    )
    args = parser.parse_args()

    import pandas as pd

    panel_dir = Path(args.panel_dir) if args.panel_dir else _latest_panel(
        PROJECT_ROOT / "data" / "raw" / "public"
    )
    prices = pd.read_csv(panel_dir / "prices.csv", parse_dates=["date"])
    benchmark = pd.read_csv(panel_dir / "benchmark.csv", parse_dates=["date"])
    panel_manifest = json.loads((panel_dir / "source_manifest.json").read_text())
    prices["date"] = prices["date"].dt.date
    benchmark["date"] = benchmark["date"].dt.date

    checks: dict[str, Any] = {}

    # Integrity and provenance gate first: a panel that does not match the
    # hashes recorded at fetch time, or that carries a non-finite price, must
    # not be compared against official sources — every downstream number would
    # inherit the defect while still looking validated.
    integrity_early = _check_panel_integrity(prices, benchmark, panel_manifest, panel_dir)
    if integrity_early["status"] != "PASS":
        report = {
            "kind": "PUBLIC_PANEL_VALIDATION",
            "validated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "panel_dir": _display_path(panel_dir),
            "panel_window": panel_manifest.get("window"),
            "status": "FAIL",
            "checks": {"panel_integrity": integrity_early},
        }
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(
            "status=FAIL (panel integrity/provenance gate): "
            f"nonfinite={integrity_early['nonfinite_price_rows']} "
            f"hash_mismatches={len(integrity_early['panel_file_hash_mismatches'])} "
            f"baseline_invalid={integrity_early['ytd_baseline_invalid_rows']}",
            file=sys.stderr,
        )
        return 1

    # --- 1. benchmark vs official composite workbook ---------------------
    workbook_path = (
        PROJECT_ROOT
        / "data" / "raw" / "idx_composite_index"
        / "Composite Stock Price Index & Stock Trading Volume - Sep 2026.xlsx"
    )
    official = _load_composite_workbook(workbook_path)
    bench = dict(zip(benchmark["date"], benchmark["close"]))
    diffs = []
    for d, off_close in sorted(official.items()):
        if d in bench:
            diffs.append(
                {"date": d.isoformat(), "official": off_close, "panel": round(bench[d], 3),
                 "abs_diff": round(abs(off_close - bench[d]), 4)}
            )
    mismatches = [x for x in diffs if x["abs_diff"] > BENCHMARK_TOL]
    checks["benchmark_vs_official_workbook"] = {
        "source": workbook_path.name,
        "official_sessions": len(official),
        "official_range": [
            min(official).isoformat() if official else None,
            max(official).isoformat() if official else None,
        ],
        "dates_matched": len(diffs),
        "tolerance_index_points": BENCHMARK_TOL,
        "max_abs_diff": max((x["abs_diff"] for x in diffs), default=None),
        "mismatches": mismatches,
        "representative": {
            "ytd_baseline_2025-12-30": next(
                (x for x in diffs if x["date"] == "2025-12-30"), None
            ),
            "last_official_2026-08-31": next(
                (x for x in diffs if x["date"] == "2026-08-31"), None
            ),
        },
        "status": "PASS" if diffs and not mismatches else "FAIL",
    }

    # --- 2. benchmark vs IDX daily statistics PDFs ------------------------
    pdf_rows = []
    pdf_errors = []
    ds_dir = PROJECT_ROOT / "data" / "raw" / "idx_daily_statistics"
    for pdf_path in sorted(ds_dir.glob("ds_*.pdf")):
        try:
            session, prev, change, printed = _parse_ds_pdf(pdf_path)
        except ValueError as exc:
            pdf_errors.append({"file": pdf_path.name, "error": str(exc)})
            continue
        computed_close = round(prev + change, 3)
        panel_close = bench.get(session)
        row = {
            "session": session.isoformat(),
            "official_prev": prev,
            "official_change": change,
            "official_close_computed": computed_close,
            "official_close_printed": printed,
            "panel_close": round(panel_close, 3) if panel_close is not None else None,
        }
        if panel_close is not None:
            row["abs_diff"] = round(abs(computed_close - panel_close), 4)
        if printed == printed:  # not NaN
            row["computed_vs_printed"] = round(abs(computed_close - printed), 4)
        pdf_rows.append(row)
    pdf_bad = [
        r for r in pdf_rows
        if r.get("abs_diff") is None or r["abs_diff"] > BENCHMARK_TOL
        or r.get("computed_vs_printed", 0) > 0.001
    ]
    checks["benchmark_vs_daily_statistics_pdfs"] = {
        "source": f"{ds_dir.name}/ds_*.pdf",
        "dates_checked": len(pdf_rows),
        "tolerance_index_points": BENCHMARK_TOL,
        "rows": pdf_rows,
        "parse_errors": pdf_errors,
        "status": "PASS" if pdf_rows and not pdf_bad and not pdf_errors else "FAIL",
    }

    # --- 3. stocks vs official stock summary ------------------------------
    summary_path = PROJECT_ROOT / "data" / "raw" / "idx_stock_summary" / "Stock Summary-20261002.xlsx"
    summary = _load_stock_summary(summary_path)
    trade_dates = summary.pop("_trade_dates")  # type: ignore[misc]
    official_date = None
    for raw in trade_dates:
        official_date = datetime.strptime(raw, "%d %b %Y").date()
        break

    latest_session = max(prices["date"])
    panel_close_latest = {
        str(t).upper(): float(c)
        for t, c in zip(
            prices.loc[prices["date"] == latest_session, "ticker"],
            prices.loc[prices["date"] == latest_session, "close"],
        )
    }
    stock_rows = []
    for ticker, panel_close in sorted(panel_close_latest.items()):
        code = ticker[:-3] if ticker.endswith(".JK") else ticker
        official_close = summary.get(code)
        if official_close is None:
            stock_rows.append({"ticker": ticker, "official": None, "status": "NOT_IN_OFFICIAL"})
            continue
        diff = abs(official_close - panel_close)
        stock_rows.append(
            {
                "ticker": ticker,
                "official": official_close,
                "panel_raw_close": round(panel_close, 2),
                "abs_diff_idr": round(diff, 4),
                "status": "MATCH" if diff <= STOCK_TOL_IDR else "MISMATCH",
            }
        )
    matched = [r for r in stock_rows if r.get("status") == "MATCH"]
    mismatched = [r for r in stock_rows if r.get("status") == "MISMATCH"]
    absent = [r for r in stock_rows if r.get("status") == "NOT_IN_OFFICIAL"]
    match_rate = (len(matched) / len(stock_rows)) if stock_rows else 0.0
    date_aligned = official_date is not None and official_date == latest_session
    checks["stocks_vs_official_stock_summary"] = {
        "source": summary_path.name,
        "official_date": official_date.isoformat() if official_date else None,
        "official_date_matches_panel": date_aligned,
        "panel_latest_session": latest_session.isoformat(),
        "universe_intersection": len(stock_rows),
        "official_codes": len(summary),
        "matched": len(matched),
        "mismatched": mismatched,
        "not_in_official": [r["ticker"] for r in absent],
        "match_rate": round(match_rate, 4),
        "tolerance_idr": STOCK_TOL_IDR,
        "max_abs_diff_idr": max((r["abs_diff_idr"] for r in matched), default=None),
        "representative": {
            t: next((r for r in matched if r["ticker"] == t), None)
            for t in ("BBCA.JK", "BBRI.JK", "AMMN.JK")
            if any(r["ticker"] == t for r in matched)
        },
        "status": "PASS"
        if match_rate >= STOCK_MATCH_RATE_MIN and not mismatched and date_aligned
        else "FAIL",
    }

    # --- 4. coverage reconciliation (distinct counts, never merged) -------
    sectors_registry = None
    sectors_registry_source = None
    validation_root = PROJECT_ROOT / "data" / "raw" / "sectors_validation"
    if validation_root.is_dir():
        reports = sorted(
            validation_root.glob("*/validation_report.json"), reverse=True
        )
        for report_path in reports:
            try:
                report = json.loads(report_path.read_text())
            except (OSError, json.JSONDecodeError):
                continue
            if report.get("status") not in {"PASS", "REVIEW_REQUIRED"}:
                continue
            taxonomy = (report.get("checks", {}) or {}).get("taxonomy", {}) or {}
            rows = taxonomy.get("structured_query_complete_rows") or taxonomy.get("rows")
            if isinstance(rows, int) and rows >= 900:
                sectors_registry = rows
                sectors_registry_source = str(
                    report_path.relative_to(PROJECT_ROOT)
                )
                break
    counts = panel_manifest.get("counts", {})
    checks["coverage_reconciliation"] = {
        "official_stock_summary_codes": len(summary),
        "sectors_snapshot_registry_codes": sectors_registry,
        "sectors_registry_source": sectors_registry_source,
        "universe_requested": counts.get("requested"),
        "downloaded": counts.get("downloaded"),
        "failed_symbols": panel_manifest.get("diagnostics", {}).get("failed_symbols"),
        "usable_ge_60_sessions": counts.get("usable_ge_60_sessions"),
        "ytd_baseline_present": counts.get("ytd_baseline_present"),
        "note": (
            "official registry (all listed codes), sectors snapshot registry, "
            "and prototype universe are three distinct populations; no count "
            "is forced to match another"
        ),
        "status": "PASS",
    }

    # --- 5. panel integrity ------------------------------------------------
    # Shared with the early gate: finiteness, positivity and panel-file
    # provenance are checked before any official comparison runs.
    checks["panel_integrity"] = _check_panel_integrity(
        prices, benchmark, panel_manifest, panel_dir
    )

    # --- 6. corporate actions disclosure -----------------------------------
    checks["corporate_actions"] = {
        **panel_manifest.get("corporate_actions", {}),
        "status": "DISCLOSURE",
    }

    status = (
        "PASS"
        if all(
            checks[k]["status"] in {"PASS", "DISCLOSURE"}
            for k in (
                "benchmark_vs_official_workbook",
                "benchmark_vs_daily_statistics_pdfs",
                "stocks_vs_official_stock_summary",
                "coverage_reconciliation",
                "panel_integrity",
            )
        )
        else "FAIL"
    )
    report = {
        "kind": "PUBLIC_PANEL_VALIDATION",
        "validated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "panel_dir": _display_path(panel_dir),
        "panel_window": panel_manifest.get("window"),
        "status": status,
        "checks": checks,
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    fixture_path = PROJECT_ROOT / "tests" / "fixtures" / "public_panel_validation.json"
    fixture_path.parent.mkdir(parents=True, exist_ok=True)
    # The report carries no bulk series (mismatch lists and 11 PDF rows only),
    # so the trimmed copy keeps every check for assertions while dropping the
    # timestamp so a re-run does not churn the tracked file.
    trimmed = {
        "kind": report["kind"],
        "panel_window": report["panel_window"],
        "status": status,
        "checks": checks,
    }
    fixture_path.write_text(json.dumps(trimmed, indent=2), encoding="utf-8")

    print(f"status={status} -> {out_path}", file=sys.stderr)
    for name, check in checks.items():
        print(f"  {name}: {check['status']}", file=sys.stderr)
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
