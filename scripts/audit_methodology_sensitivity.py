"""Run constrained horizon and deterministic group-size diagnostics offline."""
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

import pandas as pd

from idx_leadership.analytics.sensitivity import (
    HORIZON_VARIANTS,
    build_horizon_state_histories,
    build_methodology_sensitivity_report,
    write_methodology_sensitivity_outputs,
)
from idx_leadership.data.snapshots import SnapshotReader
from idx_leadership.utils import data_root, project_root


def _resolve_snapshot(path: Path) -> Path:
    if (path / "manifest.json").exists() and (
        (path / "prices.parquet").exists() or (path / "prices.csv").exists()
    ):
        return path
    reader = SnapshotReader(root=path)
    snapshots = reader.list_snapshots()
    if not snapshots:
        raise FileNotFoundError(f"no snapshot bundles under {path}")
    return snapshots[-1]


def _load_inputs(snapshot_path: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    loaded = SnapshotReader(root=snapshot_path.parent).load(snapshot_path.name)
    prices = loaded.get("prices", pd.DataFrame())
    benchmark = loaded.get("benchmark", pd.DataFrame())
    master = pd.DataFrame(loaded.get("security_master", []))
    if prices.empty or benchmark.empty or master.empty:
        raise ValueError(f"incomplete offline snapshot: {snapshot_path}")
    return prices, benchmark, master[["ticker", "group_id"]]


def _candidate_dates(
    prices: pd.DataFrame, benchmark: pd.DataFrame, maximum: int
) -> list[object]:
    maximum_horizon = max(
        max(variant.short, variant.primary, variant.long)
        for variant in HORIZON_VARIANTS
    )
    price_dates = pd.to_datetime(prices["date"], errors="coerce").dt.date
    benchmark_dates = pd.to_datetime(benchmark["date"], errors="coerce").dt.date
    dates = sorted(set(price_dates.dropna()).intersection(benchmark_dates.dropna()))
    return dates[maximum_horizon:][-maximum:]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m scripts.audit_methodology_sensitivity",
        description="Offline horizon and group-size methodology diagnostics; no forward returns.",
    )
    parser.add_argument(
        "--snapshot",
        type=Path,
        default=data_root() / "snapshots",
        help="Snapshot bundle or root; latest bundle is selected from a root.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=data_root() / "normalized" / "methodology",
    )
    parser.add_argument("--prefix", default="methodology_sensitivity")
    parser.add_argument("--max-observations", type=int, default=12)
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
    for _label, _value in (("--output-dir", args.output_dir),):
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

    if args.max_observations < 2:
        print("--max-observations must be at least 2", file=sys.stderr)
        return 2
    try:
        snapshot = _resolve_snapshot(args.snapshot)
        prices, benchmark, taxonomy = _load_inputs(snapshot)
        dates = _candidate_dates(prices, benchmark, args.max_observations)
        if len(dates) < 2:
            raise ValueError(
                "offline snapshot does not contain at least two common as-of dates after the 60-observation warm-up"
            )
        histories = build_horizon_state_histories(
            prices=prices,
            benchmark=benchmark,
            taxonomy=taxonomy,
            as_of_dates=dates,
        )
        report, horizon_summary, group_summary, group_scenarios = (
            build_methodology_sensitivity_report(histories)
        )
        paths = write_methodology_sensitivity_outputs(
            report,
            histories=histories,
            horizon_summary=horizon_summary,
            group_size_summary=group_summary,
            group_size_scenarios=group_scenarios,
            output_dir=args.output_dir,
            prefix=args.prefix,
        )
    except (FileNotFoundError, KeyError, ValueError) as exc:
        print(f"METHODOLOGY_SENSITIVITY_FAILED {exc}", file=sys.stderr)
        return 2

    print(
        "METHODOLOGY_SENSITIVITY_COMPLETE "
        f"snapshot={snapshot.name} dates={len(dates)} variants={len(histories)} "
        "forward_returns_used=NO"
    )
    print(horizon_summary.to_json(orient="records"))
    for label, path in paths.items():
        print(f"{label}={path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
