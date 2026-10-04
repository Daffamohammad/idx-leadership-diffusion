"""Regression tests for three P2 defects found during handoff review.

1. ``build_snapshot_chain`` reused existing snapshot directories without
   checking which price panel produced them, so a changed panel was silently
   ignored while the report credited the new panel.
2. ``validate_public_panel`` passed a panel whose baseline price was NaN:
   ``<= 0`` comparisons are False for NaN, and the baseline coverage count
   only counted rows. Panel file hashes were never verified.
3. ``build_snapshot_index --ids`` silently dropped a requested snapshot whose
   payload was missing and still replaced the index.

Every test builds the inputs it needs inside ``tmp_path``: a generated price
panel (with its own hashed ``source_manifest.json``) and generated snapshot
manifests/payloads. Nothing here depends on the fetched panel under
``data/raw/``, on ``data/snapshots/``, or on any other ignored local artifact,
so the regressions stay covered on a checkout that contains only committed
files.
"""
from __future__ import annotations

import csv
import hashlib
import json
import shutil
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
VALIDATION_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "public_panel_validation.json"

# The validator's YTD baseline constant; the fixture must contain this session.
YTD_BASELINE = date(2025, 12, 30)
CHAIN_AS_OF = date(2026, 10, 2)


def _run(module: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", module, *args],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        timeout=900,
    )


def _weekdays(start: date, end: date) -> list[date]:
    """Weekday sessions, minus the IDX year-end closure that sets the YTD baseline.

    The exchange was closed on 2025-12-31, so the last common session of the
    prior year -- and therefore the YTD baseline -- is 2025-12-30, matching the
    official close the validator checks.
    """
    days: list[date] = []
    cursor = start
    while cursor <= end:
        if cursor.weekday() < 5 and cursor != date(2025, 12, 31):
            days.append(cursor)
        cursor += timedelta(days=1)
    return days


def _universe_tickers() -> list[str]:
    """Tickers from the committed universe config (tracked, always present)."""
    import yaml

    cfg = yaml.safe_load((REPO_ROOT / "config" / "universe.yaml").read_text(encoding="utf-8"))
    return [row["ticker"] for row in cfg["universe"]]


