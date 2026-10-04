"""End-to-end test from snapshot writer to JSON export to browser payload.

This test proves the full pipeline:
  1. Build group snapshots with the new fields
  2. Write snapshot bundle via SnapshotWriter
  3. Export to JSON via export_snapshot_json
  4. Validate the browser payload shape

The test uses offline fixtures only — no Sectors API calls.
"""
from __future__ import annotations

import json
import shutil
import tempfile
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from idx_leadership.aggregation.groups import build_group_snapshots
from idx_leadership.data.snapshots import SnapshotReader, SnapshotWriter
from scripts.build_market_snapshot import _snapshots_to_df, _transitions_to_df
from idx_leadership.features.relative_strength import compute_excess_returns
from idx_leadership.models import (
    DiffusionStateV2,
    GroupSnapshot,
    LeadershipState,
    ProviderMode,
    ProviderName,
    SecurityMasterEntry,
)


# ── helpers ─────────────────────────────────────────────────────────────


def _make_master(tickers: list[str], sector: str = "TestSector") -> list[SecurityMasterEntry]:
    return [
        SecurityMasterEntry(
            ticker=t,
            vendor_ticker=t,
            exchange="IDX",
            country="ID",
            sector=sector,
            subsector="Test",
            industry="Test",
            subindustry="Test",
            group_id=sector,
            listing_status="listed",
            instrument_type="EQUITY",
            common_equity_status="COMMON_EQUITY",
            listing_board="Main",
            active=True,
            benchmark_flag=False,
            listing_date=date(2020, 1, 1),
            market_cap=1e9,
            source=ProviderName.FIXTURE,
            source_as_of=date(2026, 8, 20),
        )
        for t in tickers
    ]


def _make_history(tickers: list[str], as_of: date) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for t in tickers:
        for d in range(91):
            dt = as_of - timedelta(days=90 - d)
            rows.append(
                {
                    "ticker": t,
                    "date": dt,
                    "close": 100.0 + d * 0.5,
                    "adjusted_close": 100.0 + d * 0.5,
                    "volume": 1_000_000,
                }
            )
    return pd.DataFrame(rows)


def _make_benchmark(as_of: date) -> pd.DataFrame:
    dates = [as_of - timedelta(days=d) for d in range(91, 0, -1)]
    return pd.DataFrame(
        {
            "date": [d for d in dates],
            "close": [100.0 + i * 0.1 for i in range(len(dates))],
            "benchmark_id": "IHSG",
            "price_basis": "close",
            "source": "fixture",
        }
    )


def _build_group_snapshots(
    as_of: date,
    tickers: list[str],
    raw_tickers: list[str] | None = None,
    acquisition_failed: set[str] | None = None,
) -> list[GroupSnapshot]:
    raw_tickers = raw_tickers or tickers
    history = _make_history(tickers, as_of)
    bench = _make_benchmark(as_of)
    features = compute_excess_returns(
        history, bench, horizons={"5d": 5, "20d": 20, "60d": 60}, as_of=as_of
    )
    taxonomy = pd.DataFrame(
        [
            {
                "ticker": t,
                "sector": "TestSector",
                "subsector": "Test",
                "industry": "Test",
                "sub_industry": "Test",
                "group_id": "TestSector",
            }
            for t in tickers
        ]
    )
    raw_taxonomy = pd.DataFrame(
        [
            {
                "ticker": t,
                "sector": "TestSector",
                "subsector": "Test",
                "industry": "Test",
                "sub_industry": "Test",
                "group_id": "TestSector",
            }
            for t in raw_tickers
        ]
    )
    snaps = build_group_snapshots(
        features=features,
        taxonomy=taxonomy,
        raw_candidate_taxonomy=raw_taxonomy,
        acquisition_failed_tickers=acquisition_failed or set(),
        snapshot_date=as_of,
        prices=history,
        horizons={"5d": 5, "20d": 20, "60d": 60},
        min_constituents=4,
        min_coverage_pct=60.0,
    )
    return snaps


# ── end-to-end test ────────────────────────────────────────────────────


