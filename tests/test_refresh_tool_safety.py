"""Regression tests for three P2 defects found during handoff review.

1. ``build_snapshot_chain`` reused existing snapshot directories without
   checking which price panel produced them, so a changed panel was silently
   ignored while the report credited the new panel.
2. ``validate_public_panel`` passed a panel whose baseline price was NaN:
   ``<= 0`` comparisons are False for NaN, and the baseline coverage count
   only counted rows. Panel file hashes were never verified.
3. ``build_snapshot_index --ids`` silently dropped a requested snapshot whose
   payload was missing and still replaced the index.

Each test reproduces the failure in an isolated temporary directory so the
real artifacts are never touched.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
PANEL_ROOT = REPO_ROOT / "data" / "raw" / "public"
VALIDATION_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "public_panel_validation.json"


def _panel_dir() -> Path | None:
    if not PANEL_ROOT.is_dir():
        return None
    candidates = sorted(
        (d for d in PANEL_ROOT.glob("panel_*") if (d / "prices.csv").is_file()),
        key=lambda d: d.name,
    )
    return candidates[-1] if candidates else None


def _run(module: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", module, *args],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        timeout=600,
    )


def _copy_panel(tmp_path: Path) -> Path:
    source = _panel_dir()
    assert source is not None, "run scripts.refresh_public_panel first"
    target = tmp_path / "panel"
    shutil.copytree(source, target)
    return target


# ── 1. chain builder must bind snapshots to their source panel ──────


@pytest.mark.skipif(_panel_dir() is None, reason="price panel not fetched")
def test_chain_rejects_snapshot_built_from_a_different_panel(tmp_path: Path) -> None:
    """Changing BBCA's baseline must not be silently ignored."""
    panel = _copy_panel(tmp_path)
    snapshots_root = tmp_path / "snapshots"
    report = tmp_path / "chain_report.json"

    # First build: succeeds and records panel provenance.
    first = _run(
        "scripts.build_snapshot_chain",
        "--panel-dir", str(panel),
        "--asofs", "2026-09-11",
        "--snapshots-root", str(snapshots_root),
        "--report", str(report),
    )
    assert first.returncode == 0, first.stderr
    snapshot_dir = snapshots_root / "snap_public_2026-09-11"
    provenance = json.loads((snapshot_dir / "panel_provenance.json").read_text())
    assert "prices.csv" in provenance["panel_files"]

    # Re-running unchanged must reuse it successfully (provenance verified).
    second = _run(
        "scripts.build_snapshot_chain",
        "--panel-dir", str(panel),
        "--asofs", "2026-09-11",
        "--snapshots-root", str(snapshots_root),
        "--report", str(report),
    )
    assert second.returncode == 0, second.stderr
    assert "reuse verified" in second.stderr

    # Now change a baseline price in the panel, as the review did.
    prices_csv = panel / "prices.csv"
    lines = prices_csv.read_text(encoding="utf-8").splitlines()
    header = lines[0].split(",")
    ticker_i = header.index("ticker")
    date_i = header.index("date")
    adj_i = header.index("adjusted_close")
    patched = 0
    for index, line in enumerate(lines[1:], start=1):
        cells = line.split(",")
        if cells[ticker_i] == "BBCA.JK" and cells[date_i] == "2025-12-30":
            cells[adj_i] = str(float(cells[adj_i]) * 1.5)
            lines[index] = ",".join(cells)
            patched += 1
    assert patched == 1, "expected exactly one BBCA baseline row"
    prices_csv.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # The run must refuse rather than report success on the stale bundle.
    third = _run(
        "scripts.build_snapshot_chain",
        "--panel-dir", str(panel),
        "--asofs", "2026-09-11",
        "--snapshots-root", str(snapshots_root),
        "--report", str(report),
    )
    assert third.returncode == 2, third.stderr
    assert "different price panel" in third.stderr
    assert "prices.csv" in third.stderr


