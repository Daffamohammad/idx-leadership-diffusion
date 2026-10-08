import math

import pandas as pd
import pytest

from scripts.group_readings import group_readings, phase
from scripts.business_groups import legal_name, reconcile


def panel():
    dates = pd.bdate_range("2026-01-05", periods=110).strftime("%Y-%m-%d").tolist()
    prices = pd.DataFrame({day: [100 + j * (i + 1) for i in range(6)] for j, day in enumerate(dates)}, index=list("ABCDEF"))
    benchmark = pd.Series(100.0, index=dates)
    return dates, prices, benchmark


def test_horizons_have_independent_cohorts_and_missing_ytd_does_not_suppress_returns():
    dates, prices, benchmark = panel()
    prices.loc["F", dates[-21]] = math.nan
    result = group_readings(list("ABCDEF"), prices, benchmark, [dates[-1]], [dates[-1]], set("ABCDEF"))
    point = result["weekly"][0]
    assert result["cohorts"]["20d"] == list("ABCDE")
    assert result["cohorts"]["60d"] == list("ABCDEF")
    assert result["cohorts"]["ytd"] == []
    assert point["excess_return_ytd"] is None
    assert point["excess_return_20d"] is not None and point["excess_return_60d"] is not None
    raw = [(prices.loc[name, dates[-1]] / prices.loc[name, dates[-21]] - 1) * 100 for name in "ABCDE"]
    assert point["concentration_top3_pct"] == pytest.approx(sum(sorted(raw, reverse=True)[:3]) / sum(raw) * 100)
    assert [row["ticker"] for row in point["concentration_detail"]] == sorted("ABCDE", key=lambda n: prices.loc[n,dates[-1]] / prices.loc[n,dates[-21]], reverse=True)


def test_descriptive_coordinates_survive_below_five_without_a_confirmed_signal():
    dates, prices, benchmark = panel()
    result = group_readings(["A"], prices, benchmark, dates[-5:], [dates[-1]], {"A"})
    point = result["weekly"][0]
    assert point["map_x_60d"] is not None and point["relative_momentum"] is not None
    assert point["map_contributors"] == 1
    assert point["leadership"] == point["diffusion_v2"] == "UNCONFIRMED"
    assert point["rotation_phase"] == phase(point["map_x_60d"], point["relative_momentum"])


def test_diffusion_retains_fixed_names_when_one_date_is_missing_a_reading():
    dates, prices, benchmark = panel()
    prices.loc["F", dates[-3]] = math.nan
    result = group_readings(list("ABCDEF"), prices, benchmark, dates[-5:], [dates[-5], dates[-1]], set("ABCDEF"))
    assert result["cohorts"]["20d"] == list("ABCDE")
    assert all(point["breadth_denominator"] == 5 for point in result["daily"])
    assert result["weekly"][-1]["breadth_change_count"] == result["weekly"][-1]["breadth_count"] - result["weekly"][0]["breadth_count"]


@pytest.mark.parametrize("prior_count,expected", [(3,"BROADENING_FRAGILE"),(2,"BROADENING_FIRM")])
def test_calculated_six_name_participation_changes_use_integer_counts(prior_count,expected):
    dates, prices, benchmark = panel()
    prices.loc[:,:] = 100.0
    prices[dates[-2]] = [101 if i < prior_count else 99 for i in range(6)]
    prices[dates[-1]] = [102 if i < 4 else 98 for i in range(6)]
    result = group_readings(list("ABCDEF"),prices,benchmark,dates[-2:],dates[-2:],set("ABCDEF"))
    current = result["weekly"][-1]
    assert current["breadth_count"] == 4 and current["breadth_denominator"] == 6
    assert current["breadth_change_count"] == 4 - prior_count
    assert current["diffusion_v2"] == expected


@pytest.mark.parametrize("x,y,expected", [(1,1,"LEADING"),(-1,1,"IMPROVING"),(-1,-1,"LAGGING"),(1,-1,"WEAKENING"),(None,0,"UNAVAILABLE"),(math.nan,0,"UNAVAILABLE")])
def test_rotation_phase_is_only_displayed_coordinates(x,y,expected):
    assert phase(x,y) == expected


def test_legal_issuer_join_preserves_identity_and_never_matches_shared_surnames():
    assert legal_name("PT Example Holdings Tbk.") == legal_name("EXAMPLE HOLDINGS, PT")
    assert legal_name("ANTHONI SALIM") != legal_name("BHAKTI SALIM")


def test_reference_reconciliation_preserves_ids_and_follows_only_explicit_indirect_holdings():
    definition = {"groups": [{"id":f"G{i}","name":f"Group {i}","legacy_portfolios":[],"listed_anchors": ["AAAA"] if i == 0 else [],"holder_names":[],"relationship_source":None,"relationship_source_as_of":"2026-09-30","issuer_affiliations":[],"coverage_note":"Dated research lens"} for i in range(34)],"reference":{"group_count":34},"indirect_policy":"Exact legal names"}
    market = {"records":[{"ticker":"AAAA.JK","company_name":"PT Alpha Tbk"},{"ticker":"BBBB.JK","company_name":"PT Beta Tbk"},{"ticker":"CCCC.JK","company_name":"PT Gamma Tbk"}],"ownership_edges":[]}
    ownership = {"as_of":"2026-09-30","sources":[{"as_of":"2026-09-30","url":"https://www.idx.co.id/evidence.xlsx"}],"registers":{"one":[{"holder":"PT ALPHA TBK","ticker":"BBBB","percentage":25},{"holder":"PT BETA TBK","ticker":"CCCC","percentage":10}]}}
    view, edges, report = reconcile(definition=definition, legacy={"groups":[{"taxonomy_group_id":"OLD","taxonomy_group_name":"Legacy"}],"memberships":[]}, market=market,ownership=ownership)
    assert len(report["reference_groups"]) == 34
    assert "OLD" in {g["taxonomy_group_id"] for g in view["groups"]}
    assert report["reference_groups"][0]["verified_members"] == ["AAAA.JK","BBBB.JK","CCCC.JK"]
    assert next(edge for edge in edges if edge["ticker"] == "CCCC")["relationship"] == "Indirect disclosed holding"
    assert all(edge["control_source"] is None for edge in edges)
