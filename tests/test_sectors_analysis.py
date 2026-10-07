import hashlib
import json
from pathlib import Path

import pytest

from idx_leadership.models.enums import DiffusionStateV2
from idx_leadership.signals.diffusion_v2 import classify_diffusion_v2
from scripts.build_sectors_analysis import build
from scripts.verify_sectors_analysis_oracle import oracle_state, verify


ROOT = Path(__file__).resolve().parents[1]
RELEASES = ROOT / "app/web/public/releases"


def _active_asset(file_id):
    pointer = json.loads((RELEASES / "active.json").read_text())
    release_dir = RELEASES / pointer["active"]["release_id"]
    manifest = json.loads((release_dir / "manifest.json").read_text())
    entry = next(row for row in manifest["additional_files"] if row["file_id"] == file_id)
    return release_dir / entry["path"]


SAMPLE = _active_asset("sectors_recorded_sample")
SELECTION_MARKET = _active_asset("sectors_selection_market")


def _write_selection_plan(tmp_path):
    sample = json.loads(SAMPLE.read_text())
    stocks = {}
    for row in sample["stocks"]:
        stocks.setdefault(row["sector"], []).append(row["ticker"])
    plan = {
        "market_release_source": {"sha256": hashlib.sha256(SELECTION_MARKET.read_bytes()).hexdigest()},
        "selection_release_id": sample["selection"]["membership_release_id"],
        "selections": {sector: {"selected": sorted(tickers)} for sector, tickers in stocks.items()},
    }
    path = tmp_path / "selection-plan.json"
    path.write_text(json.dumps(plan))
    return path


def test_analysis_inherits_original_source_hash_and_discloses_gaps(tmp_path):
    output = tmp_path / "analysis.json"
    report = build(sample_path=SAMPLE, selection_market_path=SELECTION_MARKET, out=output)
    asset = json.loads(output.read_text())

    assert report["status"] == "PASS"
    assert asset["sources"]["selection_market_source_sha256"] == "f02edbe114d38543a1c13ac64df7b5b469e941e7859b15133d79e3a164cdf1c3"
    assert asset["sources"]["recorded_sample_sha256"] == "9e9c8540e676eed99acd4dbfe4bdf86534e1a3a9a6e6575e3d3ce99281390f20"
    assert asset["selection"]["retrospective"] is True
    assert asset["ytd"]["status"] == "NOT_AVAILABLE"
    assert len(asset["daily"]) == 21
    assert len(asset["weekly"]) == 5
    assert all(row["eligible_contributors"] >= 5 for row in asset["daily"][-1]["groups"])

    infrastructure = next(row for row in asset["daily"][-1]["groups"] if row["sector"] == "Infrastructures")
    cdia = next(row for row in infrastructure["contributors"] if row["ticker"] == "CDIA.JK")
    assert cdia["returns"]["5d"]["exclusion_reason"] == "MECHANICAL_ACTION_DIVIDEND_2026-10-01"
    assert infrastructure["concentration_v2"]["requested_constituent_count"] == infrastructure["eligible_contributors"]
    technology = next(row for row in asset["daily"][-1]["groups"] if row["sector"] == "Technology")
    mlpt = next(row for row in technology["contributors"] if row["ticker"] == "MLPT.JK")
    assert mlpt["returns"]["60d"]["exclusion_reason"] == "MECHANICAL_ACTION_STOCK_SPLIT_2026-07-21"


def test_corrupted_selection_evidence_is_rejected(tmp_path):
    market = json.loads(SELECTION_MARKET.read_text())
    market["records"][0]["market_cap"] = -1
    corrupted = tmp_path / "market.json"
    corrupted.write_text(json.dumps(market))

    with pytest.raises(ValueError, match="hash does not match"):
        build(sample_path=SAMPLE, selection_market_path=corrupted, out=tmp_path / "analysis.json")


def test_corrupted_frozen_selection_plan_is_rejected(tmp_path):
    plan_path = _write_selection_plan(tmp_path)
    plan = json.loads(plan_path.read_text())
    sector = next(iter(plan["selections"]))
    plan["selections"][sector]["selected"][0] = "ZZZZ.JK"
    corrupted = tmp_path / "plan.json"
    corrupted.write_text(json.dumps(plan))

    with pytest.raises(ValueError, match="frozen selection plan"):
        build(sample_path=SAMPLE, selection_market_path=SELECTION_MARKET,
              selection_plan_path=corrupted, out=tmp_path / "analysis.json")


