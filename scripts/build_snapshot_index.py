"""Write app/web/public/snapshots/index.json listing the available snapshots.

The React UI calls /snapshots/index.json on first load to find the latest
snapshot id. Run this after `export_snapshot_json.py` whenever a new snapshot
lands.

CLI:
    python -m scripts.build_snapshot_index
    python -m scripts.build_snapshot_index --include-all
"""
from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path

from idx_leadership.data.snapshots import SnapshotReader
from idx_leadership.utils import project_root

PUBLIC_DIR = project_root() / "app" / "web" / "public" / "snapshots"


def main() -> int:
    parser = argparse.ArgumentParser(prog="build_snapshot_index")
    parser.add_argument(
        "--out", default=None, help="Override output path (default app/web/public/snapshots/index.json)"
    )
    parser.add_argument(
        "--provider-mode",
        default="SECTORS_LIVE",
        choices=("LIVE — SECTORS", "SECTORS_LIVE", "DEMO_FIXTURE", "PUBLIC_PROTOTYPE"),
        help="Advertise only snapshots with this provider mode (default: SECTORS_LIVE).",
    )
    parser.add_argument(
        "--include-all",
        action="store_true",
        help="Opt into a mixed-provider index; the browser otherwise defaults to live Sectors snapshots.",
    )
    args = parser.parse_args()
    requested_provider_mode = (
        "SECTORS_LIVE" if args.provider_mode == "LIVE — SECTORS" else args.provider_mode
    )

    reader = SnapshotReader()
    out_path = Path(args.out) if args.out else PUBLIC_DIR / "index.json"
    entries: list[dict[str, str | None]] = []
    for snap_dir in sorted(reader.list_snapshots(), key=lambda p: p.name):
        # Only advertise payloads that the SPA can actually fetch. This keeps
        # the index safe when an operator exports one snapshot from a larger
        # on-disk history.
        payload_path = out_path.parent / f"{snap_dir.name}.json"
        if not payload_path.exists():
            continue
        manifest_path = snap_dir / "manifest.json"
        if not manifest_path.exists():
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            payload = json.loads(payload_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        manifest_entries = manifest.get("entries") or []
        payload_manifest_entries = (payload.get("manifest") or {}).get("entries") or []
        if not manifest_entries or not payload_manifest_entries:
            continue
        first = manifest_entries[0]
        payload_entry = payload_manifest_entries[0]
        # Do not let an index point at a stale or mismatched JSON export.
        if payload.get("snapshot_id") != snap_dir.name:
            continue
        if payload_entry.get("snapshot_id") != first.get("snapshot_id"):
            continue
        if payload.get("as_of") != first.get("as_of"):
            continue
        mode = (
            payload_entry.get("provider_mode")
            or first.get("provider_mode")
            or manifest.get("provider_mode")
        )
        if not args.include_all and mode != requested_provider_mode:
            continue
        entries.append(
            {
                "snapshot_id": snap_dir.name,
                "as_of": first.get("as_of"),
                "provider": first.get("provider"),
                "provider_mode": mode,
            }
        )

    entries.sort(key=lambda item: (str(item.get("as_of") or ""), str(item["snapshot_id"])))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write_text(out_path, json.dumps(entries, indent=2))
    print(json.dumps({"out_path": str(out_path), "count": len(entries)}, indent=2))
    return 0


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
