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
import sys
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
    parser.add_argument(
        "--ids",
        nargs="+",
        default=None,
        metavar="SNAPSHOT_ID",
        help=(
            "Curated allowlist of snapshot ids (overrides the provider-mode "
            "filter). Each id must have an exported payload and pass "
            "payload/manifest parity checks. Use this to pin the historical "
            "evidence snapshot together with the latest validated snapshot."
        ),
    )
    parser.add_argument(
        "--snapshots-root",
        default=None,
        help=(
            "Override the snapshot directory root (default data/snapshots). "
            "Lets an isolated run curate an index from a specific snapshot tree."
        ),
    )
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

    requested_provider_mode = (
        "SECTORS_LIVE" if args.provider_mode == "LIVE — SECTORS" else args.provider_mode
    )

    reader = SnapshotReader(
        root=Path(args.snapshots_root) if args.snapshots_root else None
    )
    out_path = Path(args.out) if args.out else PUBLIC_DIR / "index.json"
    entries: list[dict[str, str | None]] = []
    rejected: dict[str, str] = {}
    snap_dirs = sorted(reader.list_snapshots(), key=lambda p: p.name)
    if args.ids:
        wanted = set(args.ids)
        snap_dirs = [p for p in snap_dirs if p.name in wanted]
        missing = wanted - {p.name for p in snap_dirs}
        if missing:
            print(f"ERROR: unknown snapshot ids: {sorted(missing)}", file=sys.stderr)
            return 2
    for snap_dir in snap_dirs:
        # Only advertise payloads that the SPA can actually fetch. This keeps
        # the index safe when an operator exports one snapshot from a larger
        # on-disk history.
        payload_path = out_path.parent / f"{snap_dir.name}.json"
        if not payload_path.exists():
            rejected[snap_dir.name] = f"no exported payload at {payload_path.name}"
            continue
        manifest_path = snap_dir / "manifest.json"
        if not manifest_path.exists():
            rejected[snap_dir.name] = "snapshot directory has no manifest.json"
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            payload = json.loads(payload_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            rejected[snap_dir.name] = f"unreadable manifest or payload: {exc}"
            continue
        manifest_entries = manifest.get("entries") or []
        payload_manifest_entries = (payload.get("manifest") or {}).get("entries") or []
        if not manifest_entries or not payload_manifest_entries:
            rejected[snap_dir.name] = "manifest or payload has no entries"
            continue
        first = manifest_entries[0]
        payload_entry = payload_manifest_entries[0]
        # Do not let an index point at a stale or mismatched JSON export.
        if payload.get("snapshot_id") != snap_dir.name:
            rejected[snap_dir.name] = (
                f"payload snapshot_id={payload.get('snapshot_id')!r} does not match "
                f"directory {snap_dir.name!r}"
            )
            continue
        if payload_entry.get("snapshot_id") != first.get("snapshot_id"):
            rejected[snap_dir.name] = "payload manifest entry id differs from snapshot manifest"
            continue
        if payload.get("as_of") != first.get("as_of"):
            rejected[snap_dir.name] = (
                f"payload as_of={payload.get('as_of')!r} differs from snapshot manifest "
                f"as_of={first.get('as_of')!r}"
            )
            continue
        mode = (
            payload_entry.get("provider_mode")
            or first.get("provider_mode")
            or manifest.get("provider_mode")
        )
        if not args.include_all and not args.ids and mode != requested_provider_mode:
            continue
        entries.append(
            {
                "snapshot_id": snap_dir.name,
                "as_of": first.get("as_of"),
                "provider": first.get("provider"),
                "provider_mode": mode,
            }
        )

    # An explicitly requested snapshot must appear in the published index. If
    # any requested id was dropped (missing export, unreadable file, identity
    # mismatch), stop before replacing the index: silently publishing a subset
    # would hide the omission and downgrade the active bundle.
    if args.ids:
        requested_but_rejected = sorted(set(args.ids) & set(rejected))
        if requested_but_rejected:
            for snapshot_id in requested_but_rejected:
                print(
                    f"ERROR: requested snapshot {snapshot_id} was rejected: "
                    f"{rejected[snapshot_id]}",
                    file=sys.stderr,
                )
            print(
                "ERROR: refusing to write index.json with a missing requested entry",
                file=sys.stderr,
            )
            return 2

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
