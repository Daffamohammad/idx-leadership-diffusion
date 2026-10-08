"""Hermetic replay and publication regressions; no ignored inputs are required."""
from __future__ import annotations

import copy
import json
import math
from pathlib import Path

import pandas as pd
import pytest

from idx_leadership.data.rotation_replay import AXES, KINDS, replay, validate_asset
from scripts.build_rotation_replay import load_ledger, publish, sha
from tests.test_public_refresh_chain import _run_tsx


def independent_axes(prices, benchmark, tickers, session):
    """Direct arithmetic independent of the canonical feature/replay functions."""
    market = benchmark[benchmark.date <= session].set_index("date").close
    result = {}
    for axis, offset in zip(AXES, (None, 20, 60)):
        values = []
        for ticker in tickers:
            series = prices[(prices.ticker == ticker) & (prices.date <= session)].set_index("date").adjusted_close
            start = "2025-12-30" if offset is None else market.index[-offset - 1]
            values.append((series.loc[session] / series.loc[start] - market.loc[session] / market.loc[start]) * 100)
        result[axis] = sum(values) / len(values)
    return result


@pytest.fixture
def inputs():
    dates = ["2025-12-30", *pd.bdate_range("2026-01-02", "2026-10-02").strftime("%Y-%m-%d")]
    prices = pd.DataFrame([dict(ticker=t, date=d, close=100 + i * slope, adjusted_close=100 + i * slope, volume=1_000_000)
                           for t, slope in (("AAA.JK", 1.0), ("BBB.JK", .3)) for i, d in enumerate(dates)])
    benchmark = pd.DataFrame([dict(date=d, close=100 + i * .1) for i, d in enumerate(dates)])
    source = dict(observed_on="2026-08-28", published_on="2026-08-28", available_on="2026-08-31",
                  publication_evidence="Synthetic dated announcement", sha256="a" * 64)
    records = [dict(ticker=t, vendor_ticker=t, source="fixture", sector="Test", subsector="Test", industry="Test", group_id="Test", listing_board="Main",
                    source_as_of="2026-08-28") for t in ("AAA.JK", "BBB.JK")]
    version = dict(effective_from="2026-08-31", source_ids=["test"], records=records)
    taxonomies = {k: [dict(effective_from="2026-08-31", source_ids=["test"], method_version="test-v1",
                           groups={"Test": ["AAA.JK", "BBB.JK"]})] for k in KINDS}
    endpoint = dict(name="Test", **independent_axes(prices, benchmark, ["AAA.JK", "BBB.JK"], "2026-10-02"))
    return dict(prices=prices, benchmark=benchmark, sessions=[d for d in dates if d >= "2026-09-01"],
                sources={"test": source}, universes=[version], taxonomies=taxonomies,
                endpoints={k: {"Test": dict(endpoint)} for k in KINDS}, snapshot_id="test", as_of="2026-10-02", gaps=set())


def test_replay_all_taxonomies_matches_independent_arithmetic(inputs):
    result = replay(**inputs)
    validate_asset(result, inputs["endpoints"])
    for kind in KINDS:
        group = result["taxonomies"][kind]["Test"]
        assert group["daily_available"] and group["weekly_available"]
        for point in (group["segments"][0]["points"][0], group["segments"][0]["points"][12], group["segments"][0]["points"][-1]):
            expected = independent_axes(inputs["prices"], inputs["benchmark"], ["AAA.JK", "BBB.JK"], point["as_of"])
            assert {a: point[a] for a in AXES} == pytest.approx(expected)
            assert point["relative_momentum"] == pytest.approx(expected[AXES[1]] - expected[AXES[2]])


@pytest.mark.parametrize("publication", [None, "2026-10-05"])
def test_future_or_unknown_publication_never_backdated(inputs, publication):
    inputs["sources"]["test"].update(published_on=publication, available_on=publication)
    result = replay(**inputs)
    for groups in result["taxonomies"].values():
        assert not groups["Test"]["segments"]
        assert not groups["Test"]["daily_available"]


def test_publication_bound_starts_history_after_observation(inputs):
    inputs["sources"]["test"].update(published_on="2026-09-16", available_on="2026-09-17")
    result = replay(**inputs)
    assert result["taxonomies"]["KONGLO"]["Test"]["segments"][0]["sessions"][0] == "2026-09-17"


def test_membership_change_splits_segment_without_changing_other_taxonomies(inputs):
    inputs["taxonomies"]["KONGLO"].append(dict(effective_from="2026-10-01", source_ids=["test"],
                                              method_version="test-v1", groups={"Test": ["AAA.JK"]}))
    inputs["endpoints"]["KONGLO"]["Test"].update(independent_axes(inputs["prices"], inputs["benchmark"], ["AAA.JK"], inputs["as_of"]))
    result = replay(**inputs)
    group = result["taxonomies"]["KONGLO"]["Test"]
    assert len(group["segments"]) == 2
    assert not group["daily_available"] and not group["weekly_available"]
    assert result["taxonomies"]["SECTOR"]["Test"]["weekly_available"]


