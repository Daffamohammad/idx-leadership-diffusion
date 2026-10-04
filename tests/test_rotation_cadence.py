"""Daily replay stays hermetic and separate from canonical comparison history."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from idx_leadership.data.comparability import REQUIRED_COMPARABILITY_FIELDS
from idx_leadership.data.snapshots import SnapshotReader
from scripts.export_snapshot_json import export
from tests.test_public_refresh_chain import _run_tsx


SESSIONS = ["2026-09-18", *pd.bdate_range("2026-09-21", "2026-10-02").strftime("%Y-%m-%d")]
CURRENT_ID = "snap_public_2026-10-02"
PANEL_FILES = {"prices.csv": "a" * 64, "benchmark.csv": "b" * 64}


def _write_snapshot(root: Path, session: str, value: float) -> Path:
    target = root / f"snap_public_{session}"
    target.mkdir(parents=True)
    entry = {key: f"test-{key}" for key in REQUIRED_COMPARABILITY_FIELDS}
    entry.update(snapshot_id=target.name, as_of=session, provider_mode="PUBLIC_PROTOTYPE", price_basis="adjusted_close")
    (target / "manifest.json").write_text(json.dumps({"entries": [entry]}))
    (target / "security_master.json").write_text("[]")
    (target / "panel_provenance.json").write_text(json.dumps({"panel_files": PANEL_FILES}))
    (target / "COMPLETE").touch()
    for name in ("prices", "features", "transitions"):
        pd.DataFrame().to_parquet(target / f"{name}.parquet")
    pd.DataFrame({"date": SESSIONS, "close": [100.0] * len(SESSIONS)}).to_parquet(target / "benchmark.parquet")
    pd.DataFrame([{
        "group_id": "TestSector", "group_name": "Test sector",
        "group_excess_return_ytd": value, "ytd_start_date": "2025-12-30",
        "group_excess_return_20d": value / 2, "group_excess_return_60d": value / 4,
    }]).to_parquet(target / "groups.parquet")
    return target


@pytest.fixture
def replay(tmp_path: Path) -> tuple[Path, Path]:
    canonical = tmp_path / "canonical"
    daily = tmp_path / "daily"
    for index, session in enumerate(SESSIONS):
        _write_snapshot(daily, session, float(index))
    current = _write_snapshot(canonical, SESSIONS[-1], float(len(SESSIONS) - 1))
    (current / "comparability.json").write_text(json.dumps({
        "status": "COMPATIBLE", "selected_previous": "snap_public_2026-09-25",
    }))
    return canonical, daily


def test_daily_replay_exports_real_sessions_without_changing_comparison(replay, tmp_path) -> None:
    canonical, daily = replay
    output = tmp_path / "export.json"
    export(CURRENT_ID, output, snapshot_root=canonical, rotation_history_root=daily)
    payload = json.loads(output.read_text())
    history = payload["rotation_daily_history"]
    assert history["sessions"] == SESSIONS
    assert history["panel_files"] == PANEL_FILES
    assert [point["as_of"] for point in history["points"]] == SESSIONS
    assert [point["group_excess_return_ytd"] for point in history["points"]] == list(range(len(SESSIONS)))
    assert payload["previous_snapshot_id"] == "snap_public_2026-09-25"
    assert payload["rotation_history"] == []  # canonical root has only one snapshot


@pytest.mark.parametrize("defect", ["missing_session", "panel_hash", "membership", "missing_axis", "endpoint", "incomplete"])
def test_daily_replay_refuses_defects_without_replacing_output(replay, tmp_path, defect) -> None:
    canonical, daily = replay
    middle = daily / f"snap_public_{SESSIONS[2]}"
    if defect == "missing_session":
        (middle / "manifest.json").unlink()
    elif defect == "panel_hash":
        (middle / "panel_provenance.json").write_text(json.dumps({"panel_files": {**PANEL_FILES, "prices.csv": "c" * 64}}))
    elif defect == "membership":
        path = middle / "manifest.json"
        manifest = json.loads(path.read_text())
        manifest["entries"][0]["eligible_ticker_set_hash"] = "different-cohort"
        path.write_text(json.dumps(manifest))
    elif defect == "missing_axis":
        groups = pd.read_parquet(middle / "groups.parquet")
        groups["group_excess_return_60d"] = float("nan")
        groups.to_parquet(middle / "groups.parquet")
    elif defect == "endpoint":
        path = daily / CURRENT_ID / "groups.parquet"
        groups = pd.read_parquet(path)
        groups["group_excess_return_ytd"] += 1
        groups.to_parquet(path)
    else:
        (middle / "COMPLETE").unlink()
    output = tmp_path / "export.json"
    output.write_bytes(b"previous verified export")
    with pytest.raises(ValueError, match="daily rotation"):
        export(CURRENT_ID, output, snapshot_root=canonical, rotation_history_root=daily)
    assert output.read_bytes() == b"previous verified export"


def test_daily_replay_excludes_future_snapshots(replay, tmp_path) -> None:
    canonical, daily = replay
    future = _write_snapshot(daily, "2026-10-05", 999.0)
    (future / "panel_provenance.json").unlink()
    output = tmp_path / "export.json"
    export(CURRENT_ID, output, snapshot_root=canonical, rotation_history_root=daily)
    payload = json.loads(output.read_text())
    assert payload["rotation_daily_history"]["sessions"] == SESSIONS
    assert all(point["as_of"] <= "2026-10-02" for point in payload["rotation_daily_history"]["points"])


def test_rotation_sampling_uses_session_end_of_week_and_preserves_axes() -> None:
    script = '''
      import { sampleRotationHistory } from "./app/web/src/data/rotation.ts";
      const sessions = ["2026-09-18", "2026-09-21", "2026-09-22", "2026-09-23", "2026-09-24",
        "2026-09-25", "2026-09-28", "2026-09-29", "2026-09-30", "2026-10-01"];
      const points = sessions.map((as_of, i) => ({as_of, group_excess_return_ytd: i + 1, relative_momentum: i + 2}));
      const daily = sampleRotationHistory(points, sessions, "daily");
      const weekly = sampleRotationHistory([...points].reverse(), sessions, "weekly");
      console.log(JSON.stringify({ daily: daily.length, weekly }));
    '''
    out = json.loads(_run_tsx(script))
    assert out["daily"] == 10
    assert out["weekly"] == [
        {"as_of": "2026-09-18", "group_excess_return_ytd": 1, "relative_momentum": 2},
        {"as_of": "2026-09-25", "group_excess_return_ytd": 6, "relative_momentum": 7},
        {"as_of": "2026-10-01", "group_excess_return_ytd": 10, "relative_momentum": 11},
    ]


def test_rotation_sampling_refuses_sparse_duplicate_or_invalid_axes() -> None:
    script = '''
      import { sampleRotationHistory } from "./app/web/src/data/rotation.ts";
      const sessions = ["2026-09-04", "2026-09-07", "2026-09-08"];
      const points = sessions.map(as_of => ({as_of, group_excess_return_ytd: 1, relative_momentum: 2}));
      console.log(JSON.stringify([
        sampleRotationHistory(points.slice(1), sessions, "daily"),
        sampleRotationHistory([points[0], points[0], points[2]], sessions, "daily"),
        sampleRotationHistory([points[0], {...points[1], relative_momentum: null}, points[2]], sessions, "daily"),
        sampleRotationHistory(points, sessions, "weekly"),
        sampleRotationHistory(points, [...sessions].reverse(), "daily"),
      ].map(series => series.length)));
    '''
    assert json.loads(_run_tsx(script)) == [0, 0, 0, 0, 0]


def test_active_daily_replay_has_complete_sessions_and_matches_current_groups() -> None:
    active = Path(__file__).resolve().parents[1] / "app/web/public/snapshots" / f"{CURRENT_ID}.json"
    payload = json.loads(active.read_text())
    daily = payload["rotation_daily_history"]
    sessions = daily["sessions"]
    assert len(sessions) == 21
    assert sessions[0] == "2026-09-04" and sessions[-1] == payload["as_of"]
    assert len(set(daily["snapshot_ids"])) == 21
    groups = {row["group_id"]: row for row in payload["groups"]}
    assert {(point["group_id"], point["as_of"]) for point in daily["points"]} == {
        (group, session) for group in groups for session in sessions
    }
    for point in daily["points"]:
        assert point["relative_momentum"] == pytest.approx(
            point["group_excess_return_20d"] - point["group_excess_return_60d"]
        )
        assert point["ytd_start_date"][:10] == "2025-12-30"
        if point["as_of"] == payload["as_of"]:
            assert point["group_excess_return_ytd"] == groups[point["group_id"]]["group_excess_return_ytd"]
    # The daily replay must not overwrite the weekly diffusion comparison.
    assert payload["previous_snapshot_id"] == "snap_public_2026-09-25"


def test_active_daily_and_weekly_sampling_both_clear_the_trail_gate() -> None:
    out = json.loads(_run_tsx('''
      import fs from "node:fs";
      import { sampleRotationHistory } from "./app/web/src/data/rotation.ts";
      const payload = JSON.parse(fs.readFileSync("app/web/public/snapshots/snap_public_2026-10-02.json", "utf8"));
      const daily = payload.rotation_daily_history;
      console.log(JSON.stringify(payload.groups.map(group => {
        const points = daily.points.filter(point => point.group_id === group.group_id);
        return { daily: sampleRotationHistory(points, daily.sessions, "daily").length,
          weekly: sampleRotationHistory(points, daily.sessions, "weekly").map(point => point.as_of) };
      })));
    '''))
    assert len(out) == 10
    assert all(group["daily"] == 21 for group in out)
    assert all(group["weekly"] == ["2026-09-04", "2026-09-11", "2026-09-18", "2026-09-25", "2026-10-02"] for group in out)
