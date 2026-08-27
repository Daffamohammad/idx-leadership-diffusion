"""Close-basis empirical audit.

Pulls a Sectors price series across a known corporate action and
classifies the basis as raw / adjusted / unknown.

Usage:
  python -m scripts.audit_close_basis --symbol BBCA.JK \\
      --split-date 2021-10-13 --split-ratio 5 --allow-live

Requires a live Sectors key. Without `--allow-live`, raises.
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
    parser = argparse.ArgumentParser(prog="audit_close_basis")
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--split-date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--split-ratio", type=float, required=True,
                        help="e.g. 5 means a 5:1 split (post-split is 1/5 of pre-split for raw).")
    parser.add_argument("--back-days", type=int, default=10)
    parser.add_argument("--out", default=None)
    parser.add_argument("--allow-live", action="store_true")
    args = parser.parse_args()

    if not args.allow_live:
        print("BLOCKED require --allow-live to make Sectors HTTP calls", file=sys.stderr)
        return 2

    out_path = Path(args.out) if args.out else (data_root() / "normalized" / f"close_basis_{args.symbol}.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    sd = date.fromisoformat(args.split_date)
    provider = build_provider_from_config(preferred="sectors", allow_live=True)

    rows: list[dict] = []
    for i in range(args.back_days * 2 + 1):
        d = sd - timedelta(days=args.back_days) + timedelta(days=i)
        try:
            cs = provider.get_full_universe_close(d)
        except ProviderError as e:
            print(f"provider error at {d}: {e}", file=sys.stderr)
            continue
        if cs.empty:
            continue
        r = cs[cs["ticker"] == args.symbol]
        if not r.empty:
            rows.append({"date": d, "close": float(r.iloc[0]["close"])})
    if not rows:
        print(f"NO_DATA for {args.symbol}", file=sys.stderr)
        return 2
    df = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)
    pre = df[df["date"] < sd]
    post = df[df["date"] >= sd]
    out: dict[str, Any] = {
        "symbol": args.symbol,
        "split_date": sd.isoformat(),
        "split_ratio": args.split_ratio,
        "n_pre": int(len(pre)),
        "n_post": int(len(post)),
        "pre_mean_close": float(pre["close"].mean()) if not pre.empty else None,
        "post_mean_close": float(post["close"].mean()) if not post.empty else None,
    }
    if out["pre_mean_close"] and out["post_mean_close"]:
        observed_ratio = out["pre_mean_close"] / out["post_mean_close"]
        out["observed_ratio"] = round(observed_ratio, 4)
        if abs(observed_ratio - args.split_ratio) < 0.05 * args.split_ratio:
            out["classification"] = "CONFIRMED_RAW_CLOSE"
        elif abs(observed_ratio - 1.0) < 0.05:
            out["classification"] = "CONFIRMED_ADJUSTED_CLOSE"
        else:
            out["classification"] = "UNKNOWN"
    out_path.write_text(__import__("json").dumps(out, indent=2, default=str), encoding="utf-8")
    print(f"wrote close-basis audit to {out_path}")
    print(out.get("classification", "UNKNOWN"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