def test_eligibility_change_is_a_new_contract(inputs):
    newer = copy.deepcopy(inputs["universes"][0]); newer["effective_from"] = "2026-09-18"
    newer["records"][1]["listing_board"] = "Watchlist"
    inputs["universes"].append(newer)
    for kind in KINDS:
        inputs["endpoints"][kind]["Test"].update(independent_axes(inputs["prices"], inputs["benchmark"], ["AAA.JK"], inputs["as_of"]))
    result = replay(**inputs)
    segments = result["taxonomies"]["THEMES"]["Test"]["segments"]
    assert len(segments) == 2
    assert segments[0]["group_eligible_ticker_set_hash"] != segments[1]["group_eligible_ticker_set_hash"]


def test_unrelated_eligibility_change_does_not_disable_stable_group(inputs):
    newer = copy.deepcopy(inputs["universes"][0]); newer["effective_from"] = "2026-10-02"
    newer["records"][1]["listing_board"] = "Watchlist"
    inputs["universes"].append(newer)
    for kind in KINDS:
        inputs["taxonomies"][kind][0]["groups"]["Test"] = ["AAA.JK"]
        inputs["endpoints"][kind]["Test"].update(independent_axes(inputs["prices"], inputs["benchmark"], ["AAA.JK"], inputs["as_of"]))
    result = replay(**inputs)
    group = result["taxonomies"]["THEMES"]["Test"]
    assert group["weekly_available"] and len(group["segments"]) == 1
    points = group["segments"][0]["points"]
    assert points[0]["universe_eligible_ticker_set_hash"] != points[-1]["universe_eligible_ticker_set_hash"]


def test_capture_upper_bound_is_distinct_from_unknown_publication(inputs):
    inputs["sources"]["test"].update(published_on=None, publication_basis="capture_upper_bound")
    assert replay(**inputs)["taxonomies"]["SECTOR"]["Test"]["daily_available"]


def test_ledger_capture_cannot_be_backdated(tmp_path):
    capture = tmp_path / "capture.json"
    capture.write_text(json.dumps(dict(listing_registry=dict(listing_source=dict(captured_at="20260829T004355Z")))))
    ledger = tmp_path / "ledger.json"
    ledger.write_text(json.dumps(dict(schema_version="rotation-source-ledger-v1", sources={"capture": dict(
        path="capture.json", sha256=sha(capture), observed_on="2026-08-27", published_on=None,
        publication_basis="capture_upper_bound", available_on="2026-08-28", publication_evidence="capture")}, universes=[], taxonomies={})))
    with pytest.raises(ValueError, match="predates"): load_ledger(ledger, tmp_path)


def test_konglo_capture_uses_hash_bound_import_date(tmp_path):
    ownership = tmp_path / "raw" / "ownership.xlsx"
    ownership.parent.mkdir(parents=True)
    ownership.write_bytes(b"captured ownership register")
    membership = tmp_path / "config" / "konglo.yaml"
    membership.parent.mkdir(parents=True)
    membership.write_text("taxonomy_kind: KONGLO\nmemberships: []\n")
    inventory = tmp_path / "data" / "research" / "acquisitions" / "inventory.jsonl"
    inventory.parent.mkdir(parents=True)
    inventory.write_text(json.dumps({
        "schema_version": "idx-acquisition-inventory-v1",
        "acquisition_id": "ownership-2026-10-05",
        "retrieved_at": "2026-10-05T03:00:00Z",
        "observation_start": "2026-09-30",
        "observation_end": "2026-09-30",
        "availability_basis": "capture_upper_bound",
        "available_on": "2026-10-05",
        "captured_file": {
            "path": "raw/ownership.xlsx", "sha256": sha(ownership),
            "bytes": ownership.stat().st_size, "hash_scope": "captured_file_bytes",
        },
    }) + "\n")
    ledger = tmp_path / "ledger.json"
    ledger.write_text(json.dumps({
        "schema_version": "rotation-source-ledger-v1",
        "acquisition_inventory": "data/research/acquisitions/inventory.jsonl",
        "sources": {
            "ownership_capture": {
                "path": "raw/ownership.xlsx", "sha256": sha(ownership),
                "observed_on": "2026-09-30", "published_on": None,
                "available_on": "2026-10-05", "publication_basis": "capture_upper_bound",
                "publication_evidence": "hash-bound local capture", "acquisition_id": "ownership-2026-10-05",
            },
            "konglo_membership": {
                "path": "config/konglo.yaml", "sha256": sha(membership),
                "observed_on": "2026-09-30", "published_on": None,
                "available_on": "2026-10-05", "publication_basis": "capture_upper_bound",
                "publication_evidence": "derived from captured ownership register",
                "capture_source_id": "ownership_capture", "taxonomy_kind": "KONGLO",
                "derivation": "ownership_register_threshold_v1",
                "derivation_input_sha256": sha(ownership),
            },
        },
        "universes": [],
        "taxonomies": {"KONGLO": [{
            "effective_from": "2026-10-05", "config_source_id": "konglo_membership",
            "source_ids": ["konglo_membership", "ownership_capture"],
        }]},
    }))
    _, _, loaded = load_ledger(ledger, tmp_path)
    assert loaded["KONGLO"][0]["effective_from"] == "2026-10-05"


