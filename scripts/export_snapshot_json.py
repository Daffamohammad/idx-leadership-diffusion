"""Export a snapshot directory as a single JSON file for the React UI.

CLI:
    python -m scripts.export_snapshot_json --snapshot-id snap_2026-08-20
    python -m scripts.export_snapshot_json --latest

The output is written to app/web/public/snapshots/<id>.json so the Vite dev
server can serve it as a static asset (GET /snapshots/<id>.json).
"""
from __future__ import annotations

import argparse
import json
import math
import os
import tempfile
from pathlib import Path
from typing import Any

import pandas as pd

from idx_leadership.data.snapshots import SnapshotReader
from idx_leadership.data.comparability import check_snapshot_compatibility
from idx_leadership.utils import project_root, get_logger

_log = get_logger(__name__)

PUBLIC_DIR = project_root() / "app" / "web" / "public" / "snapshots"


def _records(df: pd.DataFrame | None) -> list[dict[str, Any]]:
    """DataFrame -> list[dict] with NaN->None and ISO date strings."""
    if df is None or df.empty:
        return []
    out = df.copy()
    for col in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[col]):
            out[col] = out[col].dt.strftime("%Y-%m-%d")
    encoded = out.to_json(orient="records", date_format="iso")
    return json.loads(encoded) if encoded is not None else []


def _iso_date(value: Any) -> str | None:
    if value is None:
        return None
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.date().isoformat()


def _finite_number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _build_breadth_history(
    reader: SnapshotReader,
    snapshot_id: str,
    current_snapshot: dict[str, Any],
) -> list[dict[str, Any]]:
    """Build history only from persisted absolute group observations.

    A transition's ``breadth_delta`` is a difference, not a level.  It cannot
    be converted into an absolute breadth value without the prior level, so
    transitions are deliberately not used as a history source here.
    """
    current_entries = (current_snapshot.get("manifest") or {}).get("entries") or []
    if not current_entries or not isinstance(current_entries[0], dict):
        return []
    current_entry = current_entries[0]
    current_as_of = _iso_date(current_entry.get("as_of"))
    if current_as_of is None:
        return []

    points: dict[tuple[str, str], dict[str, Any]] = {}
    for snapshot_path in reader.list_snapshots():
        if snapshot_path.name == snapshot_id:
            loaded = current_snapshot
        else:
            try:
                loaded = reader.load(snapshot_path.name)
            except (FileNotFoundError, json.JSONDecodeError, OSError):
                continue

        entries = (loaded.get("manifest") or {}).get("entries") or []
        if not entries or not isinstance(entries[0], dict):
            continue
        entry = entries[0]
        as_of = _iso_date(entry.get("as_of"))
        if as_of is None or as_of > current_as_of:
            continue
        if snapshot_path.name != snapshot_id:
            if as_of >= current_as_of:
                continue
            if not check_snapshot_compatibility(current_entry, entry).comparable:
                continue

        for row in _records(loaded.get("groups")):
            group_id = row.get("group_id")
            breadth = _finite_number(row.get("breadth_outperforming"))
            if not isinstance(group_id, str) or not group_id or breadth is None:
                continue
            if not 0 <= breadth <= 100:
                continue
            points[(group_id, as_of)] = {
                "group_id": group_id,
                "as_of": as_of,
                "breadth": breadth,
                "group_excess_return_20d": _finite_number(
                    row.get("group_excess_return_20d")
                ),
            }

    counts: dict[str, int] = {}
    for point in points.values():
        counts[point["group_id"]] = counts.get(point["group_id"], 0) + 1
    return sorted(
        (
            point
            for point in points.values()
            if counts.get(point["group_id"], 0) >= 2
        ),
        key=lambda point: (point["group_id"], point["as_of"]),
    )


