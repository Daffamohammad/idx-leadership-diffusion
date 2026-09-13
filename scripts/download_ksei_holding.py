"""Download and parse KSEI holding-composition (local-foreign) data.

KSEI publishes monthly per-security foreign-ownership files at:
    https://web.ksei.co.id/archive_download/holding_composition

Each download is a ZIP containing a pipe-delimited ``.txt`` file with
columns: Date, Code, Type, Sec. Num, Price, Local IS/CP/PF/IB/ID/MF/SC/FD/OT/Total,
Foreign IS/CP/PF/IB/ID/MF/SC/FD/OT/Total.

This script downloads one effective date, parses it, and writes a
structured JSON envelope with provenance and summary statistics.

Usage:
    .venv/bin/python scripts/download_ksei_holding.py --year 2026 --month 8 --day 31
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import zipfile
from datetime import date
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "derived" / "ksei"

KSEI_BASE = "https://web.ksei.co.id"
COMPOSITION_PATH = "/Download/BalanceposEfek{ymd}.zip"
USER_AGENT = "Mozilla/5.0 (compatible; idx-leadership-diffusion/1.0)"

COLUMNS = [
    "Date", "Code", "Type", "Sec. Num", "Price",
    "Local IS", "Local CP", "Local PF", "Local IB", "Local ID",
    "Local MF", "Local SC", "Local FD", "Local OT", "Total",
    "Foreign IS", "Foreign CP", "Foreign PF", "Foreign IB", "Foreign ID",
    "Foreign MF", "Foreign SC", "Foreign FD", "Foreign OT", "Total",
]

LOCAL_COLS = [c for c in COLUMNS if c.startswith("Local")]
FOREIGN_COLS = [c for c in COLUMNS if c.startswith("Foreign")]


def download_zip(year: int, month: int, day: int) -> bytes:
    """Download the KSEI holding-composition ZIP for the given effective date."""
    ymd = f"{year:04d}{month:02d}{day:02d}"
    url = KSEI_BASE + COMPOSITION_PATH.format(ymd=ymd)
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=60) as resp:
        return resp.read()


def parse_zip(raw: bytes) -> tuple[list[dict[str, str]], str]:
    """Extract and parse the pipe-delimited TXT from the ZIP."""
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        names = zf.namelist()
        if not names:
            raise ValueError("KSEI ZIP is empty")
        txt = zf.read(names[0]).decode("latin-1")
    lines = txt.strip().split("\n")
    header = lines[0].split("|")
    if header != COLUMNS:
        raise ValueError(f"KSEI schema drift: expected {len(COLUMNS)} cols, got {header}")
    rows: list[dict[str, str]] = []
    for line in lines[1:]:
        parts = line.split("|")
        if len(parts) != len(header):
            continue
        rows.append(dict(zip(header, parts)))
    return rows, lines[0].split("|")[0]


def build_payload(rows: list[dict[str, str]], effective_date: str) -> dict[str, Any]:
    """Convert raw rows to a structured JSON envelope."""
    import pandas as pd

    df = pd.DataFrame(rows)
    for col in LOCAL_COLS + FOREIGN_COLS:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    df["local_total"] = df[LOCAL_COLS].sum(axis=1)
    df["foreign_total"] = df[FOREIGN_COLS].sum(axis=1)
    df["total"] = df["local_total"] + df["foreign_total"]
    df["foreign_pct"] = (df["foreign_total"] / df["total"].replace(0, float("nan")) * 100).round(2)

    records = []
    for _, r in df.iterrows():
        records.append({
            "ticker": str(r["Code"]).strip(),
            "effective_date": effective_date,
            "instrument_type": str(r.get("Type", "")).strip(),
            "shares_outstanding": int(pd.to_numeric(r.get("Sec. Num"), errors="coerce") or 0),
            "price": float(pd.to_numeric(r.get("Price"), errors="coerce") or 0),
            "foreign_pct": None if pd.isna(r["foreign_pct"]) else float(r["foreign_pct"]),
            "foreign_total": float(r["foreign_total"]),
            "local_total": float(r["local_total"]),
            "total": float(r["total"]),
            "foreign_by_category": {
                "IS": float(r["Foreign IS"]),
                "CP": float(r["Foreign CP"]),
                "PF": float(r["Foreign PF"]),
                "IB": float(r["Foreign IB"]),
                "ID": float(r["Foreign ID"]),
                "MF": float(r["Foreign MF"]),
                "SC": float(r["Foreign SC"]),
                "FD": float(r["Foreign FD"]),
                "OT": float(r["Foreign OT"]),
            },
        })

    foreign_pcts = [r["foreign_pct"] for r in records if r["foreign_pct"] is not None]
    return {
        "source": "KSEI (Kustodian Sentral Efek Indonesia)",
        "source_url": "https://web.ksei.co.id/archive_download/holding_composition",
        "retrieved_at": date.today().isoformat(),
        "effective_date": effective_date,
        "schema": "ksei-holding-composition-v1",
        "parser_version": "ksei-parser-v1",
        "row_count": len(records),
        "ticker_count": len({r["ticker"] for r in records}),
        "foreign_ownership_summary": {
            "mean_pct": round(sum(foreign_pcts) / len(foreign_pcts), 2) if foreign_pcts else None,
            "median_pct": round(sorted(foreign_pcts)[len(foreign_pcts) // 2], 2) if foreign_pcts else None,
            "max_pct": round(max(foreign_pcts), 2) if foreign_pcts else None,
            "count_gt_50pct": sum(1 for p in foreign_pcts if p > 50),
            "count_gt_25pct": sum(1 for p in foreign_pcts if p > 25),
            "count_gt_10pct": sum(1 for p in foreign_pcts if p > 10),
        },
        "records": records,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Download KSEI holding composition")
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--month", type=int, required=True)
    ap.add_argument("--day", type=int, required=True)
    ap.add_argument("--out-dir", type=Path, default=OUT_DIR)
    args = ap.parse_args()

    effective = f"{args.year:04d}-{args.month:02d}-{args.day:02d}"
    print(f"Downloading KSEI holding composition for {effective}...")
    raw = download_zip(args.year, args.month, args.day)
    print(f"  Downloaded {len(raw)} bytes")

    rows, date_label = parse_zip(raw)
    print(f"  Parsed {len(rows)} rows, date label={date_label}")

    payload = build_payload(rows, effective)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    out_path = args.out_dir / f"ksei_holding_{effective.replace('-', '')}.json"
    tmp = out_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, default=str, indent=2), encoding="utf-8")
    tmp.replace(out_path)
    print(f"  Wrote {out_path} ({out_path.stat().st_size / 1024:.1f} KB)")
    print(f"  Tickers: {payload['ticker_count']}, mean foreign pct: {payload['foreign_ownership_summary']['mean_pct']}%")


if __name__ == "__main__":
    main()