@pytest.mark.parametrize("defect", ["duplicate", "nan", "quarantine", "missing_session", "endpoint"])
def test_invalid_replay_refused(inputs, defect):
    if defect == "duplicate": inputs["prices"] = pd.concat([inputs["prices"], inputs["prices"].iloc[:1]])
    if defect == "nan": inputs["prices"].loc[0, "adjusted_close"] = float("nan")
    if defect == "quarantine": inputs["gaps"] = {"AAA.JK"}
    if defect == "missing_session": inputs["sessions"].pop(3)
    if defect == "endpoint": inputs["endpoints"]["SECTOR"]["Test"][AXES[0]] += 1
    with pytest.raises(ValueError): replay(**inputs)


def test_missing_security_session_breaks_history_and_never_fills(inputs):
    inputs["prices"] = inputs["prices"][inputs["prices"].date != "2026-09-17"]
    result = replay(**inputs)
    group = result["taxonomies"]["SECTOR"]["Test"]
    assert group["segments"][0]["sessions"][-1] == "2026-09-16"
    assert group["current_segment_id"] is None and not group["daily_available"]


def test_missing_ytd_baseline_keeps_return_points_without_ytd(inputs):
    inputs["prices"] = inputs["prices"][inputs["prices"].date != "2025-12-30"]
    for groups in inputs["endpoints"].values():
        groups["Test"] = {**groups["Test"], "group_excess_return_ytd": None}
    result = replay(**inputs)
    segment = result["taxonomies"]["SECTOR"]["Test"]["segments"][0]
    assert segment["sessions"]
    last = segment["points"][-1]
    assert math.isfinite(last["group_excess_return_20d"])
    assert math.isfinite(last["group_excess_return_60d"])
    assert last["group_excess_return_ytd"] is None
    validate_asset(result, inputs["endpoints"])


def test_unknown_source_hash_refuses_ledger(tmp_path):
    source = tmp_path / "input.yaml"; source.write_text("universe: []\n")
    ledger = tmp_path / "ledger.json"
    ledger.write_text(json.dumps(dict(schema_version="rotation-source-ledger-v1", sources={"test": dict(path="input.yaml", sha256="f" * 64)}, universes=[], taxonomies={})))
    with pytest.raises(ValueError, match="source hash"): load_ledger(ledger, tmp_path)


def test_rotation_publisher_refuses_independent_index_switch(inputs, tmp_path):
    payload = replay(**inputs)
    public = tmp_path / "public"; (public / "market").mkdir(parents=True); (public / "snapshots").mkdir()
    snapshot = dict(snapshot_id="test", as_of=inputs["as_of"], groups=[dict(group_id="Test", group_name="Test", **inputs["endpoints"]["SECTOR"]["Test"])],
                    taxonomy_views={k: dict(taxonomy_kind=k, groups=[dict(taxonomy_group_id="Test", taxonomy_group_name="Test", **{a.removeprefix('group_'): v for a,v in inputs['endpoints'][k]['Test'].items() if a in AXES})]) for k in ('KONGLO','THEMES')})
    path = public / "snapshots/test.json"; path.write_text(json.dumps(snapshot))
    payload["provenance"] = dict(snapshot_sha256=sha(path))
    index = public / "market/index.json"; index.write_text(json.dumps(dict(snapshot_id="test", as_of=inputs["as_of"], assets={})))
    original = index.read_bytes(); asset_names = set((public / "market").iterdir())
    with pytest.raises(ValueError, match="complete five-family"):
        publish(payload, public)
    payload["taxonomies"]["THEMES"]["Test"]["segments"][0]["points"][3]["source_ids"] = []
    with pytest.raises(ValueError, match="complete five-family"):
        publish(payload, public)
    assert index.read_bytes() == original and set((public / "market").iterdir()) == asset_names