@pytest.mark.parametrize(
    ("previous_count", "current_count", "expected"),
    [
        (3, 4, DiffusionStateV2.BROADENING_FRAGILE),
        (2, 4, DiffusionStateV2.BROADENING_FIRM),
    ],
)
def test_six_stock_diffusion_distinguishes_one_and_two_name_changes(previous_count, current_count, expected):
    assert oracle_state(current_count - previous_count, 6) == expected.value
    state = classify_diffusion_v2(
        breadth_current=current_count / 6 * 100,
        breadth_previous=previous_count / 6 * 100,
        group_size=6,
        breadth_change_count=current_count - previous_count,
    )
    assert state is expected


def test_diffusion_uses_the_same_available_names_at_both_replay_dates(tmp_path):
    output = tmp_path / "analysis.json"
    build(sample_path=SAMPLE, selection_market_path=SELECTION_MARKET, out=output)
    asset = json.loads(output.read_text())
    previous = asset["daily"][-2]
    current = asset["daily"][-1]
    assert current["previous_date"] == previous["date"]
    for group in current["groups"]:
        members = next(row for row in previous["groups"] if row["sector"] == group["sector"])
        current_valid = {
            row["ticker"] for row in group["contributors"]
            if row["returns"]["20d"]["exclusion_reason"] is None
        }
        previous_valid = {
            row["ticker"] for row in members["contributors"]
            if row["returns"]["20d"]["exclusion_reason"] is None
        }
        paired = current_valid & previous_valid
        assert group["comparison_cohorts"]["diffusion_tickers"] == sorted(paired)
        assert group["diffusion"]["eligible_count"] == len(paired) if len(paired) >= 5 else group["diffusion"]["eligible_count"] == 0


def test_full_analysis_matches_independent_close_and_integer_count_oracle(tmp_path):
    output = tmp_path / "analysis.json"
    build(sample_path=SAMPLE, selection_market_path=SELECTION_MARKET, out=output)

    report = verify(sample_path=SAMPLE, analysis_path=output)

    assert report["status"] == "PASS"
    assert report["mismatch_count"] == 0
    assert report["counts"]["member_window_values"] == 5_148
    assert report["counts"]["diffusion_states_and_cohorts"] == 286


def test_missing_ytd_baseline_stays_unavailable(tmp_path):
    output = tmp_path / "analysis.json"
    build(sample_path=SAMPLE, selection_market_path=SELECTION_MARKET, out=output)
    asset = json.loads(output.read_text())

    assert asset["ytd"]["status"] == "NOT_AVAILABLE"
    report = verify(sample_path=SAMPLE, analysis_path=output)
    assert report["status"] == "PASS"


def test_ytd_uses_matching_baselines_actions_and_minimum_contributor_floor(tmp_path):
    sample = json.loads(SAMPLE.read_text())
    baseline_path = tmp_path / "baseline.json"
    baseline_date = "2025-12-30"
    baseline = {
        "schema_version": "sectors-ytd-baseline-v1",
        "as_of": sample["as_of"],
        "status": "PASS",
        "baseline_date": baseline_date,
        "ihsg": {"date": baseline_date, "close": 100.0, "price_basis": "close"},
        "stocks": [{"ticker": row["ticker"], "date": baseline_date,
                    "close": 100.0 + index, "source_response_sha256": "a" * 64}
                   for index, row in enumerate(sample["stocks"])],
        "gaps": [],
    }
    baseline_path.write_text(json.dumps(baseline))
    output = tmp_path / "analysis.json"
    build(sample_path=SAMPLE, selection_market_path=SELECTION_MARKET,
          ytd_baseline_path=baseline_path, out=output)

    report = verify(sample_path=SAMPLE, analysis_path=output, ytd_baseline_path=baseline_path)
    assert report["status"] == "PASS"
    assert report["counts"]["ytd_contributor_values"] == 66
    assert report["counts"]["ytd_group_aggregates"] == 11

    asset = json.loads(output.read_text())
    transportation = next(row for row in asset["ytd"]["groups"]
                          if row["sector"] == "Transportation & Logistic")
    elpi = next(row for row in transportation["contributors"] if row["ticker"] == "ELPI.JK")
    assert elpi["exclusion_reason"].startswith("MECHANICAL_ACTION_RIGHT_ISSUE_")
    assert transportation["eligible_contributors"] < 5
    assert transportation["status"] == "UNCONFIRMED_BELOW_FIVE_CONTRIBUTORS"

    asset["ytd"]["groups"][0]["contributors"][0]["return_pct"] += 1
    output.write_text(json.dumps(asset))
    corrupted = verify(sample_path=SAMPLE, analysis_path=output, ytd_baseline_path=baseline_path)
    assert corrupted["status"] == "FAIL"
    assert any(row["field"] == "ytd.contributors.return_pct" for row in corrupted["mismatches"])
