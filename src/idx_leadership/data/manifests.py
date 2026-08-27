"""Manifest helpers — separate from snapshot writer for clarity."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..models import ManifestEntry, ProviderName, SnapshotManifest
from ..utils import data_root


def write_manifest(manifest: SnapshotManifest, path: Path | None = None) -> Path:
    """Persist an aggregated manifest under data/snapshots/manifest.json."""
    p = path or (data_root() / "snapshots" / "manifest.json")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    return p


def read_manifest(path: Path | None = None) -> SnapshotManifest:
    p = path or (data_root() / "snapshots" / "manifest.json")
    if not p.exists():
        return SnapshotManifest(
            snapshot_count=0,
            first_date=None,
            latest_date=None,
            provider=ProviderName.YFINANCE,
            universe_version="prototype-v1",
            taxonomy_version="prototype-v1",
            method_version="methodology-v1",
            feature_version="features-v1",
            entries=[],
            notes=["no manifest yet"],
        )
    data = json.loads(p.read_text(encoding="utf-8"))
    return SnapshotManifest(**data)