def export(
    snapshot_id: str,
    out_path: Path,
    *,
    snapshot_root: Path | None = None,
) -> dict[str, Any]:
    reader = SnapshotReader(root=snapshot_root)
    snap = reader.load(snapshot_id)
    manifest_entries = (snap.get("manifest") or {}).get("entries") or []
    entry = manifest_entries[0] if manifest_entries else {}
    as_of = entry.get("as_of")
    # The pipeline only selects a previous snapshot when provider mode,
    # methodology versions, and chronology are compatible. Mirror that
    # decision here instead of treating the directory's previous entry as a
    # valid transition baseline.
    previous_id = (snap.get("comparability") or {}).get("selected_previous")

    payload: dict[str, Any] = {
        "schema_version": "web-snapshot-v1",
        "snapshot_id": snapshot_id,
        "as_of": as_of,
        "previous_snapshot_id": previous_id,
        "manifest": snap.get("manifest"),
        "quality": snap.get("quality"),
        "coverage": snap.get("coverage"),
        "data_warnings": snap.get("data_warnings"),
        "provider_provenance": snap.get("provider_provenance"),
        "methodology_sensitivity": snap.get("methodology_sensitivity"),
        "tavily_context": snap.get("tavily_context"),
        "you_context": snap.get("you_context"),
        "api_credit_audit": snap.get("api_credit_audit"),
        "security_master_diagnostics": snap.get("security_master_diagnostics"),
        "history_diagnostics": snap.get("history_diagnostics"),
        "endpoints": snap.get("endpoints"),
        "comparability": snap.get("comparability"),
        "groups": _records(snap["groups"]),
        "transitions": _records(snap["transitions"]),
        "features": _records(snap["features"]),
        "constituents": [],  # snapshot writer does not yet emit per-group constituents
        "breadth_history": _build_breadth_history(reader, snapshot_id, snap),
        "security_master": snap.get("security_master"),
        "change_digest": snap.get("change_digest"),
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write_text(
        out_path,
        json.dumps(payload, indent=2, default=str),
    )
    return {
        "snapshot_id": snapshot_id,
        "out_path": str(out_path),
        "groups": len(payload["groups"]),
        "transitions": len(payload["transitions"]),
        "features": len(payload["features"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser(prog="export_snapshot_json")
    parser.add_argument("--snapshot-id", default=None, help="Snapshot id (e.g. snap_2026-08-20).")
    parser.add_argument("--latest", action="store_true", help="Use the latest snapshot.")
    parser.add_argument("--out", default=None, help="Override output path.")
    parser.add_argument(
        "--snapshot-root",
        default=None,
        help="Read snapshots from an alternate root (useful for isolated harnesses).",
    )
    args = parser.parse_args()

    if not args.snapshot_id and not args.latest:
        args.latest = True
    reader = SnapshotReader(root=Path(args.snapshot_root) if args.snapshot_root else None)
    if args.latest:
        snaps = sorted(
            reader.list_snapshots(),
            key=lambda path: (_snapshot_as_of(reader, path), path.name),
        )
        if not snaps:
            print("no snapshots found", file=__import__("sys").stderr)
            return 1
        sid = snaps[-1].name
    else:
        sid = args.snapshot_id
    out_path = Path(args.out) if args.out else PUBLIC_DIR / f"{sid}.json"
    info = export(
        sid,
        out_path,
        snapshot_root=Path(args.snapshot_root) if args.snapshot_root else None,
    )
    print(json.dumps(info, indent=2))
    return 0


def _snapshot_as_of(reader: SnapshotReader, snapshot_dir: Path) -> str:
    """Return the snapshot's calendar date for chronological selection."""
    snap = reader.load(snapshot_dir.name)
    entries = (snap.get("manifest") or {}).get("entries") or []
    entry = entries[0] if entries else {}
    return str(entry.get("as_of") or entry.get("snapshot_date") or "")


def _atomic_write_text(path: Path, value: str) -> None:
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmp:
            tmp.write(value)
            tmp.flush()
            os.fsync(tmp.fileno())
        Path(tmp_name).replace(path)
    finally:
        try:
            Path(tmp_name).unlink()
        except FileNotFoundError:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