@pytest.mark.skipif(_panel_dir() is None, reason="price panel not fetched")
def test_chain_refuses_snapshot_without_provenance(tmp_path: Path) -> None:
    """A pre-existing bundle with no provenance record cannot be verified."""
    panel = _copy_panel(tmp_path)
    snapshots_root = tmp_path / "snapshots"
    report = tmp_path / "chain_report.json"
    assert _run(
        "scripts.build_snapshot_chain",
        "--panel-dir", str(panel),
        "--asofs", "2026-09-11",
        "--snapshots-root", str(snapshots_root),
        "--report", str(report),
    ).returncode == 0

    (snapshots_root / "snap_public_2026-09-11" / "panel_provenance.json").unlink()
    again = _run(
        "scripts.build_snapshot_chain",
        "--panel-dir", str(panel),
        "--asofs", "2026-09-11",
        "--snapshots-root", str(snapshots_root),
        "--report", str(report),
    )
    assert again.returncode == 2
    assert "without panel provenance" in again.stderr


@pytest.mark.skipif(_panel_dir() is None, reason="price panel not fetched")
def test_force_rebuild_replaces_a_stale_bundle(tmp_path: Path) -> None:
    """--force-rebuild is the explicit, auditable way past a mismatch."""
    panel = _copy_panel(tmp_path)
    snapshots_root = tmp_path / "snapshots"
    report = tmp_path / "chain_report.json"
    assert _run(
        "scripts.build_snapshot_chain",
        "--panel-dir", str(panel),
        "--asofs", "2026-09-11",
        "--snapshots-root", str(snapshots_root),
        "--report", str(report),
    ).returncode == 0

    prices_csv = panel / "prices.csv"
    prices_csv.write_text(
        prices_csv.read_text(encoding="utf-8").replace(
            "BBCA.JK,2025-12-30,", "BBCA.JK,2025-12-30,", 1
        ),
        encoding="utf-8",
    )
    prices_csv.write_text(
        prices_csv.read_text(encoding="utf-8") + "\n", encoding="utf-8"
    )

    rebuilt = _run(
        "scripts.build_snapshot_chain",
        "--panel-dir", str(panel),
        "--asofs", "2026-09-11",
        "--snapshots-root", str(snapshots_root),
        "--report", str(report),
        "--force-rebuild",
    )
    assert rebuilt.returncode == 0, rebuilt.stderr
    provenance = json.loads(
        (snapshots_root / "snap_public_2026-09-11" / "panel_provenance.json").read_text()
    )
    import hashlib

    assert provenance["panel_files"]["prices.csv"] == hashlib.sha256(
        (panel / "prices.csv").read_bytes()
    ).hexdigest()


# ── 2. validator must reject NaN prices and unverified panels ──────


@pytest.mark.skipif(_panel_dir() is None, reason="price panel not fetched")
def test_validator_rejects_nan_baseline_price(tmp_path: Path) -> None:
    panel = _copy_panel(tmp_path)
    out = tmp_path / "validation.json"
    prices_csv = panel / "prices.csv"
    lines = prices_csv.read_text(encoding="utf-8").splitlines()
    header = lines[0].split(",")
    ticker_i, date_i, adj_i = header.index("ticker"), header.index("date"), header.index("adjusted_close")
    patched = 0
    for index, line in enumerate(lines[1:], start=1):
        cells = line.split(",")
        if cells[ticker_i] == "BBCA.JK" and cells[date_i] == "2025-12-30":
            cells[adj_i] = "NaN"
            lines[index] = ",".join(cells)
            patched += 1
    assert patched == 1
    prices_csv.write_text("\n".join(lines) + "\n", encoding="utf-8")

    result = _run(
        "scripts.validate_public_panel",
        "--panel-dir", str(panel),
        "--out", str(out),
    )
    assert result.returncode == 1, result.stderr
    report = json.loads(out.read_text())
    assert report["status"] == "FAIL"
    integrity = report["checks"]["panel_integrity"]
    assert integrity["nonfinite_price_rows"] >= 1
    assert integrity["ytd_baseline_invalid_rows"] >= 1
    # A corrupt panel must not reach the official comparisons at all.
    assert set(report["checks"]) == {"panel_integrity"}