def test_frontend_sampling_endpoint_and_per_group_gates(inputs, tmp_path):
    result = replay(**inputs)
    good = result["taxonomies"]["THEMES"]["Test"]
    result["taxonomies"]["THEMES"]["Missing"] = dict(good, segments=[], current_segment_id=None, reason="No publication evidence")
    path = tmp_path / "replay.json"; path.write_text(json.dumps(result))
    endpoint = inputs["endpoints"]["THEMES"]["Test"]
    script = '''
      import {readFileSync} from 'node:fs';
      import {replaySelection} from './app/web/src/data/rotationReplay.ts';
      const asset = JSON.parse(readFileSync(PATH, 'utf8'));
      const endpoint = ENDPOINT;
      const daily = replaySelection(asset, 'THEMES', 'Test', 'daily', endpoint);
      const weekly = replaySelection(asset, 'THEMES', 'Test', 'weekly', endpoint);
      if (daily.points.length !== asset.sessions.length || weekly.points.length !== 5) throw Error('cadence');
      if (weekly.points.some(p => !daily.points.some(d => JSON.stringify(p) === JSON.stringify(d)))) throw Error('coordinates changed');
      if (replaySelection(asset, 'THEMES', 'Missing', 'daily', endpoint).points.length) throw Error('missing enabled');
      if (replaySelection(asset, 'THEMES', 'Test', 'daily', {...endpoint, relativeStrength: 999}).points.length) throw Error('endpoint');
      asset.taxonomies.THEMES.Test.segments[0].points[0].source_ids = [];
      if (replaySelection(asset, 'THEMES', 'Test', 'daily', endpoint).points.length) throw Error('source');
      console.log('ok');
    '''.replace('PATH', json.dumps(str(path))).replace('ENDPOINT', json.dumps(dict(relativeStrength=endpoint[AXES[0]], excess20d=endpoint[AXES[1]], excess60d=endpoint[AXES[2]])))
    assert _run_tsx(script) == "ok"


def test_cli_rejects_stale_panel_without_replacing_report(tmp_path, monkeypatch):
    from tests.test_refresh_tool_safety import _panel_fixture
    from scripts.validate_public_panel import _check_panel_integrity
    from scripts.build_rotation_replay import main
    panel = _panel_fixture(tmp_path)
    prices = pd.read_csv(panel / "prices.csv"); benchmark = pd.read_csv(panel / "benchmark.csv")
    for frame in (prices, benchmark): frame["date"] = pd.to_datetime(frame["date"]).dt.date
    manifest = json.loads((panel / "source_manifest.json").read_text())
    integrity = _check_panel_integrity(prices, benchmark, manifest, panel)
    assert integrity["status"] == "PASS"
    report = tmp_path / "validation.json"; report.write_text(json.dumps(dict(status="PASS", checks=dict(panel_integrity=integrity))))
    ledger = tmp_path / "ledger.json"; ledger.write_text(json.dumps(dict(schema_version="rotation-source-ledger-v1", sources={}, universes=[], taxonomies={})))
    snapshot = tmp_path / "snapshot.json"; snapshot.write_text(json.dumps(dict(as_of="2026-10-02", complete=True)))
    provenance = tmp_path / "provenance.json"; provenance.write_text(json.dumps(dict(panel_files={n: sha(panel/n) for n in ('prices.csv','benchmark.csv')})))
    output = tmp_path / "output.json"; output.write_bytes(b"previous verified report")
    prices.loc[0, "close"] += 1
    prices.to_csv(panel / "prices.csv", index=False)
    monkeypatch.setattr("sys.argv", ["build_rotation_replay", "--ledger", str(ledger), "--source-root", str(tmp_path),
        "--panel", str(panel), "--validation", str(report), "--snapshot", str(snapshot), "--snapshot-provenance", str(provenance), "--out", str(output)])
    assert main() == 1
    assert output.read_bytes() == b"previous verified report"


def test_served_replay_is_bound_to_snapshot_and_source_ledger():
    from idx_leadership.data.rotation_replay import endpoints_from_snapshot
    root = Path(__file__).resolve().parents[1]
    public = root / "app/web/public"
    index = json.loads((public / "market/index.json").read_text())
    asset = index["assets"]["rotation"]
    path = public / asset["path"].lstrip("/")
    assert sha(path) == asset["sha256"]
    payload = json.loads(path.read_text())
    snapshot = public / "snapshots" / f'{index["snapshot_id"]}.json'
    assert payload["snapshot_id"] == index["snapshot_id"]
    assert payload["provenance"]["snapshot_sha256"] == sha(snapshot)
    assert payload["provenance"]["ledger_sha256"] == sha(root / "docs/rotation-history-handoff/SOURCE_LEDGER.json")
    validate_asset(payload, endpoints_from_snapshot(json.loads(snapshot.read_text())))
    load_ledger(root / "docs/rotation-history-handoff/SOURCE_LEDGER.json", root)
    assert payload["coverage"]["SECTOR"]["daily"] > 0
    assert payload["coverage"]["THEMES"]["weekly"] > 0
    assert payload["coverage"]["KONGLO"]["observations"] == 0
