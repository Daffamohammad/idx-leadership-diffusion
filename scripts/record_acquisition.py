"""Append a hash-bound record when a source file is captured or imported."""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil

from idx_leadership.utils import project_root


INVENTORY_SCHEMA = "idx-acquisition-inventory-v1"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _strict_date(value: str | None, label: str) -> str | None:
    if value is None:
        return None
    parsed = date.fromisoformat(value)
    if parsed.isoformat() != value:
        raise ValueError(f"{label} must use YYYY-MM-DD")
    return value


def _preserve_capture(source_path: Path, destination_dir: Path) -> Path:
    """Copy captured bytes to a new versioned path with exclusive creation."""
    destination_dir.mkdir(parents=True, exist_ok=False)
    suffix = source_path.suffix.lower() if source_path.suffix else ".bin"
    destination = destination_dir / f"capture{suffix}"
    with source_path.open("rb") as incoming, destination.open("xb") as saved:
        shutil.copyfileobj(incoming, saved)
        saved.flush()
        os.fsync(saved.fileno())
    if _sha256(source_path) != _sha256(destination) or source_path.stat().st_size != destination.stat().st_size:
        raise ValueError("versioned capture copy failed byte verification")
    return destination


def append_acquisition(record: dict, inventory_path: Path) -> None:
    inventory_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = inventory_path.with_suffix(inventory_path.suffix + ".lock")
    descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        if inventory_path.exists():
            for line_number, line in enumerate(inventory_path.read_text(encoding="utf-8").splitlines(), 1):
                try:
                    existing = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"acquisition inventory line {line_number} is invalid JSON") from exc
                if existing.get("acquisition_id") == record["acquisition_id"]:
                    raise ValueError(f"acquisition ID already exists: {record['acquisition_id']}")
        encoded = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
        append_descriptor = os.open(inventory_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
        try:
            with os.fdopen(append_descriptor, "a", encoding="utf-8", closefd=False) as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
        finally:
            os.close(append_descriptor)
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--acquisition-id", required=True)
    parser.add_argument("--file", required=True, type=Path)
    parser.add_argument("--publisher", required=True)
    parser.add_argument("--url")
    parser.add_argument("--observation-start", required=True)
    parser.add_argument("--observation-end", required=True)
    parser.add_argument("--publication-date")
    parser.add_argument("--publication-evidence")
    parser.add_argument("--derivation-contract")
    parser.add_argument("--derivation-input", action="append", default=[], metavar="ID=SHA256")
    parser.add_argument("--inventory", type=Path, default=None)
    args = parser.parse_args()
    try:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", args.acquisition_id):
            raise ValueError("acquisition ID must be a stable filename-safe identifier")
        observation_start = _strict_date(args.observation_start, "observation start")
        observation_end = _strict_date(args.observation_end, "observation end")
        publication_date = _strict_date(args.publication_date, "publication date")
        if observation_start > observation_end:
            raise ValueError("observation start must not follow observation end")
        if bool(publication_date) != bool(args.publication_evidence):
            raise ValueError("publication date and evidence must be supplied together")
        if args.url and not args.url.startswith(("https://", "http://")):
            raise ValueError("source URL must use HTTP or HTTPS")

        root = project_root().resolve()
        source_path = args.file.resolve(strict=True)
        if not source_path.is_file():
            raise ValueError("captured source must be a regular file")
        inventory = (args.inventory or root / "data" / "research" / "acquisitions" / "inventory.jsonl").resolve()
        if not inventory.is_relative_to(root):
            raise ValueError("acquisition inventory must stay inside the project root")
        capture_root = root / "data" / "raw" / "acquisitions"
        cursor = root
        for part in ("data", "raw", "acquisitions"):
            cursor = cursor / part
            if cursor.is_symlink():
                raise ValueError("versioned acquisition path may not contain a symlink")
        destination_dir = capture_root / args.acquisition_id
        destination = _preserve_capture(source_path, destination_dir)
        relative_path = destination.relative_to(root).as_posix()
        retrieved_at = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        captured_on = retrieved_at[:10]
        available_on = publication_date or captured_on
        record = {
            "schema_version": INVENTORY_SCHEMA,
            "acquisition_id": args.acquisition_id,
            "publisher": args.publisher,
            "source_url": args.url,
            "observation_start": observation_start,
            "observation_end": observation_end,
            "retrieved_at": retrieved_at,
            "publication_date": publication_date,
            "publication_evidence": args.publication_evidence,
            "availability_basis": "published_on" if publication_date else "capture_upper_bound",
            "available_on": available_on,
            "captured_file": {
                "path": relative_path,
                "sha256": _sha256(source_path),
                "bytes": source_path.stat().st_size,
                "hash_scope": "captured_file_bytes",
                "original_file_name": source_path.name,
            },
            "derivation": {
                "contract": args.derivation_contract,
                "inputs": [],
            },
        }
        for item in args.derivation_input:
            source_id, separator, digest = item.partition("=")
            if not separator or not source_id or not re.fullmatch(r"[0-9a-f]{64}", digest):
                raise ValueError("derivation inputs must use ID=lowercase-SHA256")
            record["derivation"]["inputs"].append({"source_id": source_id, "sha256": digest})
        record["derivation"]["inputs"].sort(key=lambda item: item["source_id"])
        if len({item["source_id"] for item in record["derivation"]["inputs"]}) != len(record["derivation"]["inputs"]):
            raise ValueError("derivation input source IDs must be unique")
        append_acquisition(record, inventory)
        print(json.dumps({"acquisition_id": args.acquisition_id, "sha256": record["captured_file"]["sha256"],
                          "bytes": record["captured_file"]["bytes"], "retrieved_at": retrieved_at,
                          "available_on": available_on, "inventory": inventory.as_posix()}))
        return 0
    except (OSError, ValueError) as exc:
        parser.exit(1, f"ACQUISITION_NOT_RECORDED: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