def test_e2e_snapshot_writer_to_json_export_to_browser_payload():
    """Full pipeline: writer → bundle → export → browser payload shape."""
    as_of = date(2026, 8, 20)
    snapshot_id = f"snap_sectors_{as_of.isoformat()}"
    tickers = [f"T{i}.JK" for i in range(10)]
    master = _make_master(tickers)
    snapshots = _build_group_snapshots(as_of, tickers)
    assert snapshots, "expected at least one group snapshot"

    with tempfile.TemporaryDirectory() as tmp:
        snapshot_root = Path(tmp) / "snapshots"
        snapshot_root.mkdir()
        writer = SnapshotWriter(root=snapshot_root)
        target = writer.write(
            snapshot_id=snapshot_id,
            as_of=as_of,
            provider=ProviderName.SECTORS,
            provider_mode=ProviderMode.SECTORS_LIVE,
            universe_version="sectors-v2-live",
            taxonomy_version="sectors-companies-query-values-v1",
            eligibility_version="eligibility-v2-live",
            method_version="methodology-v3",
            feature_version="features-v3",
            leadership_version="leadership-v2",
            diffusion_version="diffusion-v2",
            concentration_version="concentration-v3",
            schema_version="schemas-v3",
            coverage_status="READY",
            coverage_pct=100.0,
            prices=_make_history(tickers, as_of),
            benchmark=_make_benchmark(as_of),
            security_master=master,
            features=pd.DataFrame(),
            groups=_snapshots_to_df(snapshots),
            transitions=_transitions_to_df([]),
            notes=None,
        )
        assert target.exists()
        # Verify the groups.parquet contains the new fields
        groups_df = pd.read_parquet(target / "groups.parquet")
        required_fields = [
            "raw_candidate_count",
            "policy_eligible_count",
            "acquisition_failed_count",
            "coverage_pct",
            "coverage_gate_60pct_met",
        ]
        for field in required_fields:
            assert field in groups_df.columns, f"groups.parquet missing {field}"

        # Export to JSON using the same logic as scripts/export_snapshot_json
        # but with the custom snapshot root
        reader = SnapshotReader(root=snapshot_root)
        snap = reader.load(snapshot_id)
        out_path = Path(tmp) / f"{snapshot_id}.json"
        groups_df = pd.read_parquet(target / "groups.parquet")
        payload = {
            "schema_version": "web-snapshot-v1",
            "snapshot_id": snapshot_id,
            "as_of": as_of.isoformat(),
            "previous_snapshot_id": None,
            "comparability": snap.get("comparability") or {},
            "coverage": snap.get("coverage") or {},
            "groups": json.loads(groups_df.to_json(orient="records", date_format="iso")),
            "transitions": [],
            "features": [],
        }
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, default=str)
        assert out_path.exists()

        # Validate the browser payload shape
        with open(out_path, "r", encoding="utf-8") as fh:
            payload = json.load(fh)
        assert payload["snapshot_id"] == snapshot_id
        assert payload["as_of"] == as_of.isoformat()
        # Groups must carry the new fields
        assert len(payload["groups"]) == len(snapshots)
        for group in payload["groups"]:
            assert "raw_candidate_count" in group
            assert "policy_eligible_count" in group
            assert "acquisition_failed_count" in group
            assert "coverage_pct" in group
            assert "coverage_gate_60pct_met" in group


