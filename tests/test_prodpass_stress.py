"""Production-pass stress tests: same-id races, crash recovery, ledger exactness."""
from __future__ import annotations

import json
import threading
from datetime import date
from pathlib import Path

import pandas as pd

from idx_leadership.data import RawCache
from idx_leadership.data.snapshots import SnapshotReader, SnapshotWriter
from idx_leadership.models import DataQualityStatus, ProviderName
from idx_leadership.providers.ledger import RequestLedger


def _frames(as_of):
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
    return prices, benchmark, features, groups, transitions


def _write(root, snapshot_id, as_of):
    prices, benchmark, features, groups, transitions = _frames(as_of)
    SnapshotWriter(root=root).write(
        snapshot_id=snapshot_id,
        as_of=as_of,
        provider=ProviderName.YFINANCE,
        universe_version="u",
        taxonomy_version="t",
        method_version="m",
        feature_version="f",
        coverage_status=DataQualityStatus.READY,
        coverage_pct=100.0,
        prices=prices,
        benchmark=benchmark,
        security_master=[],
        features=features,
        groups=groups,
        transitions=transitions,
    )


def test_same_id_concurrent_writes_stay_loadable(tmp_path):
    root = tmp_path / "snaps"
    as_of = date(2026, 8, 20)
    errors: list[Exception] = []

    def worker():
        try:
            _write(root, "snap_race", as_of)
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert not errors
    loaded = SnapshotReader(root=root).load("snap_race")
    assert not loaded["prices"].empty
    assert len(loaded["prices"]) == 2


def test_reader_tolerates_torn_bundle(tmp_path):
    root = tmp_path / "snaps"
    as_of = date(2026, 8, 20)
    _write(root, "snap_torn", as_of)
    target = root / "snap_torn"
    # Simulate a crash between file writes: remove one twin, corrupt one JSON.
    (target / "prices.parquet").unlink(missing_ok=True)
    (target / "quality.json").write_text("{not json", encoding="utf-8")
    loaded = SnapshotReader(root=root).load("snap_torn")
    # CSV twin covers the missing parquet; corrupt JSON degrades to default.
    assert not loaded["prices"].empty
    assert loaded["quality"] == {}
    assert loaded["complete"] is False


def test_ledger_exact_under_threads(tmp_path):
    ledger = RequestLedger(path=tmp_path / "ledger.jsonl")

    def worker(n):
        for _ in range(n):
            ledger.record(
                provider="t",
                endpoint="/e",
                request_type="single",
                parameters={"a": 1},
                cache_hit=False,
                status="ok",
                rows_returned=1,
                elapsed_ms=1.0,
            )

    threads = [threading.Thread(target=worker, args=(50,)) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(ledger.entries()) == 400
    ledger.flush()
    lines = (tmp_path / "ledger.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 400
    assert all("timestamp_iso" in line and "T" in line for line in lines)


def test_cache_torn_file_returns_none(tmp_path):
    cache = RawCache(root=tmp_path / "cache")
    cache.set("k", {"rows": [1, 2, 3]})
    assert cache.get("k") == {"rows": [1, 2, 3]}
    # Corrupt the single cache file; reads must fail closed, not raise.
    files = list((tmp_path / "cache").rglob("*.json"))
    assert len(files) == 1
    files[0].write_text("{corrupt", encoding="utf-8")
    assert cache.get("k") is None


def test_live_probe_fixture_has_no_secrets():
    raw = Path("tests/fixtures/yfinance_probe_bbca_2026-09-06_12.json").read_text()
    lowered = raw.lower()
    assert "api_key" not in lowered
    assert "bearer" not in lowered
    assert "authorization" not in lowered
    fixture = json.loads(raw)
    assert fixture["receipt"]["live_calls"] == 1
    assert fixture["receipt"]["credits_spent"] == 0
