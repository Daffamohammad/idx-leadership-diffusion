"""Agent B — traversal tests: snapshot-id, ledger derived names, --out.

Valid ids pass; '../', absolute, empty and dot ids are rejected BEFORE any
filesystem access (assert no file is created outside the root). Ledger paths
derived from snapshot ids inherit the guard via validate_snapshot_id; the
ledger itself rejects empty/dot filenames. --out containment for the web
export lane requires --allow-outside-root. Zero live calls.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from idx_leadership.data.snapshots import (
    SnapshotReader,
    SnapshotWriter,
    validate_snapshot_id,
)
from idx_leadership.models import DataQualityStatus, ProviderName
from idx_leadership.providers.ledger import RequestLedger

BAD_IDS = ["../x", "..", ".", "a/b", "/abs", "", "a..b", "snap id", "snap;rm"]


@pytest.mark.parametrize("bad", BAD_IDS)
def test_validate_snapshot_id_rejects_escape_ids(bad):
    with pytest.raises(ValueError):
        validate_snapshot_id(bad)


def test_validate_snapshot_id_accepts_well_formed_ids():
    assert validate_snapshot_id("snap_2026-08-20") == "snap_2026-08-20"
    assert validate_snapshot_id("ok-id_123") == "ok-id_123"


def _minimal_frames(as_of):
    prices = pd.DataFrame(
        {
            "ticker": ["A"],
            "date": [as_of],
            "close": [100.0],
            "adjusted_close": [100.0],
            "volume": [1000],
            "market_cap": [None],
            "currency": ["IDR"],
            "price_basis": ["adjusted_close"],
            "source": ["fixture"],
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
    features = pd.DataFrame({"ticker": ["A"], "return_20d": [1.0]})
    groups = pd.DataFrame(
        {
            "snapshot_date": [as_of],
            "group_id": ["X"],
            "leadership_state": ["LEADING"],
            "diffusion_state": ["BROADENING"],
            "group_excess_return": [1.0],
            "breadth_outperforming": [80.0],
        }
    )
    transitions = pd.DataFrame({"group_id": ["X"], "current_date": [as_of]})
    return prices, benchmark, features, groups, transitions


@pytest.mark.parametrize("bad", BAD_IDS)
def test_snapshot_reader_load_rejects_before_fs_access(tmp_path, bad):
    reader = SnapshotReader(root=tmp_path / "snaps")
    before = set(tmp_path.rglob("*"))
    with pytest.raises(ValueError):
        reader.load(bad)
    assert set(tmp_path.rglob("*")) == before


@pytest.mark.parametrize("bad", BAD_IDS)
def test_snapshot_writer_rejects_before_fs_access(tmp_path, bad):
    as_of = date(2026, 8, 20)
    prices, benchmark, features, groups, transitions = _minimal_frames(as_of)
    writer = SnapshotWriter(root=tmp_path / "snaps")
    before = set(tmp_path.rglob("*"))
    with pytest.raises(ValueError):
        writer.write(
            snapshot_id=bad, as_of=as_of, provider=ProviderName.YFINANCE,
            universe_version="u", taxonomy_version="t",
            method_version="m", feature_version="f",
            coverage_status=DataQualityStatus.READY, coverage_pct=100.0,
            prices=prices, benchmark=benchmark, security_master=[],
            features=features, groups=groups, transitions=transitions,
        )
    assert set(tmp_path.rglob("*")) == before


def test_ledger_derived_filename_inherits_snapshot_id_guard(tmp_path):
    # Enrichment CLIs build ledger paths as f"{snapshot_id}_context_ledger.jsonl";
    # a validated id cannot escape the ledger directory.
    from idx_leadership.utils import data_root  # noqa: F401 (import guard)

    for bad in BAD_IDS:
        with pytest.raises(ValueError):
            validate_snapshot_id(bad)
    good = validate_snapshot_id("snap_2026-08-20")
    ledger_path = tmp_path / "raw" / "tavily" / f"{good}_context_ledger.jsonl"
    ledger = RequestLedger(path=ledger_path)
    ledger.record(
        provider="tavily", endpoint="/search", request_type="POST",
        parameters={}, cache_hit=True, status="ok", rows_returned=0, elapsed_ms=0.0,
    )
    ledger.flush()
    assert ledger_path.exists()
    assert ledger_path.resolve().is_relative_to(tmp_path.resolve())


def test_ledger_rejects_empty_and_dot_filenames(tmp_path):
    with pytest.raises(ValueError):
        RequestLedger(path=Path(""))
    with pytest.raises(ValueError):
        RequestLedger(path=tmp_path)  # existing directory, not a file
    with pytest.raises(ValueError):
        RequestLedger(path=tmp_path / ".")  # normalizes to the directory itself


def test_export_out_outside_root_requires_flag(tmp_path, monkeypatch, capsys):
    # The web-export lane refuses --out outside the public snapshots dir
    # unless --allow-outside-root is given. Exercise the real CLI guard.
    import sys

    import scripts.export_snapshot_json as mod

    as_of = date(2026, 8, 20)
    prices, benchmark, features, groups, transitions = _minimal_frames(as_of)
    SnapshotWriter(root=tmp_path / "snaps").write(
        snapshot_id="snap_ok", as_of=as_of, provider=ProviderName.YFINANCE,
        universe_version="u", taxonomy_version="t",
        method_version="m", feature_version="f",
        coverage_status=DataQualityStatus.READY, coverage_pct=100.0,
        prices=prices, benchmark=benchmark, security_master=[],
        features=features, groups=groups, transitions=transitions,
    )
    fake_public = tmp_path / "public"
    fake_public.mkdir()
    monkeypatch.setattr(mod, "PUBLIC_DIR", fake_public)
    outside = tmp_path / "elsewhere" / "snap_ok.json"

    monkeypatch.setattr(
        sys, "argv",
        ["export_snapshot_json", "--snapshot-id", "snap_ok",
         "--out", str(outside), "--snapshot-root", str(tmp_path / "snaps")],
    )
    assert mod.main() == 2
    assert not outside.exists()

    monkeypatch.setattr(
        sys, "argv",
        ["export_snapshot_json", "--snapshot-id", "snap_ok",
         "--out", str(outside), "--allow-outside-root",
         "--snapshot-root", str(tmp_path / "snaps")],
    )
    assert mod.main() == 0
    assert outside.exists()
    capsys.readouterr()
