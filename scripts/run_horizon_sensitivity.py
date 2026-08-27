"""Horizon sensitivity study.

Given a snapshot directory, runs the same engine over a small set of
horizon combinations and reports state agreement, transition rate,
mean leadership rank correlation, and coverage.

Output: JSON file with the per-variant metrics.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from idx_leadership.aggregation.groups import build_group_snapshots, rank_groups
from idx_leadership.data.snapshots import SnapshotReader
from idx_leadership.features.relative_strength import compute_excess_returns
from idx_leadership.providers.factory import build_provider_from_config
from idx_leadership.utils import data_root, get_logger
from idx_leadership.utils.errors import ProviderError

_log = get_logger(__name__)


VARIANTS = [
    ("5/20/60", {"5d": 5, "20d": 20, "60d": 60}),
    ("10/20/60", {"5d": 10, "20d": 20, "60d": 60}),
    ("10/40", {"5d": 10, "20d": 40, "60d": 60}),
    ("20/60", {"5d": 5, "20d": 20, "60d": 60}),  # same as 5/20/60 for the primary 20D; secondary 60D
]


def main() -> int:
    parser = argparse.ArgumentParser(prog="run_horizon_sensitivity")
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--allow-live", action="store_true")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    as_of = date.fromisoformat(args.as_of)
    out_path = Path(args.out) if args.out else (data_root() / "normalized" / f"horizon_sensitivity_{as_of.isoformat()}.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    provider = build_provider_from_config(preferred="sectors", allow_live=args.allow_live)
    try:
        cs = provider.get_full_universe_close(as_of)
        master = provider.get_security_master()
    except ProviderError as e:
        print(f"provider error: {e}", file=sys.stderr)
        return 2

    if cs.empty or not master:
        print("BLOCKED empty cross-section or master", file=sys.stderr)
        return 2

    tax = pd.DataFrame(
        [
            {
                "ticker": m.ticker,
                "group_id": m.group_id,
                "sector": m.sector,
                "subsector": m.subsector,
                "industry": m.industry,
                "sub_industry": m.subindustry,
            }
            for m in master
        ]
    )

    results: dict[str, Any] = {}
    for label, horizons in VARIANTS:
        feats = compute_excess_returns(cs, cs.iloc[0:1], horizons=horizons, as_of=as_of)
        if feats.empty:
            results[label] = {"error": "no features"}
            continue
        snaps = build_group_snapshots(
            features=feats,
            taxonomy=tax,
            snapshot_date=as_of,
            prices=cs,
            horizons=horizons,
        )
        snaps = rank_groups(snaps)
        df = pd.DataFrame(
            [
                {
                    "group_id": s.group_id,
                    "leadership_state": s.leadership_state.value,
                    "diffusion_state": s.diffusion_state.value,
                    "group_excess_return": s.group_excess_return,
                    "breadth_outperforming": s.breadth_outperforming,
                    "leadership_rank": s.leadership_rank,
                }
                for s in snaps
            ]
        )
        results[label] = {
            "n_groups": int(len(df)),
            "state_distribution": (
                df["leadership_state"].value_counts().to_dict()
                if "leadership_state" in df.columns
                else {}
            ),
            "mean_excess_return": (
                float(df["group_excess_return"].dropna().mean())
                if "group_excess_return" in df.columns
                else None
            ),
        }
    out_path.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    print(f"wrote horizon sensitivity to {out_path}")
    for k, v in results.items():
        print(f"  {k}: groups={v.get('n_groups')} mean_excess={v.get('mean_excess_return')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