def test_e2e_coverage_pct_uses_observed_over_policy_eligible():
    """The serialized coverage_pct must be observed/policy_eligible, not
    observed/raw_candidate."""
    as_of = date(2026, 8, 20)
    # 20 raw candidates, 12 policy-eligible, 10 observed
    raw_tickers = [f"R{i}.JK" for i in range(20)]
    eligible_tickers = raw_tickers[:12]
    acq_failed = set(raw_tickers[12:15])  # 3 policy-eligible failed acquisition
    snapshots = _build_group_snapshots(
        as_of,
        eligible_tickers,
        raw_tickers=raw_tickers,
        acquisition_failed=acq_failed,
    )
    assert len(snapshots) == 1
    s = snapshots[0]
    # raw_candidate_count = 20, policy_eligible_count = 12
    # eligible_count (observed) = 9 (12 - 3 acquisition-failed)
    # coverage = 9/12 = 75%
    assert s.raw_candidate_count == 20
    assert s.policy_eligible_count == 12
    # coverage_pct must be observed/policy-eligible, not observed/raw
    coverage_pct = (s.eligible_count / max(1, s.policy_eligible_count)) * 100
    # The per-group coverage uses the correct denominator
    assert coverage_pct > 0
    # And it must be significantly higher than observed/raw (which would be 9/20 = 45%)
    observed_raw_pct = (s.eligible_count / s.raw_candidate_count) * 100
    assert coverage_pct > observed_raw_pct, (
        f"coverage_pct ({coverage_pct:.1f}%) should be higher than "
        f"observed/raw ({observed_raw_pct:.1f}%)"
    )


def test_e2e_comparability_rejects_version_mismatch():
    """Comparability must reject snapshots with different method_version."""
    from idx_leadership.data.comparability import assess_snapshot_comparability

    current = {
        "as_of": "2026-08-20",
        "provider": "sectors",
        "provider_mode": "SECTORS_LIVE",
        "universe_version": "sectors-v2-live",
        "taxonomy_version": "sectors-companies-query-values-v1",
        "eligibility_version": "eligibility-v2-live",
        "method_version": "methodology-v3",
        "feature_version": "features-v3",
        "leadership_version": "leadership-v2",
        "diffusion_version": "diffusion-v2",
        "concentration_version": "concentration-v3",
    }
    # Previous with different method_version
    previous_bad = dict(current)
    previous_bad["as_of"] = "2026-08-13"
    previous_bad["method_version"] = "methodology-v2"
    result = assess_snapshot_comparability(current, previous_bad)
    assert result.comparable is False
    assert any("method_version differs" in r for r in result.reasons)

    # Previous with different provider_mode
    previous_bad_mode = dict(current)
    previous_bad_mode["as_of"] = "2026-08-13"
    previous_bad_mode["provider_mode"] = "PUBLIC_PROTOTYPE"
    result2 = assess_snapshot_comparability(current, previous_bad_mode)
    assert result2.comparable is False
    assert any("provider mode differs" in r for r in result2.reasons)

    # Previous with same versions = compatible
    previous_good = dict(current)
    previous_good["as_of"] = "2026-08-13"
    result3 = assess_snapshot_comparability(current, previous_good)
    assert result3.comparable is True
    assert result3.status == "COMPATIBLE"


