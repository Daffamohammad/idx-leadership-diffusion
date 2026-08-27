"""Public-vs-Sectors parity harness with synthetic and live modes.

Fixture results are always labelled synthetic. Live Sectors calls require the
same explicit intent gates used by the validation command.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Mapping

import pandas as pd

from idx_leadership.models import ProviderMode
from idx_leadership.providers.factory import build_provider_from_config
from idx_leadership.utils import data_root
from idx_leadership.utils.errors import ProviderError


PARITY_CLASSIFICATIONS = (
    "MATCH",
    "EXPECTED_SOURCE_DIFF",
    "DATE_ALIGNMENT",
    "PRICE_BASIS",
    "CORPORATE_ACTION",
    "MAPPING",
    "UNEXPLAINED",
)

PARITY_COLUMNS = (
    "Ticker",
    "Date",
    "Metric",
    "Public",
    "Sectors",
    "Difference",
    "Classification",
)


def _canonical_ticker(value: Any) -> str:
    ticker = str(value or "").strip().upper()
    if not ticker:
        return ""
    return ticker if ticker.endswith(".JK") else f"{ticker}.JK"


def _action_dates(corporate_actions: Iterable[Mapping[str, Any]] | None) -> set[date]:
    dates: set[date] = set()
    for action in corporate_actions or []:
        raw = action.get("date") or action.get("ex_date")
        if not raw:
            continue
        try:
            dates.add(date.fromisoformat(str(raw)))
        except ValueError:
            continue
    return dates


def build_parity_table(
    public: pd.DataFrame,
    sectors: pd.DataFrame,
    *,
    public_value: str = "adjusted_close",
    sectors_value: str = "close",
    metric: str = "CLOSE",
    corporate_actions: Iterable[Mapping[str, Any]] | None = None,
    price_basis_confirmed: bool = False,
    match_tolerance: float = 1e-9,
    expected_source_tolerance: float = 0.001,
) -> pd.DataFrame:
    """Return the canonical seven-column parity report."""

    left = public[["ticker", "date", public_value]].copy()
    right = sectors[["ticker", "date", sectors_value]].copy()
    left["raw_public_ticker"] = left["ticker"].astype(str)
    right["raw_sectors_ticker"] = right["ticker"].astype(str)
    left["ticker"] = left["ticker"].map(_canonical_ticker)
    right["ticker"] = right["ticker"].map(_canonical_ticker)
    left["date"] = pd.to_datetime(left["date"]).dt.date
    right["date"] = pd.to_datetime(right["date"]).dt.date
    left = left.rename(columns={public_value: "Public"})
    right = right.rename(columns={sectors_value: "Sectors"})
    merged = left.merge(right, on=["ticker", "date"], how="outer")
    event_dates = _action_dates(corporate_actions)
    rows: list[dict[str, Any]] = []

    for _, row in merged.sort_values(["ticker", "date"]).iterrows():
        public_value_raw = row.get("Public")
        sectors_value_raw = row.get("Sectors")
        public_number = None if pd.isna(public_value_raw) else float(public_value_raw)
        sectors_number = None if pd.isna(sectors_value_raw) else float(sectors_value_raw)
        raw_public = row.get("raw_public_ticker")
        raw_sectors = row.get("raw_sectors_ticker")
        mapping_diff = (
            pd.notna(raw_public)
            and pd.notna(raw_sectors)
            and str(raw_public).upper() != str(raw_sectors).upper()
        )

        if mapping_diff:
            classification = "MAPPING"
            difference = (
                sectors_number - public_number
                if sectors_number is not None and public_number is not None
                else None
            )
        elif public_number is None or sectors_number is None:
            classification = "DATE_ALIGNMENT"
            difference = None
        else:
            difference = sectors_number - public_number
            relative = abs(difference) / abs(public_number) if public_number != 0 else abs(difference)
            if abs(difference) <= match_tolerance:
                classification = "MATCH"
            elif row["date"] in event_dates:
                classification = "CORPORATE_ACTION"
            elif price_basis_confirmed and relative > expected_source_tolerance:
                classification = "PRICE_BASIS"
            elif relative <= expected_source_tolerance:
                classification = "EXPECTED_SOURCE_DIFF"
            else:
                classification = "UNEXPLAINED"

        rows.append(
            {
                "Ticker": row["ticker"],
                "Date": row["date"],
                "Metric": metric,
                "Public": public_number,
                "Sectors": sectors_number,
                "Difference": difference,
                "Classification": classification,
            }
        )
    return pd.DataFrame(rows, columns=PARITY_COLUMNS)


def _load_public_fixture(path: Path, tickers: list[str], as_of: date) -> pd.DataFrame:
    frame = pd.read_csv(path)
    frame["date"] = pd.to_datetime(frame["date"]).dt.date
    frame["ticker"] = frame["ticker"].map(_canonical_ticker)
    return frame[(frame["ticker"].isin(tickers)) & (frame["date"] == as_of)].copy()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="compare_providers")
    parser.add_argument("--as-of", required=True, help="YYYY-MM-DD")
    parser.add_argument("--tickers", default="BBCA.JK,ADRO.JK,KLBF.JK")
    parser.add_argument("--public-fixture", default="tests/fixtures/prices.csv")
    parser.add_argument("--public-live", action="store_true")
    parser.add_argument(
        "--sectors-mode",
        choices=[ProviderMode.SECTORS_FIXTURE.value, ProviderMode.SECTORS_LIVE.value],
        default=ProviderMode.SECTORS_FIXTURE.value,
    )
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--allow-credit-spend", action="store_true")
    parser.add_argument("--max-pages", type=int, default=1)
    parser.add_argument("--force-refresh", action="store_true")
    parser.add_argument("--out", default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    as_of = date.fromisoformat(args.as_of)
    tickers = [_canonical_ticker(value) for value in args.tickers.split(",") if value.strip()]
    mode = ProviderMode(args.sectors_mode)
    if args.max_pages < 1:
        print("BLOCKED --max-pages must be at least 1", file=sys.stderr)
        return 2
    if mode is ProviderMode.SECTORS_LIVE:
        if not (args.live and args.allow_credit_spend):
            print(
                "BLOCKED SECTORS_LIVE parity requires --live and --allow-credit-spend",
                file=sys.stderr,
            )
            return 2
        if not os.environ.get("SECTORS_API_KEY", "").strip():
            print("BLOCKED SECTORS_API_KEY is unavailable", file=sys.stderr)
            return 2

    if args.public_live:
        public_provider = build_provider_from_config(mode=ProviderMode.PUBLIC_PROTOTYPE)
        try:
            public = public_provider.get_price_history(tickers, start=as_of, end=as_of)
        except ProviderError as exc:
            print(f"public provider error: {exc}", file=sys.stderr)
            return 2
    else:
        public = _load_public_fixture(Path(args.public_fixture), tickers, as_of)

    sectors_provider = build_provider_from_config(
        mode=mode,
        allow_live=mode is ProviderMode.SECTORS_LIVE,
        max_pages=args.max_pages,
        force_refresh=args.force_refresh,
    )
    try:
        sectors = sectors_provider.get_full_universe_close(as_of)
    except ProviderError as exc:
        print(f"sectors provider error: {exc}", file=sys.stderr)
        return 2
    sectors = sectors[sectors["ticker"].isin(tickers)].copy()

    public_value = "adjusted_close" if "adjusted_close" in public.columns else "close"
    parity = build_parity_table(
        public,
        sectors,
        public_value=public_value,
        sectors_value="close",
    )
    synthetic = mode is ProviderMode.SECTORS_FIXTURE
    out_path = (
        Path(args.out)
        if args.out
        else data_root() / "normalized" / f"provider_parity_{as_of.isoformat()}.csv"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    parity.to_csv(out_path, index=False)
    metadata = {
        "provider_mode": mode.value,
        "synthetic": synthetic,
        "result_label": (
            "SYNTHETIC FIXTURE PARITY HARNESS — NOT LIVE SECTORS PARITY"
            if synthetic
            else "LIVE PROVIDER PARITY"
        ),
        "as_of": as_of.isoformat(),
        "rows": len(parity),
        "classifications": parity["Classification"].value_counts().to_dict(),
        "allowed_classifications": list(PARITY_CLASSIFICATIONS),
    }
    out_path.with_suffix(".metadata.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )
    print(metadata["result_label"])
    print(parity.to_string(index=False))
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