def _build_panel(target: Path, *, sessions: list[date]) -> Path:
    """Write a self-contained, deterministic price panel with hashed manifest.

    Prices are synthetic but structurally valid (positive, finite, one row per
    ticker/session) and deliberately identical for ``close`` and
    ``adjusted_close`` so no corporate-action divergence muddies the tests.
    """
    tickers = _universe_tickers()
    target.mkdir(parents=True, exist_ok=True)

    price_rows: list[list[object]] = []
    for ticker_index, ticker in enumerate(tickers):
        base = 1000.0 + ticker_index * 7.0
        for day_index, day in enumerate(sessions):
            # Gentle deterministic drift keeps every series positive.
            price = round(base * (1.0 + 0.0005 * day_index + 0.0001 * ticker_index), 2)
            price_rows.append([ticker, day.isoformat(), price, price, 1_000_000 + day_index])

    with (target / "prices.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["ticker", "date", "close", "adjusted_close", "volume"])
        writer.writerows(price_rows)

    bench_rows = [
        [day.isoformat(), round(6000.0 + 2.0 * index, 3)]
        for index, day in enumerate(sessions)
    ]
    with (target / "benchmark.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["date", "close"])
        writer.writerows(bench_rows)

    def _sha256(name: str) -> str:
        return hashlib.sha256((target / name).read_bytes()).hexdigest()

    baseline_present = sorted({YTD_BASELINE.isoformat()})
    manifest = {
        "kind": "PUBLIC_PRICE_PANEL",
        "provider": "yfinance",
        "provider_mode": "PUBLIC_PROTOTYPE",
        "window": {
            "start": sessions[0].isoformat(),
            "end": sessions[-1].isoformat(),
        },
        "benchmark_id": "^JKSE",
        "units": {"price": "IDR per share", "volume": "shares"},
        "price_basis": {
            "stocks": "close and adjusted_close both persisted",
            "benchmark": "close",
        },
        "counts": {
            "requested": len(tickers),
            "downloaded": len(tickers),
            "failed": 0,
            "empty": 0,
            "usable_ge_60_sessions": len(tickers),
            "ytd_baseline_present": len(tickers),
            "rows": len(price_rows),
            "benchmark_rows": len(bench_rows),
        },
        "sessions": {
            "latest_session": sessions[-1].isoformat(),
            "benchmark_latest_session": sessions[-1].isoformat(),
            "ytd_baseline_date": YTD_BASELINE.isoformat(),
            "per_ticker": {
                t: {
                    "first": sessions[0].isoformat(),
                    "last": sessions[-1].isoformat(),
                    "sessions": len(sessions),
                }
                for t in tickers
            },
        },
        "diagnostics": {"failed_symbols": [], "empty_symbols": []},
        "corporate_actions": {
            "tickers_with_adjusted_close_divergence": [],
            "divergent_row_counts": {},
        },
        "files": {
            "prices.csv": {"sha256": _sha256("prices.csv"), "rows": len(price_rows)},
            "benchmark.csv": {"sha256": _sha256("benchmark.csv"), "rows": len(bench_rows)},
        },
    }
    assert YTD_BASELINE in sessions, "fixture must contain the YTD baseline session"
    assert baseline_present
    (target / "source_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    return target


def _panel_fixture(tmp_path: Path) -> Path:
    # Enough sessions for the 60-day eligibility rule plus a YTD baseline.
    sessions = _weekdays(date(2025, 12, 1), CHAIN_AS_OF)
    return _build_panel(tmp_path / "panel", sessions=sessions)


def _patch_cell(panel: Path, *, filename: str, ticker: str, day: str, column: str, value: str) -> int:
    """Rewrite one CSV cell, matching the fixture's column layout."""
    path = panel / filename
    lines = path.read_text(encoding="utf-8").splitlines()
    header = lines[0].split(",")
    ticker_i = header.index("ticker") if "ticker" in header else None
    date_i = header.index("date")
    column_i = header.index(column)
    patched = 0
    for index, line in enumerate(lines[1:], start=1):
        cells = line.split(",")
        if cells[date_i] != day:
            continue
        if ticker_i is not None and cells[ticker_i] != ticker:
            continue
        cells[column_i] = value
        lines[index] = ",".join(cells)
        patched += 1
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return patched


def _make_snapshot(snapshots_root: Path, snapshot_id: str, as_of: str, *, mode: str) -> Path:
    """Minimal snapshot directory: the index builder only needs a manifest."""
    snapshot_dir = snapshots_root / snapshot_id
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "entries": [
            {
                "snapshot_id": snapshot_id,
                "as_of": as_of,
                "provider": "yfinance" if mode == "PUBLIC_PROTOTYPE" else "sectors",
                "provider_mode": mode,
                "price_basis": "adjusted_close" if mode == "PUBLIC_PROTOTYPE" else "close",
            }
        ]
    }
    (snapshot_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return snapshot_dir


def _make_payload(public_dir: Path, snapshot_id: str, as_of: str, *, mode: str) -> Path:
    public_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "web-snapshot-v1",
        "snapshot_id": snapshot_id,
        "as_of": as_of,
        "manifest": {
            "entries": [
                {
                    "snapshot_id": snapshot_id,
                    "as_of": as_of,
                    "provider": "yfinance" if mode == "PUBLIC_PROTOTYPE" else "sectors",
                    "provider_mode": mode,
                }
            ]
        },
    }
    path = public_dir / f"{snapshot_id}.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


# ── 1. chain builder must bind snapshots to their source panel ──────


def _build_chain(panel: Path, snapshots_root: Path, report: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return _run(
        "scripts.build_snapshot_chain",
        "--panel-dir", str(panel),
        "--asofs", CHAIN_AS_OF.isoformat(),
        "--snapshots-root", str(snapshots_root),
        "--report", str(report),
        *extra,
    )


def test_chain_rejects_snapshot_built_from_a_different_panel(tmp_path: Path) -> None:
    """Changing a baseline price must not be silently ignored."""
    panel = _panel_fixture(tmp_path)
    snapshots_root = tmp_path / "snapshots"
    report = tmp_path / "chain_report.json"
    snapshot_id = f"snap_public_{CHAIN_AS_OF.isoformat()}"

    first = _build_chain(panel, snapshots_root, report)
    assert first.returncode == 0, first.stderr
    provenance = json.loads(
        (snapshots_root / snapshot_id / "panel_provenance.json").read_text(encoding="utf-8")
    )
    assert set(provenance["panel_files"]) == {"prices.csv", "benchmark.csv"}

    # Re-running with the identical panel must reuse the bundle.
    second = _build_chain(panel, snapshots_root, report)
    assert second.returncode == 0, second.stderr
    assert "reuse verified" in second.stderr

    # Change one baseline price, as the review did.
    patched = _patch_cell(
        panel,
        filename="prices.csv",
        ticker=_universe_tickers()[0],
        day=YTD_BASELINE.isoformat(),
        column="adjusted_close",
        value="999999.0",
    )
    assert patched == 1

    third = _build_chain(panel, snapshots_root, report)
    assert third.returncode == 2, third.stderr
    assert "different price panel" in third.stderr
    assert "prices.csv" in third.stderr


def test_chain_refuses_snapshot_without_provenance(tmp_path: Path) -> None:
    """A pre-existing bundle with no provenance record cannot be verified."""
    panel = _panel_fixture(tmp_path)
    snapshots_root = tmp_path / "snapshots"
    report = tmp_path / "chain_report.json"
    assert _build_chain(panel, snapshots_root, report).returncode == 0

    snapshot_id = f"snap_public_{CHAIN_AS_OF.isoformat()}"
    (snapshots_root / snapshot_id / "panel_provenance.json").unlink()
    again = _build_chain(panel, snapshots_root, report)
    assert again.returncode == 2, again.stderr
    assert "without panel provenance" in again.stderr


def test_force_rebuild_updates_the_ytd_calculation(tmp_path: Path) -> None:
    """--force-rebuild is the explicit, auditable way past a mismatch, and it
    must actually recompute the YTD value from the new panel."""
    import pandas as pd

    panel = _panel_fixture(tmp_path)
    snapshots_root = tmp_path / "snapshots"
    report = tmp_path / "chain_report.json"
    assert _build_chain(panel, snapshots_root, report).returncode == 0

    snapshot_dir = snapshots_root / f"snap_public_{CHAIN_AS_OF.isoformat()}"
    features_before = pd.read_parquet(snapshot_dir / "features.parquet")
    ticker = _universe_tickers()[0]
    row = features_before[features_before["ticker"] == ticker].iloc[0]
    assert str(row["return_ytd_start_date"])[:10] == YTD_BASELINE.isoformat()
    ytd_before = float(row["return_ytd"])

    # Double the baseline price: the YTD return must change materially.
    baseline_value = float(
        [
            line.split(",")
            for line in (panel / "prices.csv").read_text(encoding="utf-8").splitlines()[1:]
            if line.startswith(f"{ticker},{YTD_BASELINE.isoformat()},")
        ][0][3]
    )
    assert baseline_value > 0
    patched = _patch_cell(
        panel,
        filename="prices.csv",
        ticker=ticker,
        day=YTD_BASELINE.isoformat(),
        column="adjusted_close",
        value=str(round(baseline_value * 2, 2)),
    )
    assert patched == 1

    rebuilt = _build_chain(panel, snapshots_root, report, "--force-rebuild")
    assert rebuilt.returncode == 0, rebuilt.stderr
    features_after = pd.read_parquet(snapshot_dir / "features.parquet")
    row_after = features_after[features_after["ticker"] == ticker].iloc[0]
    assert float(row_after["return_ytd"]) != ytd_before, (
        "the rebuilt snapshot must reflect the changed baseline price"
    )
    provenance = json.loads((snapshot_dir / "panel_provenance.json").read_text(encoding="utf-8"))
    assert provenance["panel_files"]["prices.csv"] == hashlib.sha256(
        (panel / "prices.csv").read_bytes()
    ).hexdigest()


# ── 2. validator must reject NaN prices and unverified panels ──────


def test_validator_rejects_nan_baseline_price(tmp_path: Path) -> None:
    panel = _panel_fixture(tmp_path)
    out = tmp_path / "validation.json"
    patched = _patch_cell(
        panel,
        filename="prices.csv",
        ticker=_universe_tickers()[0],
        day=YTD_BASELINE.isoformat(),
        column="adjusted_close",
        value="NaN",
    )
    assert patched == 1

    result = _run("scripts.validate_public_panel", "--panel-dir", str(panel), "--out", str(out))
    assert result.returncode == 1, result.stderr
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["status"] == "FAIL"
    integrity = report["checks"]["panel_integrity"]
    assert integrity["nonfinite_price_rows"] >= 1
    assert integrity["ytd_baseline_invalid_rows"] >= 1
    # Official comparisons must never run on a corrupt panel.
    assert set(report["checks"]) == {"panel_integrity"}


def test_validator_verifies_panel_file_hashes(tmp_path: Path) -> None:
    """Editing a plausible price still invalidates the panel via its hash."""
    panel = _panel_fixture(tmp_path)
    out = tmp_path / "validation.json"
    day = "2026-08-28"
    patched = _patch_cell(
        panel,
        filename="prices.csv",
        ticker=_universe_tickers()[0],
        day=day,
        column="close",
        value="4242.0",
    )
    assert patched == 1

    result = _run("scripts.validate_public_panel", "--panel-dir", str(panel), "--out", str(out))
    assert result.returncode == 1, result.stderr
    integrity = json.loads(out.read_text(encoding="utf-8"))["checks"]["panel_integrity"]
    assert integrity["panel_file_hashes_verified"] is False
    assert integrity["panel_file_hash_mismatches"], "hash mismatch must be reported"
    assert any(m["file"] == "prices.csv" for m in integrity["panel_file_hash_mismatches"])


def test_validator_accepts_untouched_generated_panel_structure(tmp_path: Path) -> None:
    """An intact generated panel clears integrity and provenance.

    The overall verdict still depends on the official source files, which are
    not part of a committed checkout, so only the structural evidence is
    asserted here.
    """
    panel = _panel_fixture(tmp_path)
    out = tmp_path / "validation.json"
    _run("scripts.validate_public_panel", "--panel-dir", str(panel), "--out", str(out))
    report = json.loads(out.read_text(encoding="utf-8"))
    integrity = report["checks"]["panel_integrity"]
    assert integrity["status"] == "PASS"
    assert integrity["nonfinite_price_rows"] == 0
    assert integrity["ytd_baseline_invalid_rows"] == 0
    assert integrity["ytd_baseline_tickers"] == len(_universe_tickers())
    assert integrity["panel_file_hashes_verified"] is True
    if report["status"] != "PASS":
        # Official comparisons need the cached IDX files; report why.
        unavailable = [
            name
            for name, check in report["checks"].items()
            if check.get("status") == "SOURCE_UNAVAILABLE"
        ]
        assert unavailable, f"unexpected failure: {sorted(report['checks'])}"


def test_validator_records_new_integrity_fields() -> None:
    """The tracked fixture must carry the strengthened integrity evidence."""
    if not VALIDATION_FIXTURE.exists():
        pytest.skip("panel validation fixture missing")
    fixture = json.loads(VALIDATION_FIXTURE.read_text(encoding="utf-8"))
    integrity = fixture["checks"]["panel_integrity"]
    assert integrity["nonfinite_price_rows"] == 0
    assert integrity["benchmark_nonfinite_rows"] == 0
    assert integrity["ytd_baseline_invalid_rows"] == 0
    assert integrity["panel_file_hashes_verified"] is True
    assert integrity["panel_file_hash_mismatches"] == []


# ── 3. index builder must fail on a rejected requested id ──────────


def test_index_refuses_when_requested_payload_is_missing(tmp_path: Path) -> None:
    snapshots_root = tmp_path / "snapshots"
    public_dir = tmp_path / "public"
    _make_snapshot(snapshots_root, "snap_sectors_2026-08-27", "2026-08-27", mode="SECTORS_LIVE")
    _make_snapshot(snapshots_root, "snap_public_2026-10-02", "2026-10-02", mode="PUBLIC_PROTOTYPE")
    # Only the Sectors payload is exported; the requested latest one is not.
    _make_payload(public_dir, "snap_sectors_2026-08-27", "2026-08-27", mode="SECTORS_LIVE")

    out_path = public_dir / "index.json"
    result = _run(
        "scripts.build_snapshot_index",
        "--snapshots-root", str(snapshots_root),
        "--out", str(out_path),
        "--allow-outside-root",
        "--ids", "snap_sectors_2026-08-27", "snap_public_2026-10-02",
    )
    assert result.returncode == 2, result.stdout + result.stderr
    assert "was rejected" in result.stderr
    assert "snap_public_2026-10-02" in result.stderr
    assert "refusing to write index.json" in result.stderr
    assert not out_path.exists(), "index must not be replaced on failure"


def test_index_refuses_identity_mismatch_and_keeps_existing_index(tmp_path: Path) -> None:
    snapshots_root = tmp_path / "snapshots"
    public_dir = tmp_path / "public"
    _make_snapshot(snapshots_root, "snap_public_2026-10-02", "2026-10-02", mode="PUBLIC_PROTOTYPE")
    # Payload claims a different as_of than the snapshot manifest.
    _make_payload(public_dir, "snap_public_2026-10-02", "2026-09-30", mode="PUBLIC_PROTOTYPE")

    out_path = public_dir / "index.json"
    out_path.write_text('[{"snapshot_id": "previous_index"}]', encoding="utf-8")
    before = out_path.read_text(encoding="utf-8")

    result = _run(
        "scripts.build_snapshot_index",
        "--snapshots-root", str(snapshots_root),
        "--out", str(out_path),
        "--allow-outside-root",
        "--ids", "snap_public_2026-10-02",
    )
    assert result.returncode == 2, result.stdout + result.stderr
    assert "was rejected" in result.stderr
    assert out_path.read_text(encoding="utf-8") == before, (
        "a rejected request must leave the existing index untouched"
    )


def test_index_accepts_fully_satisfied_requests(tmp_path: Path) -> None:
    """The happy path still works: every requested id lands in the index."""
    snapshots_root = tmp_path / "snapshots"
    public_dir = tmp_path / "public"
    ids = [("snap_sectors_2026-08-27", "2026-08-27", "SECTORS_LIVE"),
           ("snap_public_2026-10-02", "2026-10-02", "PUBLIC_PROTOTYPE")]
    for snapshot_id, as_of, mode in ids:
        _make_snapshot(snapshots_root, snapshot_id, as_of, mode=mode)
        _make_payload(public_dir, snapshot_id, as_of, mode=mode)

    out_path = public_dir / "index.json"
    result = _run(
        "scripts.build_snapshot_index",
        "--snapshots-root", str(snapshots_root),
        "--out", str(out_path),
        "--allow-outside-root",
        "--ids", *[snapshot_id for snapshot_id, _, _ in ids],
    )
    assert result.returncode == 0, result.stderr
    entries = json.loads(out_path.read_text(encoding="utf-8"))
    assert {e["snapshot_id"] for e in entries} == {snapshot_id for snapshot_id, _, _ in ids}
    assert [e["as_of"] for e in entries] == sorted(e["as_of"] for e in entries)


def test_index_default_mode_filter_is_unchanged(tmp_path: Path) -> None:
    """Without --ids the historical SECTORS_LIVE default still applies."""
    snapshots_root = tmp_path / "snapshots"
    public_dir = tmp_path / "public"
    for snapshot_id, as_of, mode in [
        ("snap_sectors_2026-08-27", "2026-08-27", "SECTORS_LIVE"),
        ("snap_public_2026-10-02", "2026-10-02", "PUBLIC_PROTOTYPE"),
    ]:
        _make_snapshot(snapshots_root, snapshot_id, as_of, mode=mode)
        _make_payload(public_dir, snapshot_id, as_of, mode=mode)

    out_path = public_dir / "index.json"
    result = _run(
        "scripts.build_snapshot_index",
        "--snapshots-root", str(snapshots_root),
        "--out", str(out_path),
        "--allow-outside-root",
    )
    assert result.returncode == 0, result.stderr
    entries = json.loads(out_path.read_text(encoding="utf-8"))
    assert [e["snapshot_id"] for e in entries] == ["snap_sectors_2026-08-27"]