@pytest.mark.skipif(_panel_dir() is None, reason="price panel not fetched")
def test_validator_verifies_panel_file_hashes(tmp_path: Path) -> None:
    """Editing any price invalidates the panel, even when values stay plausible."""
    panel = _copy_panel(tmp_path)
    out = tmp_path / "validation.json"
    prices_csv = panel / "prices.csv"
    text = prices_csv.read_text(encoding="utf-8")
    # Halve one mid-panel close: still finite and positive, so only the
    # recorded-hash comparison can catch it.
    prices_csv.write_text(
        text.replace(",2026-08-28,", ",2026-08-27,", 1).replace(
            "2026-08-27,8", "2026-08-27,4", 1
        ),
        encoding="utf-8",
    )
    result = _run(
        "scripts.validate_public_panel",
        "--panel-dir", str(panel),
        "--out", str(out),
    )
    assert result.returncode == 1, result.stderr
    integrity = json.loads(out.read_text())["checks"]["panel_integrity"]
    assert integrity["panel_file_hashes_verified"] is False
    assert integrity["panel_file_hash_mismatches"], "hash mismatch must be reported"


def test_validator_records_new_integrity_fields() -> None:
    """The tracked fixture must carry the strengthened integrity evidence."""
    if not VALIDATION_FIXTURE.exists():
        pytest.skip("panel validation fixture missing")
    fixture = json.loads(VALIDATION_FIXTURE.read_text())
    integrity = fixture["checks"]["panel_integrity"]
    assert integrity["nonfinite_price_rows"] == 0
    assert integrity["benchmark_nonfinite_rows"] == 0
    assert integrity["ytd_baseline_invalid_rows"] == 0
    assert integrity["panel_file_hashes_verified"] is True
    assert integrity["panel_file_hash_mismatches"] == []


# ── 3. index builder must fail on a rejected requested id ──────────


def _published_snapshots() -> list[str]:
    public = REPO_ROOT / "app" / "web" / "public" / "snapshots"
    return sorted(p.stem for p in public.glob("*.json") if p.stem != "index")


def test_index_refuses_when_requested_payload_is_missing(tmp_path: Path) -> None:
    available = _published_snapshots()
    if not available:
        pytest.skip("no exported snapshots to curate")
    keep, omit = available[0], (available[1] if len(available) > 1 else available[0])
    if keep == omit:
        # Only one payload exists; request it plus a known-but-unexported id.
        omit = "snap_public_2026-09-25"

    public = REPO_ROOT / "app" / "web" / "public" / "snapshots"
    stage = tmp_path / "public"
    stage.mkdir()
    shutil.copy(public / f"{keep}.json", stage / f"{keep}.json")

    out_path = stage / "index.json"
    result = _run(
        "scripts.build_snapshot_index",
        "--out", str(out_path),
        "--ids", keep, omit,
    )
    assert result.returncode == 2, result.stdout + result.stderr
    assert "was rejected" in result.stderr
    assert "refusing to write index.json" in result.stderr
    assert not out_path.exists(), "index must not be replaced on failure"


def test_index_accepts_fully_satisfied_requests(tmp_path: Path) -> None:
    """The happy path still works: every requested id lands in the index."""
    public = REPO_ROOT / "app" / "web" / "public" / "snapshots"
    available = [p.stem for p in public.glob("*.json") if p.stem != "index"]
    if len(available) < 2:
        pytest.skip("need at least two exported snapshots")
    stage = tmp_path / "public"
    stage.mkdir()
    for snapshot_id in available:
        shutil.copy(public / f"{snapshot_id}.json", stage / f"{snapshot_id}.json")
    out_path = stage / "index.json"
    result = _run(
        "scripts.build_snapshot_index",
        "--out", str(out_path),
        "--ids", *available,
    )
    assert result.returncode == 0, result.stderr
    entries = json.loads(out_path.read_text())
    assert {e["snapshot_id"] for e in entries} == set(available)