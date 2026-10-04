"""Contract tests for the 2026-10-02 public refresh (panel, chain, export).

These read only tracked artifacts:

* ``app/web/public/snapshots/snap_public_2026-10-02.json`` -- the exported,
  git-whitelisted active bundle,
* ``app/web/public/snapshots/index.json`` -- the curated index,
* ``tests/fixtures/public_panel_validation.json`` -- trimmed validation report.

The heavy artifacts (``data/raw/public/panel_*``,
``data/snapshots/snap_public_*``, ``data/normalized/*``) stay ignored, so the
tests assert the published contract rather than local scratch state.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
PUBLIC_DIR = REPO_ROOT / "app" / "web" / "public" / "snapshots"
ACTIVE_ID = "snap_public_2026-10-02"


@pytest.fixture(scope="module")
def payload() -> dict:
    path = PUBLIC_DIR / f"{ACTIVE_ID}.json"
    if not path.exists():
        pytest.skip(f"{ACTIVE_ID}.json not exported")
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def validation() -> dict:
    path = REPO_ROOT / "tests" / "fixtures" / "public_panel_validation.json"
    if not path.exists():
        pytest.skip("panel validation fixture missing")
    return json.loads(path.read_text(encoding="utf-8"))


# ── export integrity ─────────────────────────────────────────────


def test_active_bundle_is_complete_and_marked_complete(payload: dict) -> None:
    assert payload.get("complete") is True
    assert payload.get("snapshot_id") == ACTIVE_ID
    assert payload.get("as_of") == "2026-10-02"
    assert payload.get("schema_version") == "web-snapshot-v1"


def test_manifest_parity_and_contract(payload: dict) -> None:
    entry = (payload.get("manifest") or {}).get("entries", [{}])[0]
    assert entry.get("snapshot_id") == payload["snapshot_id"]
    assert entry.get("as_of") == payload["as_of"]
    assert entry.get("provider_mode") == "PUBLIC_PROTOTYPE"
    assert entry.get("price_basis") == "adjusted_close"
    # Fail-closed comparability key: one hash shared by the whole chain.
    assert entry.get("eligible_ticker_set_hash") == "5ee90b3d073b02ec"


def test_quality_ready_with_gaps_discloses_wskt(payload: dict) -> None:
    quality = payload.get("quality") or {}
    assert quality.get("status") in {"READY", "READY_WITH_GAPS"}
    # 54 requested, 53 usable: WSKT.JK is an honest, disclosed acquisition gap.
    assert quality.get("requested_securities") == 54
    assert quality.get("usable_securities") == 53
    issues = " ".join(quality.get("issues") or [])
    assert "WSKT.JK" in issues, "the missing ticker must be disclosed, not hidden"


# ── Goal 1: YTD from a validated prior-year baseline ─────────────


def test_features_carry_ytd_from_prior_year_baseline(payload: dict) -> None:
    features = payload.get("features") or []
    dated = [f for f in features if f.get("return_ytd_start_date")]
    assert len(dated) == 53, f"expected 53 features with YTD, got {len(dated)}"
    baselines = {
        str(f["return_ytd_start_date"])[:10] for f in dated
    }
    assert baselines == {"2025-12-30"}, f"unexpected YTD baselines: {baselines}"
    for feature in dated:
        assert isinstance(feature.get("return_ytd"), (int, float))
        assert isinstance(feature.get("benchmark_return_ytd"), (int, float))
        assert isinstance(feature.get("excess_return_ytd"), (int, float))


def test_groups_expose_ytd_excess_and_baseline(payload: dict) -> None:
    groups = payload.get("groups") or []
    assert groups, "groups must be present"
    with_ytd = [g for g in groups if g.get("group_excess_return_ytd") is not None]
    assert len(with_ytd) == len(groups), "every group row should carry YTD excess"
    for group in with_ytd:
        assert str(group.get("ytd_start_date"))[:10] == "2025-12-30"


def test_ytd_benchmark_return_matches_official_close_ratio(payload: dict) -> None:
    """Group YTD excess must be internally consistent: benchmark YTD return
    equals the official close ratio from 2025-12-30 to 2026-10-02."""
    # Official closes: 2025-12-30 = 8646.94, 2026-10-02 = 6036.888 (IDX).
    expected = (6036.888 / 8646.94 - 1.0) * 100.0
    groups = payload.get("groups") or []
    benchmark = groups[0].get("benchmark_return_ytd")
    assert benchmark is not None
    assert abs(benchmark - expected) < 0.01, (
        f"benchmark YTD {benchmark} does not match official close ratio {expected}"
    )


# ── Goal 2: real comparable prior snapshot producing changes ─────


def test_comparability_is_compatible_with_real_previous(payload: dict) -> None:
    comparability = payload.get("comparability") or {}
    assert comparability.get("status") == "COMPATIBLE"
    assert payload.get("previous_snapshot_id") == "snap_public_2026-09-25"
    assert comparability.get("selected_previous_as_of") == "2026-09-25"
    # The Sectors capture must be reported as incomparable, never silently used.
    checked = {
        c.get("snapshot_id"): c.get("status") for c in comparability.get("snapshots_checked") or []
    }
    assert checked.get("snap_sectors_2026-08-27") == "INCOMPARABLE"
    compatible = sorted(k for k, v in checked.items() if v == "COMPATIBLE")
    assert compatible == [
        "snap_public_2026-09-04",
        "snap_public_2026-09-11",
        "snap_public_2026-09-18",
        "snap_public_2026-09-25",
    ], f"unexpected compatible priors: {compatible}"


def test_transitions_carry_previous_values(payload: dict) -> None:
    transitions = payload.get("transitions") or []
    assert len(transitions) == 10
    for row in transitions:
        assert str(row.get("previous_date"))[:10] == "2026-09-25"
        assert str(row.get("current_date"))[:10] == "2026-10-02"
        assert row.get("previous_diffusion_state_v2") is not None
        assert row.get("current_diffusion_state_v2") is not None


def test_supported_groups_have_real_diffusion_states(payload: dict) -> None:
    """Groups meeting the methodology minimum must not be UNCONFIRMED, and
    groups below it must stay UNCONFIRMED rather than being forced."""
    import yaml

    methodology = yaml.safe_load(
        (REPO_ROOT / "config" / "methodology.yaml").read_text(encoding="utf-8")
    )
    minimum = int(methodology["groups"]["minimum_constituents"])
    groups = payload.get("groups") or []
    supported = [g for g in groups if int(g.get("eligible_count") or 0) >= minimum]
    assert len(supported) >= 4, "expected several supported groups"
    states = {g["group_id"]: g.get("diffusion_state_v2") for g in supported}
    assert all(v and v != "UNCONFIRMED" for v in states.values()), (
        f"groups at or above the minimum ({minimum}) should have confirmed states: {states}"
    )
    below = [g for g in groups if int(g.get("eligible_count") or 0) < minimum]
    for group in below:
        assert group.get("diffusion_state_v2") == "UNCONFIRMED", (
            f"{group['group_id']} is below the minimum and must stay UNCONFIRMED"
        )
    # at least one group with a non-zero breadth delta => a real change
    deltas = [g.get("breadth_delta") for g in supported]
    assert any(d is not None and abs(d) > 0 for d in deltas), (
        "expected at least one group with a real breadth change"
    )


def test_breadth_history_covers_five_dated_sessions(payload: dict) -> None:
    history = payload.get("breadth_history") or []
    dates = sorted({p["as_of"] for p in history})
    assert dates == [
        "2026-09-04",
        "2026-09-11",
        "2026-09-18",
        "2026-09-25",
        "2026-10-02",
    ], f"unexpected breadth history dates: {dates}"
    for point in history:
        assert point["as_of"] <= payload["as_of"], "no future points allowed"
        assert 0 <= point["breadth"] <= 100


# ── Goal 4 / rotation tail: real dated observations ─────────────


def test_rotation_history_has_five_dated_points_per_group(payload: dict) -> None:
    history = payload.get("rotation_history") or []
    assert history, "rotation_history must be emitted for the tail"
    by_group: dict[str, list[dict]] = {}
    for point in history:
        by_group.setdefault(point["group_id"], []).append(point)
    assert len(by_group) == 10, f"expected 10 groups, got {len(by_group)}"
    for group_id, points in by_group.items():
        dates = sorted(p["as_of"] for p in points)
        assert len(dates) >= 3, f"{group_id} needs >= 3 dated points for a trail"
        assert dates == sorted(dates)
        assert dates[-1] == payload["as_of"], "trail must reach the current session"
        for point in points:
            assert point["as_of"] <= payload["as_of"], "no future rotation points"
            assert isinstance(point["group_excess_return_ytd"], (int, float))
            if (
                point["group_excess_return_20d"] is not None
                and point["group_excess_return_60d"] is not None
            ):
                expected = point["group_excess_return_20d"] - point["group_excess_return_60d"]
                assert abs(point["relative_momentum"] - expected) < 1e-9


def test_rotation_history_latest_point_matches_group_row(payload: dict) -> None:
    groups = {g["group_id"]: g for g in payload.get("groups") or []}
    history = payload.get("rotation_history") or []
    latest: dict[str, dict] = {}
    for point in history:
        current = latest.get(point["group_id"])
        if current is None or point["as_of"] > current["as_of"]:
            latest[point["group_id"]] = point
    for group_id, point in latest.items():
        group = groups.get(group_id)
        assert group is not None
        assert abs(point["group_excess_return_ytd"] - group["group_excess_return_ytd"]) < 1e-9, (
            f"{group_id}: trail endpoint must equal the published group value"
        )


def test_rotation_history_excludes_future_and_incompatible_snapshots(payload: dict) -> None:
    dates = {p["as_of"] for p in payload.get("rotation_history") or []}
    assert "2026-08-28" not in dates, (
        "the August snapshot has a different eligible cohort and must not leak in"
    )
    assert "2026-08-27" not in dates, "Sectors dates must never appear in rotation history"


# ── panel validation invariants ──────────────────────────────────


def test_panel_validation_passes_every_check(validation: dict) -> None:
    assert validation.get("status") == "PASS"
    for name, check in validation["checks"].items():
        assert check.get("status") in {"PASS", "DISCLOSURE"}, f"{name}: {check.get('status')}"


def test_benchmark_validated_against_official_sources(validation: dict) -> None:
    workbook = validation["checks"]["benchmark_vs_official_workbook"]
    assert workbook["dates_matched"] >= 150, (
        f"expected >= 150 official sessions matched, got {workbook['dates_matched']}"
    )
    assert workbook["max_abs_diff"] <= 0.01
    assert workbook["mismatches"] == []
    # The YTD baseline session must be verified against the official close.
    baseline = workbook["representative"]["ytd_baseline_2025-12-30"]
    assert baseline["official"] == 8646.94
    assert abs(baseline["panel"] - 8646.94) <= 0.01


def test_benchmark_validated_against_daily_statistics_pdfs(validation: dict) -> None:
    pdfs = validation["checks"]["benchmark_vs_daily_statistics_pdfs"]
    assert pdfs["dates_checked"] >= 10
    assert pdfs["parse_errors"] == []
    sessions = {row["session"] for row in pdfs["rows"]}
    assert "2026-10-02" in sessions
    for row in pdfs["rows"]:
        assert row["abs_diff"] <= 0.01, f"{row['session']}: diff {row['abs_diff']}"
        assert abs(row["official_close_computed"] - row["official_close_printed"]) <= 0.001


def test_stocks_validated_against_official_stock_summary(validation: dict) -> None:
    stocks = validation["checks"]["stocks_vs_official_stock_summary"]
    assert stocks["official_date"] == "2026-10-02"
    assert stocks["official_date_matches_panel"] is True
    assert stocks["mismatched"] == []
    assert stocks["match_rate"] >= 0.95
    assert stocks["max_abs_diff_idr"] <= 1.0


def test_coverage_reconciliation_keeps_populations_distinct(validation: dict) -> None:
    coverage = validation["checks"]["coverage_reconciliation"]
    assert coverage["official_stock_summary_codes"] == 963
    assert coverage["sectors_snapshot_registry_codes"] == 962
    assert coverage["universe_requested"] == 54
    assert coverage["downloaded"] == 53
    assert coverage["failed_symbols"] == ["WSKT.JK"]
    assert coverage["ytd_baseline_present"] == 53


def test_panel_integrity_and_units_are_declared(validation: dict) -> None:
    integrity = validation["checks"]["panel_integrity"]
    assert integrity["duplicate_ticker_date_rows"] == 0
    assert integrity["nonpositive_price_rows"] == 0
    assert integrity["ytd_baseline_date"] == "2025-12-30"
    assert integrity["ytd_baseline_tickers"] == 53
    assert integrity["latest_session"] == "2026-10-02"
    units = integrity["units"]
    assert "IDR" in units["price"]
    assert "shares" in units["volume"]
    basis = integrity["price_basis"]
    assert "adjusted_close" in basis["stocks"]
    assert basis["benchmark"] == "close"


def test_corporate_actions_disclosed(validation: dict) -> None:
    corp = validation["checks"]["corporate_actions"]
    tickers = corp["tickers_with_adjusted_close_divergence"]
    assert len(tickers) > 20, "dividend-affected tickers must be disclosed, not hidden"
    assert corp["status"] == "DISCLOSURE"


# ── frontend contracts (pure functions, exercised through bun/tsx) ──


def _run_tsx(script: str) -> str:
    import subprocess

    result = subprocess.run(
        ["bun", "x", "tsx", "-e", script],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        timeout=60,
    )
    assert result.returncode == 0, f"tsx failed: {result.stderr}"
    return result.stdout.strip()


def test_pick_latest_entry_prefers_newest_as_of_over_provider_brand() -> None:
    out = _run_tsx(
        'import {pickLatestEntry} from "./app/web/src/data/snapshotSelection.ts"; '
        'const entries = ['
        '  {snapshot_id: "snap_sectors_2026-08-27", as_of: "2026-08-27", provider_mode: "SECTORS_LIVE"},'
        '  {snapshot_id: "snap_public_2026-10-02", as_of: "2026-10-02", provider_mode: "PUBLIC_PROTOTYPE"},'
        ']; '
        'console.log(JSON.stringify(pickLatestEntry(entries)?.snapshot_id));'
    )
    assert out == '"snap_public_2026-10-02"', (
        f"newest as_of must win regardless of provider mode, got {out}"
    )


def test_pick_latest_entry_tie_breaks_deterministically_and_handles_empty() -> None:
    out = _run_tsx(
        'import {pickLatestEntry} from "./app/web/src/data/snapshotSelection.ts"; '
        'const tie = ['
        '  {snapshot_id: "snap_b", as_of: "2026-10-02"},'
        '  {snapshot_id: "snap_a", as_of: "2026-10-02"},'
        ']; '
        'console.log(JSON.stringify([pickLatestEntry(tie)?.snapshot_id, pickLatestEntry([])]));'
    )
    assert out == '["snap_b",null]', f"tie-break/empty contract changed: {out}"


def test_build_rotation_tail_requires_three_real_dated_points() -> None:
    out = _run_tsx(
        'import {buildRotationTrail, MIN_ROTATION_TRAIL_POINTS} from "./app/web/src/data/rotation.ts"; '
        'const two = ['
        '  {as_of: "2026-09-11", group_excess_return_ytd: 1, relative_momentum: 2},'
        '  {as_of: "2026-09-18", group_excess_return_ytd: 3, relative_momentum: 4},'
        ']; '
        'const three = [...two, {as_of: "2026-09-25", group_excess_return_ytd: 5, relative_momentum: 6}]; '
        'console.log(JSON.stringify({'
        '  min: MIN_ROTATION_TRAIL_POINTS,'
        '  insufficient: buildRotationTrail(two, 2).length,'
        '  zero: buildRotationTrail(three, 0).length,'
        '  tail1: buildRotationTrail(three, 1).map(p => p.asOf),'
        '  tail2: buildRotationTrail(three, 2).map(p => p.asOf),'
        '}));'
    )
    import json as _json

    parsed = _json.loads(out)
    assert parsed["min"] == 3
    assert parsed["insufficient"] == 0, "a two-point series must not draw a trail"
    assert parsed["zero"] == 0, "tail length 0 must draw nothing"
    assert parsed["tail1"] == ["2026-09-18", "2026-09-25"]
    assert parsed["tail2"] == ["2026-09-11", "2026-09-18", "2026-09-25"]


def test_build_rotation_tail_drops_points_missing_either_axis() -> None:
    out = _run_tsx(
        'import {buildRotationTrail} from "./app/web/src/data/rotation.ts"; '
        'const history = ['
        '  {as_of: "2026-09-04", group_excess_return_ytd: 1, relative_momentum: 1},'
        '  {as_of: "2026-09-11", group_excess_return_ytd: 2, relative_momentum: null},'
        '  {as_of: "2026-09-18", group_excess_return_ytd: 3, relative_momentum: 3},'
        '  {as_of: "2026-09-25", group_excess_return_ytd: 4, relative_momentum: 4},'
        ']; '
        'console.log(JSON.stringify(buildRotationTrail(history, 5).map(p => p.asOf)));'
    )
    import json as _json

    parsed = _json.loads(out)
    assert parsed == ["2026-09-04", "2026-09-18", "2026-09-25"], (
        f"points without a momentum axis must be dropped, not interpolated: {parsed}"
    )


def test_rotation_history_satisfies_the_tail_gate(payload: dict) -> None:
    """The persisted history must actually clear the frontend tail gate."""
    history = payload.get("rotation_history") or []
    by_group: dict[str, int] = {}
    for point in history:
        by_group[point["group_id"]] = by_group.get(point["group_id"], 0) + 1
    assert by_group, "no rotation history to gate on"
    assert min(by_group.values()) >= 3, (
        f"every group needs >= 3 dated points: {by_group}"
    )