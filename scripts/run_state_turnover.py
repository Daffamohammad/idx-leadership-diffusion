"""Run a state-turnover study over a list of historical snapshots.

Reads the snapshots in `data/snapshots/<kind>/`, computes per-group
state transitions, and reports churn metrics.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from idx_leadership.data.snapshots import SnapshotReader
from idx_leadership.utils import data_root, get_logger

_log = get_logger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(prog="run_state_turnover")
    parser.add_argument(
        "--snapshots-dir",
        default=None,
        help="Root for snapshots (default: data/snapshots/sectors).",
    )
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    root = Path(args.snapshots_dir) if args.snapshots_dir else (data_root() / "snapshots" / "sectors")
    out_path = Path(args.out) if args.out else (data_root() / "normalized" / "state_turnover.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    reader = SnapshotReader(root=root)
    snaps = sorted(reader.list_snapshots(), key=lambda p: p.name)
    if len(snaps) < 2:
        print(f"NEED_AT_LEAST_2_SNAPSHOTS found={len(snaps)} root={root}", file=sys.stderr)
        return 2

    series: dict[str, list[str]] = defaultdict(list)
    dates: list[str] = []
    for s in snaps:
        loaded = reader.load(s.name)
        groups = loaded.get("groups", pd.DataFrame())
        if groups.empty:
            continue
        dates.append(s.name)
        for _, r in groups.iterrows():
            series[r["group_id"]].append(r.get("leadership_state", "UNCONFIRMED"))

    out: dict[str, Any] = {
        "snapshots_used": dates,
        "n_groups": len(series),
        "per_group": {},
    }
    n_transitions = 0
    n_periods = 0
    for gid, states in series.items():
        changes = sum(1 for i in range(1, len(states)) if states[i] != states[i - 1])
        n_transitions += changes
        n_periods += max(0, len(states) - 1)
        flips = [
            f"{states[i-1]}->{states[i]}" for i in range(1, len(states)) if states[i] != states[i - 1]
        ]
        out["per_group"][gid] = {
            "n_periods": len(states) - 1,
            "n_changes": changes,
            "change_rate": round(changes / max(1, len(states) - 1), 4),
            "state_sequence": states,
            "transitions": flips,
        }
    out["aggregate"] = {
        "total_transitions": n_transitions,
        "total_periods": n_periods,
        "mean_change_rate": round(n_transitions / max(1, n_periods), 4),
    }
    out_path.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    print(f"wrote state turnover study to {out_path}")
    print(f"groups={out['n_groups']} periods={n_periods} mean_change_rate={out['aggregate']['mean_change_rate']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