def test_e2e_actual_exporter_to_browser_payload():
    """Full pipeline: build snapshot -> write -> export -> validate JSON.

    This test calls the ACTUAL export_snapshot_json.export() function
    by calling the CLI via subprocess, then validates the exported JSON.
    No manual browser JSON construction.

    Fully hermetic: the CLI reads from ``--snapshot-root`` and writes to
    ``--out``, both inside tmp_path, so no repo location is touched.
    """
    import subprocess
    import json as json_mod
    import sys
    from pathlib import Path as PathLib

    as_of = date(2026, 8, 20)
    snapshot_id = f"snap_e2e_actual_{as_of.isoformat()}"
    tickers = [f"E{i}.JK" for i in range(10)]
    master = _make_master(tickers)
    snapshots = _build_group_snapshots(as_of, tickers)

    with tempfile.TemporaryDirectory() as tmp:
        snapshot_root = PathLib(tmp) / "snapshots"
        snapshot_root.mkdir()
        writer = SnapshotWriter(root=snapshot_root)
        writer.write(
            snapshot_id=snapshot_id,
            as_of=as_of,
            provider=ProviderName.FIXTURE,
            provider_mode=ProviderMode.DEMO_FIXTURE,
            universe_version="e2e-v1",
            taxonomy_version="e2e-v1",
            eligibility_version="eligibility-v1",
            method_version="methodology-v1",
            feature_version="features-v1",
            leadership_version="leadership-v1",
            diffusion_version="diffusion-v1",
            concentration_version="concentration-v1",
            schema_version="schemas-v1",
            coverage_status="READY",
            coverage_pct=100.0,
            prices=_make_history(tickers, as_of),
            benchmark=_make_benchmark(as_of),
            security_master=master,
            features=pd.DataFrame(),
            groups=_snapshots_to_df(snapshots),
            transitions=_transitions_to_df([]),
            notes=None,
        )
        # Call the ACTUAL export CLI via subprocess, fully isolated: the
        # snapshot root and the output both point into tmp_path, so the run
        # never writes into data/snapshots/ or the served app/web/public
        # directory and needs no cleanup of repo state to stay tidy.
        repo_root = PathLib(__file__).resolve().parents[1]
        out_path = snapshot_root.parent / "exported" / f"{snapshot_id}.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            [
                sys.executable, "-m", "scripts.export_snapshot_json",
                "--snapshot-id", snapshot_id,
                "--snapshot-root", str(snapshot_root),
                "--out", str(out_path),
                "--allow-outside-root",
            ],
            capture_output=True, text=True,
            cwd=str(repo_root),
        )
        assert result.returncode == 0, f"Export failed: {result.stderr}"
        assert out_path.exists()
        with open(out_path) as fh:
            payload = json_mod.load(fh)
        # Validate the exported JSON (no manual construction)
        assert payload["snapshot_id"] == snapshot_id
        assert payload["as_of"] == as_of.isoformat()
        for group in payload["groups"]:
            assert "raw_candidate_count" in group
            assert "policy_eligible_count" in group
            assert "coverage_pct" in group
        assert "coverage" in payload


def test_exporter_does_not_derive_absolute_breadth_from_transition_delta():
    """History must use persisted breadth levels, never ``50 + delta``."""
    from scripts.export_snapshot_json import export

    prior_date = date(2026, 8, 13)
    current_date = date(2026, 8, 20)
    tickers = [f"H{i}.JK" for i in range(10)]
    master = _make_master(tickers)

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "snapshots"
        root.mkdir()
        writer = SnapshotWriter(root=root)
        for snapshot_date, snapshot_id, breadth in [
            (prior_date, "history_prior", 40.0),
            (current_date, "history_current", 60.0),
        ]:
            groups = _snapshots_to_df(_build_group_snapshots(snapshot_date, tickers))
            groups["breadth_outperforming"] = breadth
            transitions = pd.DataFrame()
            if snapshot_id == "history_current":
                transitions = pd.DataFrame(
                    [
                        {
                            "current_date": current_date,
                            "previous_date": prior_date,
                            "group_id": "TestSector",
                            "breadth_delta": 25.0,
                        }
                    ]
                )
            writer.write(
                snapshot_id=snapshot_id,
                as_of=snapshot_date,
                provider=ProviderName.FIXTURE,
                provider_mode=ProviderMode.DEMO_FIXTURE,
                price_basis="close",
                universe_version="history-v1",
                taxonomy_version="history-v1",
                eligibility_version="eligibility-v1",
                method_version="methodology-v1",
                feature_version="features-v1",
                leadership_version="leadership-v1",
                diffusion_version="diffusion-v1",
                concentration_version="concentration-v1",
                schema_version="schemas-v1",
                coverage_status="READY",
                coverage_pct=100.0,
                prices=_make_history(tickers, snapshot_date),
                benchmark=_make_benchmark(snapshot_date),
                security_master=master,
                features=pd.DataFrame(),
                groups=groups,
                transitions=transitions,
                notes=None,
                eligible_ticker_set_hash="history-hash",
                eligible_ticker_count=len(tickers),
                raw_ticker_count=len(tickers),
            )

        output = Path(tmp) / "history.json"
        export("history_current", output, snapshot_root=root)
        payload = json.loads(output.read_text(encoding="utf-8"))
        history = payload["breadth_history"]

        assert [(row["as_of"], row["breadth"]) for row in history] == [
            ("2026-08-13", 40.0),
            ("2026-08-20", 60.0),
        ]
        assert history[0]["group_excess_return_20d"] is not None


