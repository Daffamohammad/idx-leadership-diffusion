"""Tests for snapshot and manifest integrity."""
from __future__ import annotations

import json
import shutil
import tempfile
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from idx_leadership.data.manifests import read_manifest, write_manifest
from idx_leadership.data.snapshots import SnapshotReader, SnapshotWriter
from idx_leadership.data.quality import assess_quality
from idx_leadership.models import (
    DataQualityStatus,
    GroupSnapshot,
    ProviderName,
    ConcentrationMetrics,
    LeadershipState,
    DiffusionState,
)


@pytest.fixture()
def tmp_snap_root():
    d = Path(tempfile.mkdtemp())
    yield d
    shutil.rmtree(d, ignore_errors=True)


def _write_minimal_snapshot(root: Path, snapshot_id: str, as_of: date) -> Path:
    prices = pd.DataFrame(
        {
            "ticker": ["A", "B"],
            "date": [as_of, as_of],
            "close": [100.0, 200.0],
            "adjusted_close": [100.0, 200.0],
            "volume": [1000, 2000],
            "market_cap": [None, None],
            "currency": ["IDR", "IDR"],
            "price_basis": ["adjusted_close", "adjusted_close"],
            "source": ["fixture", "fixture"],
        }
    )
    benchmark = pd.DataFrame(
        {
            "benchmark_id": ["IHSG"],
            "date": [as_of],
            "close": [1000.0],
            "price_basis": ["close"],
            "source": ["fixture"],
        }
    )
    features = pd.DataFrame({"ticker": ["A", "B"], "return_20d": [5.0, 10.0]})
    groups = pd.DataFrame(
        {
            "snapshot_date": [as_of],
            "group_id": ["X"],
            "leadership_state": ["LEADING"],
            "diffusion_state": ["BROADENING"],
            "group_excess_return": [3.0],
            "breadth_outperforming": [80.0],
        }
    )
    transitions = pd.DataFrame({"group_id": ["X"], "current_date": [as_of]})
    writer = SnapshotWriter(root=root)
    target = writer.write(
        snapshot_id=snapshot_id,
        as_of=as_of,
        provider=ProviderName.YFINANCE,
        universe_version="prototype-v1",
        taxonomy_version="prototype-v1",
        method_version="methodology-v1",
        feature_version="features-v1",
        coverage_status=DataQualityStatus.READY,
        coverage_pct=100.0,
        prices=prices,
        benchmark=benchmark,
        security_master=[],
        features=features,
        groups=groups,
        transitions=transitions,
    )
    return target


def test_write_and_read_snapshot(tmp_snap_root):
    as_of = date(2026, 8, 20)
    _write_minimal_snapshot(tmp_snap_root, "snap_test", as_of)
    reader = SnapshotReader(root=tmp_snap_root)
    assert len(reader.list_snapshots()) == 1
    loaded = reader.load("snap_test")
    assert not loaded["prices"].empty
    assert not loaded["benchmark"].empty
    assert not loaded["features"].empty
    assert not loaded["groups"].empty


def test_aggregate_manifest_orders_by_date(tmp_snap_root):
    _write_minimal_snapshot(tmp_snap_root, "snap_2026-08-13", date(2026, 8, 13))
    _write_minimal_snapshot(tmp_snap_root, "snap_2026-08-20", date(2026, 8, 20))
    reader = SnapshotReader(root=tmp_snap_root)
    m = reader.aggregate_manifest()
    assert m.snapshot_count == 2
    assert m.first_date == date(2026, 8, 13)
    assert m.latest_date == date(2026, 8, 20)


def test_manifest_round_trip(tmp_snap_root):
    m = reader_manifest_fixture(tmp_snap_root)
    write_manifest(m, tmp_snap_root / "manifest.json")
    again = read_manifest(tmp_snap_root / "manifest.json")
    assert again.snapshot_count == m.snapshot_count


def reader_manifest_fixture(root: Path):
    from idx_leadership.models import SnapshotManifest, ManifestEntry
    return SnapshotManifest(
        snapshot_count=1,
        first_date=date(2026, 8, 20),
        latest_date=date(2026, 8, 20),
        provider=ProviderName.YFINANCE,
        universe_version="prototype-v1",
        taxonomy_version="prototype-v1",
        method_version="methodology-v1",
        feature_version="features-v1",
        entries=[
            ManifestEntry(
                snapshot_id="snap_2026-08-20",
                snapshot_date=date(2026, 8, 20),
                as_of=date(2026, 8, 20),
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
        notes=[],
    )


def test_assess_quality_ready(prices_df, benchmark_df):
    r = assess_quality(
        requested_tickers=["BBCA.JK", "BBRI.JK", "BMRI.JK", "BBNI.JK"],
        prices=prices_df,
        benchmark=benchmark_df,
        today=date(2026, 8, 20),
    )
    assert r.status in (DataQualityStatus.READY, DataQualityStatus.READY_WITH_GAPS)


def test_assess_quality_failed_when_no_data():
    prices = pd.DataFrame(columns=["ticker", "date", "close", "adjusted_close"])
    benchmark = pd.DataFrame(columns=["benchmark_id", "date", "close"])
    r = assess_quality(
        requested_tickers=["X"],
        prices=prices,
        benchmark=benchmark,
        today=date(2026, 8, 20),
    )
    assert r.status == DataQualityStatus.FAILED


def test_assess_quality_detects_duplicates(prices_df, benchmark_df):
    # Add a duplicate row
    extra = prices_df.head(2).copy()
    dup_prices = pd.concat([prices_df, extra], ignore_index=True)
    r = assess_quality(
        requested_tickers=["BBCA.JK"],
        prices=dup_prices,
        benchmark=benchmark_df,
        today=date(2026, 8, 20),
    )
    assert r.duplicate_ticker_date_rows > 0
