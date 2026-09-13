"""Export diagnostics — descriptive, not performance claims.

CLI: python -m scripts.export_diagnostics
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

import pandas as pd

from idx_leadership.data.snapshots import SnapshotReader
from idx_leadership.utils import data_root, get_logger, project_root

_log = get_logger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(prog="export_diagnostics")
    parser.add_argument("--snapshots-dir", default=None)
    parser.add_argument("--out", default="data/normalized/diagnostics.csv")
    parser.add_argument(
        "--allow-outside-root",
        action="store_true",
        help="Acknowledge writing outputs outside the project root.",
    )
    args = parser.parse_args()
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

    reader = SnapshotReader(root=Path(args.snapshots_dir) if args.snapshots_dir else None)
    rows: list[dict] = []
    for p in reader.list_snapshots():
        snap = reader.load(p.name)
        groups = snap.get("groups", pd.DataFrame())
        if groups.empty:
            continue
        for _, r in groups.iterrows():
            rows.append(
                {
                    "snapshot_id": p.name,
                    "snapshot_date": r.get("snapshot_date"),
                    "group_id": r.get("group_id"),
                    "leadership_state": r.get("leadership_state"),
                    "diffusion_state": r.get("diffusion_state"),
                    "group_excess_return": r.get("group_excess_return"),
                    "breadth_outperforming": r.get("breadth_outperforming"),
                    "breadth_delta": r.get("breadth_delta"),
                    "top1_contribution_share": r.get("top1_contribution_share"),
                    "leadership_rank": r.get("leadership_rank"),
                    "change_rank": r.get("change_rank"),
                }
            )
    if not rows:
        print("no_diagnostics", file=sys.stderr)
        return 1
    df = pd.DataFrame(rows)
    out_path = data_root() / "normalized" / "diagnostics.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)
    print(f"wrote {len(df)} rows to {out_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