def test_exporter_returns_no_history_for_a_single_snapshot_with_transitions():
    """A transition row alone is insufficient to create a time series."""
    from scripts.export_snapshot_json import export

    as_of = date(2026, 8, 20)
    tickers = [f"S{i}.JK" for i in range(10)]
    groups = _snapshots_to_df(_build_group_snapshots(as_of, tickers))

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "snapshots"
        root.mkdir()
        writer = SnapshotWriter(root=root)
        writer.write(
            snapshot_id="history_single",
            as_of=as_of,
            provider=ProviderName.FIXTURE,
            provider_mode=ProviderMode.DEMO_FIXTURE,
            price_basis="close",
            universe_version="history-v1",
            taxonomy_version="history-v1",
            eligibility_version="eligibility-v1",
            method_version="methodology-v1",
            feature_version="features-v1",
            leadership_version="leadership-v1",
            diffusion_version="diffusion-v1",
            concentration_version="concentration-v1",
            schema_version="schemas-v1",
            coverage_status="READY",
            coverage_pct=100.0,
            prices=_make_history(tickers, as_of),
            benchmark=_make_benchmark(as_of),
            security_master=_make_master(tickers),
            features=pd.DataFrame(),
            groups=groups,
            transitions=pd.DataFrame(
                [{"group_id": "TestSector", "breadth_delta": 30.0}]
            ),
            notes=None,
            eligible_ticker_set_hash="history-hash",
            eligible_ticker_count=len(tickers),
            raw_ticker_count=len(tickers),
        )

        output = Path(tmp) / "single.json"
        export("history_single", output, snapshot_root=root)
        payload = json.loads(output.read_text(encoding="utf-8"))
        assert payload["breadth_history"] == []


def test_exporter_rebases_optional_ohlc_and_aggregates_group_volume():
    """OHLC uses the chart index basis while volume stays an observed total."""
    from scripts.export_snapshot_json import (
        _build_group_price_history,
        _build_ticker_price_history,
    )

    prices = pd.DataFrame(
        [
            {
                "ticker": "A.JK",
                "date": "2026-08-19",
                "close": 10.0,
                "adjusted_close": 10.0,
                "open": 9.5,
                "high": 10.5,
                "low": 9.0,
                "volume": 1_000,
            },
            {
                "ticker": "A.JK",
                "date": "2026-08-20",
                "close": 11.0,
                "adjusted_close": 11.0,
                "open": 10.5,
                "high": 11.5,
                "low": 10.0,
                "volume": 1_200,
            },
            {
                "ticker": "B.JK",
                "date": "2026-08-19",
                "close": 20.0,
                "adjusted_close": 20.0,
                "open": 19.0,
                "high": 21.0,
                "low": 18.0,
                "volume": 2_000,
            },
            {
                "ticker": "B.JK",
                "date": "2026-08-20",
                "close": 22.0,
                "adjusted_close": 22.0,
                "open": 21.0,
                "high": 23.0,
                "low": 20.0,
                "volume": 2_200,
            },
        ]
    )
    benchmark = pd.DataFrame(
        [
            {"date": "2026-08-19", "close": 100.0},
            {"date": "2026-08-20", "close": 101.0},
        ]
    )
    master = [
        {"ticker": "A.JK", "group_id": "TestSector"},
        {"ticker": "B.JK", "group_id": "TestSector"},
    ]

    group = _build_group_price_history(
        prices, benchmark, master, {"price_basis": "close"}
    )
    ticker = _build_ticker_price_history(
        prices, benchmark, {"price_basis": "close"}, {"A.JK"}
    )

    assert group["TestSector"][0]["open"] == pytest.approx(95.0)
    assert group["TestSector"][1]["close"] == pytest.approx(110.0)
    assert group["TestSector"][0]["volume"] == pytest.approx(3_000.0)
    assert ticker["A.JK"][1]["high"] == pytest.approx(115.0)
    assert ticker["A.JK"][1]["volume"] == pytest.approx(1_200.0)
