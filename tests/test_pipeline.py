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


def test_build_snapshot_coverage_carries_pagination_defaults(tmp_root):
    from idx_leadership.pipeline import _build_pipeline_coverage
    from idx_leadership.models import ProviderMode
    from types import SimpleNamespace

    universe = pd.DataFrame(
        {
            "ticker": ["A", "B"],
            "eligible": [True, True],
            "acquisition_status": ["ACQUIRED", "ACQUIRED"],
            "sector": ["X", "Y"],
        }
    )
    quality = SimpleNamespace(
        requested_securities=2,
        loaded_securities=2,
        usable_securities=2,
        duplicate_ticker_date_rows=0,
        coverage_pct=100.0,
        benchmark_latest_date=None,
    )
    empty = pd.DataFrame()
    coverage = _build_pipeline_coverage(
        universe=universe,
        features=empty,
        prices=empty,
        benchmark=empty,
        quality=quality,
        as_of=date(2026, 8, 20),
        coverage_gate_pct=60.0,
        provider_mode=ProviderMode.DEMO_FIXTURE,
    )
    assert coverage["security_master_pagination_completeness"] is None
    assert coverage["close_pagination_completeness"] is None
    assert coverage["pagination_incomplete"] is False
    assert coverage["history_window_capped_90d"] is False

    capped = _build_pipeline_coverage(
        universe=universe,
        features=empty,
        prices=empty,
        benchmark=empty,
        quality=quality,
        as_of=date(2026, 8, 20),
        coverage_gate_pct=60.0,
        provider_mode=ProviderMode.SECTORS_LIVE,
        security_master_diagnostics={"pagination_completeness": "PARTIAL"},
        close_pagination_diagnostics={"pagination_completeness": "COMPLETE"},
        history_diagnostics={"window_capped_to_90_calendar_days": True},
    )
    assert capped["security_master_pagination_completeness"] == "PARTIAL"
    assert capped["close_pagination_completeness"] == "COMPLETE"
    assert capped["pagination_incomplete"] is True
    assert capped["history_window_capped_90d"] is True
    assert capped["history_window_capped_note"] is not None


def test_observation_lag_disclosure():
    from idx_leadership.pipeline import _observation_lag_days

    as_of = date(2026, 8, 20)
    prices = pd.DataFrame(
        {
            "ticker": ["FRESH.JK"] * 3 + ["STALE.JK"] * 3,
            "date": [
                date(2026, 8, 18), date(2026, 8, 19), date(2026, 8, 20),
                date(2026, 8, 13), date(2026, 8, 14), date(2026, 8, 15),
            ],
        }
    )
    benchmark = pd.DataFrame({"date": [date(2026, 8, 20)]})
    max_lag, n_lagging = _observation_lag_days(prices, benchmark)
    assert max_lag == 5
    assert n_lagging == 1
    assert _observation_lag_days(pd.DataFrame(), benchmark) == (None, 0)


def test_jakarta_session_state_classification():
    from datetime import datetime, timezone

    from idx_leadership.utils.dates import jakarta_session_state

    # Thursday 2026-08-20 06:00 UTC == 13:00 WIB -> OPEN
    assert (
        jakarta_session_state(datetime(2026, 8, 20, 6, 0, tzinfo=timezone.utc))
        == "OPEN"
    )
    # Saturday -> WEEKEND even at midday WIB
    assert (
        jakarta_session_state(datetime(2026, 8, 22, 6, 0, tzinfo=timezone.utc))
        == "WEEKEND"
    )
    # Thursday 13:00 UTC == 20:00 WIB -> CLOSED
    assert (
        jakarta_session_state(datetime(2026, 8, 20, 13, 0, tzinfo=timezone.utc))
        == "CLOSED"
    )


def test_explicit_as_of_never_marked_intraday(tmp_path):
    from idx_leadership.providers.fixture import FixtureProvider

    provider = FixtureProvider(fixtures_dir=Path("tests/fixtures"))
    res = build_snapshot(
        provider,
        as_of=date(2026, 8, 20),
        out_dir=tmp_path,
        snapshot_id="snap_intraday_check",
    )
    assert res["coverage"]["intraday_build"] is False
    assert not any(
        str(issue).startswith("intraday_build")
        for issue in res["quality"]["issues"]
    )


def test_build_snapshot_writes_complete_last(tmp_path):
    from idx_leadership.data.snapshots import SnapshotReader
    from idx_leadership.providers.fixture import FixtureProvider

    provider = FixtureProvider(fixtures_dir=Path("tests/fixtures"))
    build_snapshot(
        provider,
        as_of=date(2026, 8, 20),
        out_dir=tmp_path,
        snapshot_id="snap_done",
    )
    target = tmp_path / "snap_done"
    assert (target / "COMPLETE").exists()
    assert (target / "coverage.json").exists()
    assert (target / "evidence.json").exists()
    assert SnapshotReader(root=tmp_path).load("snap_done")["complete"] is True
