"""Compare public raw/adjusted prices with Sectors fixture or live closes."""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from idx_leadership.models import ProviderMode
from idx_leadership.providers.factory import build_provider_from_config
from idx_leadership.utils import data_root, project_root
from idx_leadership.utils.errors import ProviderError


LIVE_BLOCKED = "SECTORS LIVE COMPARISON BLOCKED"


def _canonical_ticker(ticker: str) -> str:
    value = ticker.strip().upper()
    return value if value.endswith(".JK") else f"{value}.JK"


def _load_public_series(path: Path, ticker: str, start: date, end: date) -> pd.DataFrame:
    frame = pd.read_csv(path)
    frame["date"] = pd.to_datetime(frame["date"]).dt.date
    frame["ticker"] = frame["ticker"].map(_canonical_ticker)
    frame = frame[
        (frame["ticker"] == ticker)
        & (frame["date"] >= start)
        & (frame["date"] <= end)
    ].copy()
    raw_col = "close" if "close" in frame.columns else None
    adjusted_col = "adjusted_close" if "adjusted_close" in frame.columns else raw_col
    if raw_col is None:
        return pd.DataFrame(columns=["ticker", "date", "public_raw", "public_adjusted"])
    return frame.assign(
        public_raw=pd.to_numeric(frame[raw_col], errors="coerce"),
        public_adjusted=pd.to_numeric(frame[adjusted_col], errors="coerce"),
    )[["ticker", "date", "public_raw", "public_adjusted"]]


