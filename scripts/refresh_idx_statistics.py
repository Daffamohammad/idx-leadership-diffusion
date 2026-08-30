"""Fetch and validate an official IDX monthly investor-statistics release.

The command is intentionally separate from the Sectors refresh. It uses the
public IDX page as its numeric source, keeps search agents in a discovery-only
role, and writes nothing until both official tables and their totals reconcile.

Examples::

    .venv/bin/python -m scripts.refresh_idx_statistics --year 2026 --month 7
    .venv/bin/python -m scripts.refresh_idx_statistics \
        --year 2026 --month 7 --html-file /path/to/rendered-page.html \
        --output data/derived/idx_investor_trading_2026-07.json
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

from idx_leadership.providers.idx_statistics import (
    IDX_MONTHLY_INVESTOR_URL,
    IDXStatisticsError,
    build_monthly_investor_url,
    fetch_idx_html,
    parse_idx_monthly_investor_html,
    write_json_atomic,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="refresh_idx_statistics")
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--month", type=int, required=True)
    parser.add_argument(
        "--url",
        default=None,
        help="Optional canonical IDX monthly URL; defaults to the encoded period URL.",
    )
    parser.add_argument(
        "--html-file",
        type=Path,
        default=None,
        help="Offline rendered HTML input for a no-network parse.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output JSON path; defaults to data/derived/idx_investor_trading_YYYY-MM.json.",
    )
    parser.add_argument(
        "--public-output",
        type=Path,
        default=None,
        help="Optional second atomic output for the web app public directory.",
    )
    parser.add_argument(
        "--retrieved-at",
        default=None,
        help="Optional fixed retrieval timestamp for reproducible exports.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        source_url = args.url or build_monthly_investor_url(args.year, args.month)
        html = (
            args.html_file.read_text(encoding="utf-8")
            if args.html_file is not None
            else fetch_idx_html(source_url)
        )
        payload = parse_idx_monthly_investor_html(
            html,
            source_url=source_url,
            period={"year": args.year, "month": args.month},
            retrieved_at=args.retrieved_at,
        )
        if payload["status"] != "READY":
            raise IDXStatisticsError(
                "IDX release failed reconciliation; no output was written"
            )
        output = args.output or Path(
            f"data/derived/idx_investor_trading_{args.year}-{args.month:02d}.json"
        )
        write_json_atomic(output, payload)
        if args.public_output is not None:
            write_json_atomic(args.public_output, payload)
    except (IDXStatisticsError, OSError, ValueError) as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 2
    print(
        {
            "status": payload["status"],
            "source": source_url,
            "period": payload["release"]["period"],
            "trading_days": payload["release"]["trading_day_count"],
            "net_foreign_value_idr": payload["totals"]["net_foreign_value_idr"],
            "output": str(output),
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

