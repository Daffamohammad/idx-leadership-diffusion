"""Generate leadership and diffusion churn evidence from offline snapshots."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from idx_leadership.analytics.turnover import (
    analyze_state_turnover,
    write_turnover_outputs,
)
from idx_leadership.data.snapshots import SnapshotReader
from idx_leadership.utils import data_root


def load_group_history(snapshots_dir: Path) -> pd.DataFrame:
    reader = SnapshotReader(root=snapshots_dir)
    rows: list[pd.DataFrame] = []
    for snapshot_path in reader.list_snapshots():
        loaded = reader.load(snapshot_path.name)
        groups = loaded.get("groups", pd.DataFrame()).copy()
        if groups.empty:
            continue
        if "snapshot_date" not in groups.columns:
            manifest = loaded.get("manifest", {})
            entries = manifest.get("entries", [])
            snapshot_date = entries[0].get("as_of") if entries else None
            groups["snapshot_date"] = snapshot_date
        required = {
            "snapshot_date",
            "group_id",
            "leadership_state",
            "diffusion_state",
        }
        missing = required.difference(groups.columns)
        if missing:
            raise ValueError(
                f"{snapshot_path.name} groups missing: {', '.join(sorted(missing))}"
            )
        rows.append(groups[list(required)])
    if not rows:
        return pd.DataFrame(
            columns=[
                "snapshot_date",
                "group_id",
                "leadership_state",
                "diffusion_state",
            ]
        )
    return pd.concat(rows, ignore_index=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m scripts.audit_state_turnover",
        description="Offline state churn, reversal, duration, and transition audit.",
    )
    parser.add_argument(
        "--snapshots-dir",
        type=Path,
        default=data_root() / "snapshots",
        help="Snapshot bundle root (default: data/snapshots).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=data_root() / "normalized" / "methodology",
    )
    parser.add_argument("--prefix", default="state_turnover")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        history = load_group_history(args.snapshots_dir)
        if history["snapshot_date"].nunique() < 2:
            print(
                "NEED_AT_LEAST_2_SNAPSHOTS "
                f"found={history['snapshot_date'].nunique()} root={args.snapshots_dir}",
                file=sys.stderr,
            )
            return 2
        report = analyze_state_turnover(history)
        paths = write_turnover_outputs(
            report, output_dir=args.output_dir, prefix=args.prefix
        )
    except (FileNotFoundError, ValueError) as exc:
        print(f"STATE_TURNOVER_AUDIT_FAILED {exc}", file=sys.stderr)
        return 2

    print(
        "STATE_TURNOVER_AUDIT_COMPLETE "
        f"snapshots={report.snapshot_count} groups={report.group_count} "
        f"leadership_change_pct={report.leadership.change_pct} "
        f"diffusion_change_pct={report.diffusion.change_pct}"
    )
    for label, path in paths.items():
        print(f"{label}={path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
