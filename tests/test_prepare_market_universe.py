from copy import deepcopy

from scripts.prepare_market_universe import structural_versions


def test_structural_versions_ignore_observation_dates_and_quotes():
    records = [
        {
            "ticker": "AAA.JK",
            "instrument_type": "Common Stock",
            "analysis_requested": True,
            "listing_board": "Main",
            "market_cap": 100,
            "classification_as_of": "2026-09-30",
            "taxonomy": {"sector": "Energy", "subsector": "Oil", "industry": "Energy", "subindustry": "Oil"},
        },
        {
            "ticker": "BBB.JK",
            "instrument_type": "Common Stock",
            "analysis_requested": False,
            "listing_board": "Watchlist",
            "market_cap": 10,
            "classification_as_of": "2026-09-30",
            "taxonomy": {"sector": "Unknown"},
        },
    ]
    later = deepcopy(records)
    later[0]["market_cap"] = 250
    later[0]["classification_as_of"] = "2026-10-02"
    assert structural_versions(later) == structural_versions(records)


def test_structural_version_changes_when_verified_facts_change():
    records = [{
        "ticker": "AAA.JK",
        "instrument_type": "Common Stock",
        "analysis_requested": True,
        "listing_board": "Main",
        "taxonomy": {"sector": "Energy", "subindustry": "Oil"},
    }]
    baseline = structural_versions(records)
    changed = deepcopy(records)
    changed[0]["listing_board"] = "Development"
    assert structural_versions(changed)[0] != baseline[0]
    changed = deepcopy(records)
    changed[0]["taxonomy"]["subindustry"] = "Gas"
    assert structural_versions(changed)[1] != baseline[1]