def _discontinuity_table(series: pd.DataFrame, event_date: date) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for column in ("public_raw", "public_adjusted", "sectors_close"):
        if column not in series.columns:
            continue
        values = series[["date", column]].dropna().sort_values("date").copy()
        values["return"] = values[column].pct_change()
        for _, row in values.iterrows():
            rows.append(
                {
                    "date": row["date"],
                    "series": column,
                    "return": None if pd.isna(row["return"]) else float(row["return"]),
                    "corporate_action_window": abs((row["date"] - event_date).days) <= 1,
                }
            )
    return pd.DataFrame(
        rows,
        columns=["date", "series", "return", "corporate_action_window"],
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="audit_price_basis")
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--start", required=True, help="YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="YYYY-MM-DD")
    parser.add_argument("--corporate-action-date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--public-csv", default="tests/fixtures/prices.csv")
    parser.add_argument(
        "--sectors-mode",
        choices=[ProviderMode.SECTORS_FIXTURE.value, ProviderMode.SECTORS_LIVE.value],
        default=ProviderMode.SECTORS_FIXTURE.value,
    )
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--allow-credit-spend", action="store_true")
    parser.add_argument("--force-refresh", action="store_true")
    parser.add_argument("--max-pages", type=int, default=1)
    parser.add_argument(
        "--as-of",
        default=None,
        help="Optional reference as-of date (YYYY-MM-DD) recorded in the report for live runs; does not change the requested price window.",
    )
    parser.add_argument("--out", default=None)
    parser.add_argument(
        "--allow-outside-root",
        action="store_true",
        help="Acknowledge writing outputs outside the project root.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    # Root containment for --out/--output (export pattern): outputs must
    # stay within the project root — or the system temp dir used by
    # isolated/pytest harnesses — unless --allow-outside-root is set.
    _project_root = project_root()
    _temp_root = Path(tempfile.gettempdir()).resolve()
    for _label, _value in (("--out", args.out),):
        if _value:
            _resolved = Path(_value).resolve()
            _inside_root = True
            try:
                _resolved.relative_to(_project_root.resolve())
            except ValueError:
                _inside_root = False
            _inside_temp = True
            try:
                _resolved.relative_to(_temp_root)
            except ValueError:
                _inside_temp = False
            if not (_inside_root or _inside_temp) and not getattr(
                args, "allow_outside_root", False
            ):
                print(
                    f"refusing {_label} outside {_project_root} without --allow-outside-root",
                    file=sys.stderr,
                )
                return 2

    ticker = _canonical_ticker(args.ticker)
    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)
    event_date = date.fromisoformat(args.corporate_action_date)
    if start > end or args.max_pages < 1:
        print("BLOCKED invalid date range or --max-pages", file=sys.stderr)
        return 2

    public = _load_public_series(Path(args.public_csv), ticker, start, end)
    mode = ProviderMode(args.sectors_mode)
    report: dict[str, Any] = {
        "ticker": ticker,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "corporate_action_date": event_date.isoformat(),
        "as_of": (date.fromisoformat(args.as_of).isoformat() if args.as_of else end.isoformat()),
        "public_source": str(args.public_csv),
        "sectors_mode": mode.value,
        "sectors_live_status": LIVE_BLOCKED,
        "fixture_warning": (
            "SYNTHETIC SECTORS FIXTURE — NOT A LIVE PRICE-BASIS RESULT"
            if mode is ProviderMode.SECTORS_FIXTURE
            else None
        ),
        "errors": [],
    }
    provider: Any = None

    if mode is ProviderMode.SECTORS_LIVE:
        if not (args.live and args.allow_credit_spend):
            report["errors"].append(
                f"{LIVE_BLOCKED} — require --live and --allow-credit-spend"
            )
            sectors = pd.DataFrame(columns=["ticker", "date", "sectors_close"])
        elif not os.environ.get("SECTORS_API_KEY", "").strip():
            report["errors"].append(f"{LIVE_BLOCKED} — SECTORS_API_KEY unavailable")
            sectors = pd.DataFrame(columns=["ticker", "date", "sectors_close"])
        else:
            provider = build_provider_from_config(
                mode=ProviderMode.SECTORS_LIVE,
                allow_live=True,
                max_pages=args.max_pages,
                force_refresh=args.force_refresh,
            )
            frames: list[pd.DataFrame] = []
            for market_date in pd.bdate_range(start=start, end=end).date:
                try:
                    cross_section = provider.get_full_universe_close(market_date)
                except ProviderError as exc:
                    report["errors"].append(f"{market_date}: {exc}")
                    continue
                row = cross_section[cross_section["ticker"] == ticker].copy()
                if not row.empty:
                    frames.append(
                        row[["ticker", "date", "close"]].rename(
                            columns={"close": "sectors_close"}
                        )
                    )
            sectors = (
                pd.concat(frames, ignore_index=True)
                if frames
                else pd.DataFrame(columns=["ticker", "date", "sectors_close"])
            )
            report["sectors_live_status"] = (
                "SECTORS LIVE COMPARISON EXECUTED" if not sectors.empty else LIVE_BLOCKED
            )
    else:
        provider = build_provider_from_config(
            mode=ProviderMode.SECTORS_FIXTURE,
            max_pages=args.max_pages,
        )
        frames = []
        for market_date in pd.bdate_range(start=start, end=end).date:
            try:
                cross_section = provider.get_full_universe_close(market_date)
            except ProviderError:
                continue
            row = cross_section[cross_section["ticker"] == ticker].copy()
            if not row.empty:
                frames.append(
                    row[["ticker", "date", "close"]].rename(
                        columns={"close": "sectors_close"}
                    )
                )
        sectors = (
            pd.concat(frames, ignore_index=True)
            if frames
            else pd.DataFrame(columns=["ticker", "date", "sectors_close"])
        )

    series = public.merge(sectors, on=["ticker", "date"], how="outer").sort_values("date")
    discontinuities = _discontinuity_table(series, event_date)

    corporate_actions: Any = "UNAVAILABLE"
    try:
        if provider is not None:
            corporate_actions = provider.get_corporate_actions(ticker)
    except ProviderError:
        pass

    out_dir = (
        Path(args.out)
        if args.out
        else data_root() / "normalized" / f"price_basis_{ticker.replace('.', '_')}"
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    series.to_csv(out_dir / "series.csv", index=False)
    discontinuities.to_csv(out_dir / "return_discontinuities.csv", index=False)
    report.update(
        {
            "rows": {
                "public": int(public[["public_raw", "public_adjusted"]].dropna(how="all").shape[0]),
                "sectors": int(sectors.shape[0]),
            },
            "corporate_action_metadata": corporate_actions,
            "outputs": ["series.csv", "return_discontinuities.csv"],
        }
    )
    (out_dir / "report.json").write_text(
        json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8"
    )
    print(report["sectors_live_status"])
    print(f"wrote {out_dir}")
    return 2 if mode is ProviderMode.SECTORS_LIVE and report["sectors_live_status"] == LIVE_BLOCKED else 0


if __name__ == "__main__":
    sys.exit(main())
