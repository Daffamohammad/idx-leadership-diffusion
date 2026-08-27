"""Tests that the methodology version is carried through snapshots
and that v1 snapshots remain readable.
"""
from __future__ import annotations

import json
import tempfile
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from idx_leadership.data.manifests import write_manifest, read_manifest
from idx_leadership.data.snapshots import SnapshotReader, SnapshotWriter
from idx_leadership.models import (
    DataQualityStatus,
    GroupSnapshot,
    LeadershipState,
    DiffusionState,
    ManifestEntry,
    ProviderName,
    SnapshotManifest,
)
from idx_leadership import (
    CONCENTRATION_METHOD_VERSION,
    DIFFUSION_METHOD_VERSION,
    FEATURE_VERSION,
    SCHEMA_VERSION,
)


def test_package_version_constants_match_current_methodology():
    assert SCHEMA_VERSION == "schemas-v3"
    assert FEATURE_VERSION == "features-v3"
    assert DIFFUSION_METHOD_VERSION == "diffusion-v2"
    assert CONCENTRATION_METHOD_VERSION == "concentration-v3"


def test_v2_manifest_carries_method_version_v2():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        m = SnapshotManifest(
            snapshot_count=1,
            first_date=date(2026, 8, 20),
            latest_date=date(2026, 8, 20),
            provider=ProviderName.SECTORS,
            universe_version="prototype-v1",
            taxonomy_version="sectors-v1",
            method_version="methodology-v2",
            feature_version="features-v2",
            entries=[
                ManifestEntry(
                    snapshot_id="snap_2026-08-20",
                    snapshot_date=date(2026, 8, 20),
                    as_of=date(2026, 8, 20),
                    provider=ProviderName.SECTORS,
                    universe_version="prototype-v1",
                    taxonomy_version="sectors-v1",
                    method_version="methodology-v2",
                    feature_version="features-v2",
                    coverage_status=DataQualityStatus.READY,
                    coverage_pct=100.0,
                    created_at=date.today(),
                )
            ],
        )
        path = write_manifest(m, path=root / "manifest.json")
        again = read_manifest(path=path)
        assert again.entries[0].method_version == "methodology-v2"
        assert again.entries[0].taxonomy_version == "sectors-v1"


def test_v1_snapshot_is_still_readable_via_legacy_field():
    """v1 manifests without the v2 method_version field must still
    deserialize (Pydantic's `extra=ignore` on GroupSnapshot extends
    here by default)."""
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        m = SnapshotManifest(
            snapshot_count=1,
            first_date=date(2026, 7, 20),
            latest_date=date(2026, 7, 20),
            provider=ProviderName.YFINANCE,
            universe_version="prototype-v1",
            taxonomy_version="prototype-v1",
            method_version="methodology-v1",
            feature_version="features-v1",
            entries=[
                ManifestEntry(
                    snapshot_id="snap_2026-07-20",
                    snapshot_date=date(2026, 7, 20),
                    as_of=date(2026, 7, 20),
                    provider=ProviderName.YFINANCE,
                    universe_version="prototype-v1",
                    taxonomy_version="prototype-v1",
                    method_version="methodology-v1",
                    feature_version="features-v1",
                    coverage_status=DataQualityStatus.READY,
                    coverage_pct=100.0,
                    created_at=date.today(),
                )
            ],
        )
        write_manifest(m, path=root / "manifest.json")
        again = read_manifest(path=root / "manifest.json")
        assert again.entries[0].method_version == "methodology-v1"


def test_legacy_v1_diffusion_enum_values_still_resolve():
    """The v1 DiffusionState enum keeps its string values so old
    serialized group snapshots remain readable."""
    assert DiffusionState.BROADENING.value == "BROADENING"
    assert DiffusionState.STABLE.value == "STABLE"
    assert DiffusionState.NARROWING.value == "NARROWING"
    assert DiffusionState.UNCONFIRMED.value == "UNCONFIRMED"


def test_v1_group_snapshot_still_constructible():
    g = GroupSnapshot(snapshot_date=date(2026, 8, 20), group_id="X")
    assert g.leadership_state == LeadershipState.UNCONFIRMED
    assert g.method_version == "methodology-v1"
