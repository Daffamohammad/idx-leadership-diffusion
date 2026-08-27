"""End-to-end pipeline smoke test using the fixture provider."""
from __future__ import annotations

import tempfile
import shutil
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from idx_leadership.pipeline import build_snapshot
from idx_leadership.providers.fixture import FixtureProvider


@pytest.fixture()
def tmp_root():
    d = Path(tempfile.mkdtemp())
    yield d
    shutil.rmtree(d, ignore_errors=True)


def test_build_snapshot_full(tmp_root):
    provider = FixtureProvider(fixtures_dir=Path("tests/fixtures"))
    res = build_snapshot(provider, as_of=date(2026, 8, 20), out_dir=tmp_root, snapshot_id="snap_2026-08-20")
    assert "groups" in res
    assert "transitions" in res
    assert "change_digest" in res
    assert "quality" in res
    # The snapshot directory was created
    snap_dir = tmp_root / "snap_2026-08-20"
    assert snap_dir.exists()
    assert (snap_dir / "manifest.json").exists()
    assert (snap_dir / "change_digest.json").exists()
    assert (snap_dir / "quality.json").exists()
    assert (snap_dir / "groups.parquet").exists()
    groups = pd.read_parquet(snap_dir / "groups.parquet")
    assert set(groups["method_version"]) == {"methodology-v3"}
    assert set(groups["feature_version"]) == {"features-v3"}
    assert set(groups["convention"]) == {"absolute_move_v2"}
    # Quality must have a status
    assert res["quality"]["status"] in {"READY", "READY_WITH_GAPS"}


def test_build_snapshot_writes_history_and_manifest(tmp_root):
    provider = FixtureProvider(fixtures_dir=Path("tests/fixtures"))
    build_snapshot(provider, as_of=date(2026, 8, 13), out_dir=tmp_root, snapshot_id="snap_2026-08-13")
    build_snapshot(provider, as_of=date(2026, 8, 20), out_dir=tmp_root, snapshot_id="snap_2026-08-20")
    manifest = tmp_root / "manifest.json"
    assert manifest.exists()
    import json
    m = json.loads(manifest.read_text())
    assert m["snapshot_count"] == 2
    assert m["first_date"] == "2026-08-13"
    assert m["latest_date"] == "2026-08-20"


def test_build_snapshot_does_not_mutate_default_manifest(tmp_root):
    """An export rooted at ``out_dir`` must not rewrite the project artifact."""
    default_manifest = Path("data/snapshots/manifest.json")
    before = default_manifest.read_bytes() if default_manifest.exists() else None

    provider = FixtureProvider(fixtures_dir=Path("tests/fixtures"))
    build_snapshot(
        provider,
        as_of=date(2026, 8, 20),
        out_dir=tmp_root,
        snapshot_id="snap_isolated",
    )

    after = default_manifest.read_bytes() if default_manifest.exists() else None
    assert after == before
    assert (tmp_root / "manifest.json").exists()
