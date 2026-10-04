"""Validate the most recent snapshot.

CLI: python -m scripts.validate_data
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from idx_leadership.data.snapshots import SnapshotReader
from idx_leadership.data.quality import assess_quality
from idx_leadership.utils import data_root, get_logger, load_yaml

_log = get_logger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(prog="validate_data")
    parser.add_argument("--universe", default="config/universe.yaml")
    parser.add_argument("--snapshots-dir", default=None)
    args = parser.parse_args()

    universe = load_yaml(args.universe)
    requested = [row["ticker"] for row in universe.get("universe", [])]
    reader = SnapshotReader(root=Path(args.snapshots_dir) if args.snapshots_dir else None)
    snaps = reader.list_snapshots()
    if not snaps:
        print("no_snapshots", file=sys.stderr)
        return 1
    latest = None
    latest_as_of = None
    for snap_dir in snaps:
        try:
            loaded = reader.load(snap_dir.name)
            raw_manifest = loaded.get("manifest") or {}
            raw_entries = raw_manifest.get("entries") or []
            if isinstance(raw_entries, dict):
                raw_entries = list(raw_entries.values())
            first_entry = raw_entries[0] if raw_entries else {}
            as_of = str(first_entry.get("as_of") or "")
            __import__("datetime").date.fromisoformat(as_of)
        except (FileNotFoundError, json.JSONDecodeError, ValueError, KeyError, TypeError, IndexError):
            continue
        if latest_as_of is None or as_of > latest_as_of:
            latest = loaded
            latest_as_of = as_of
    if latest is None:
        print("no_loadable_snapshots", file=sys.stderr)
        return 1
    quality = assess_quality(
        requested_tickers=requested,
        prices=latest["prices"],
        benchmark=latest["benchmark"],
        today=__import__("datetime").date.fromisoformat(latest_as_of),
    )
    print(json.dumps(quality.to_dict(), indent=2, default=str))
    return 0 if quality.status.value in ("READY", "READY_WITH_GAPS") else 2


if __name__ == "__main__":
    sys.exit(main())
