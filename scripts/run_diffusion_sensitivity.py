"""Diffusion sensitivity study.

Compares baseline v1 (raw ±10pp) vs v2 (group-size-aware) classifications
for a given snapshot directory.

Reports per-group classification agreement and small-group stability.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from idx_leadership.data.snapshots import SnapshotReader
from idx_leadership.signals.diffusion import classify_diffusion
from idx_leadership.signals.diffusion_v2 import (
    DiffusionStateV2,
    classify_diffusion_v2,
    to_v1_state,
)
from idx_leadership.utils import data_root, get_logger

_log = get_logger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(prog="run_diffusion_sensitivity")
    parser.add_argument("--snapshots-dir", default=None)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()
    root = Path(args.snapshots_dir) if args.snapshots_dir else (data_root() / "snapshots" / "sectors")
    out_path = Path(args.out) if args.out else (data_root() / "normalized" / f"diffusion_sensitivity.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    reader = SnapshotReader(root=root)
    snaps = reader.list_snapshots()
    if len(snaps) < 2:
        print(f"NEED_AT_LEAST_2_SNAPSHOTS found={len(snaps)}", file=sys.stderr)
        return 2

    cur = reader.load(snaps[-1].name)
    prev = reader.load(snaps[-2].name)
    cur_g = cur.get("groups", pd.DataFrame())
    prev_g = prev.get("groups", pd.DataFrame())
    if cur_g.empty or prev_g.empty:
        print("EMPTY groups in snapshots", file=sys.stderr)
        return 2

    cur_map = {r["group_id"]: r for _, r in cur_g.iterrows()}
    prev_map = {r["group_id"]: r for _, r in prev_g.iterrows()}

    out: dict[str, Any] = {"per_group": {}, "aggregate": {}}
    n_match = 0
    n_total = 0
    by_size_bucket: dict[str, dict[str, int]] = {"small (<=10)": Counter(), "medium (11-30)": Counter(), "large (>30)": Counter()}

    for gid, cur_row in cur_map.items():
        prev_row = prev_map.get(gid)
        if prev_row is None:
            continue
        cur_b = cur_row.get("breadth_outperforming")
        prev_b = prev_row.get("breadth_outperforming")
        n_total += 1
        if pd.isna(cur_b) or pd.isna(prev_b):
            continue
        # crude group size proxy: missing here. Use eligible_count.
        gs = int(cur_row.get("eligible_count") or 0)
        bucket = "small (<=10)" if gs <= 10 else ("medium (11-30)" if gs <= 30 else "large (>30)")
        v1 = classify_diffusion(
            breadth_delta_pp=(float(cur_b) - float(prev_b)) if cur_b is not None and prev_b is not None else None,
            broadening_threshold_pp=10.0,
            narrowing_threshold_pp=-10.0,
        )
        v2 = classify_diffusion_v2(
            breadth_current=float(cur_b),
            breadth_previous=float(prev_b),
            group_size=gs,
        )
        v1_str = v1.value if hasattr(v1, "value") else str(v1)
        v2_str = to_v1_state(v2)
        match = v1_str == v2_str
        if match:
            n_match += 1
        by_size_bucket[bucket][v1_str] += 1
        by_size_bucket[bucket][v2_str] += 1
        out["per_group"][gid] = {
            "group_size": gs,
            "bucket": bucket,
            "v1_state": v1_str,
            "v2_state": v2_str,
            "agree": match,
        }
    out["aggregate"] = {
        "n_groups": n_total,
        "n_agreement": n_match,
        "agreement_rate": round(n_match / max(1, n_total), 4),
    }
    out_path.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    print(f"wrote diffusion sensitivity to {out_path}")
    print(f"agreement: {n_match}/{n_total} ({out['aggregate']['agreement_rate'] * 100:.1f}%)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
