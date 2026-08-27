"""Stale-trading / inactive-name study.

For a given as-of date, walks the universe and measures:
* latest close age (calendar days)
* number of trading days in the last 30 calendar days
* number of distinct closes in the last 30 calendar days
* mean absolute daily move in the last 30 calendar days
* is_stale: true if latest close age > stale_trading_days

Outputs a CSV; logs the headline stats to stderr.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from idx_leadership.providers.factory import build_provider_from_config
from idx_leadership.utils import data_root, get_logger
from idx_leadership.utils.errors import ProviderError

_log = get_logger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(prog="run_stale_trading")
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--back-days", type=int, default=30)
    parser.add_argument("--out", default=None)
    parser.add_argument("--allow-live", action="store_true")
    args = parser.parse_args()

    as_of = date.fromisoformat(args.as_of)
    out_path = Path(args.out) if args.out else (data_root() / "normalized" / f"stale_trading_{as_of.isoformat()}.csv")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    provider = build_provider_from_config(preferred="sectors", allow_live=args.allow_live)
    # Walk back to fetch a multi-day cross-section
    rows: list[dict] = []
    for i in range(args.back_days + 5):
        d = as_of - timedelta(days=i)
        try:
            cs = provider.get_full_universe_close(d)
        except ProviderError as e:
            print(f"provider error at {d}: {e}", file=sys.stderr)
            continue
        if cs.empty:
            continue
        cs = cs[["ticker", "date", "close"]]
        rows.append(cs)
    if not rows:
        print("BLOCKED no data", file=sys.stderr)
        return 2
    hist = pd.concat(rows, ignore_index=True)
    hist["date"] = pd.to_datetime(hist["date"]).dt.date

    cutoff = as_of - timedelta(days=args.back_days)
    window = hist[hist["date"] >= cutoff].copy()
    window_sorted = window.sort_values(["ticker", "date"])

    out_rows: list[dict] = []
    for tkr, g in window_sorted.groupby("ticker"):
        n_obs = int(len(g))
        n_distinct = int(g["close"].nunique(dropna=True))
        last_date = g["date"].max()
        age = (as_of - last_date).days if last_date else None
        # Mean absolute daily move (excluding the first row)
        moves = g["close"].diff().abs().dropna()
        mean_abs_move = float(moves.mean()) if not moves.empty else None
        out_rows.append(
            {
                "ticker": tkr,
                "n_obs_30d": n_obs,
                "n_distinct_30d": n_distinct,
                "latest_close_date": str(last_date),
                "latest_close_age_days": age,
                "mean_abs_daily_move": mean_abs_move,
                "is_stale": bool(age is None or age > 14),
            }
        )
    df = pd.DataFrame(out_rows).sort_values("latest_close_age_days", ascending=False)
    df.to_csv(out_path, index=False)
    n = int(len(df))
    n_stale = int(df["is_stale"].sum())
    pct_stale = (n_stale / max(1, n)) * 100
    print(f"wrote stale-trading study to {out_path}")
    print(f"securities={n} stale={n_stale} ({pct_stale:.1f}%)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
