from copy import deepcopy

import pytest

from idx_leadership.providers.idx_stock_summary import normalize_stock_summary


def official_rows():
    return [{"Stock Code": "BBCA", "Company Name": "Bank Central Asia",
             "Previous": 100, "Close": 110, "Last Trading Date": "02 Oct 2026",
             "Listed Shares": 1000, "Volume": 10, "Foreign Buy": 20, "Foreign Sell": 7},
            {"Stock Code": "WSKT", "Previous": 5, "Close": 5,
             "Last Trading Date": "02 Oct 2026", "Listed Shares": 300, "Volume": 0}]


def test_official_units_and_no_trade_breadth():
    result = normalize_stock_summary(official_rows(), as_of="2026-10-02")
    stock = result["records"][0]
    assert stock["return_1d"] == pytest.approx(10)
    assert stock["market_cap"] == 110_000
    assert stock["foreign_net_shares"] == 13
    assert result["units"]["foreign"] == "shares"
    assert result["breadth"]["advancers"] == 1
    assert result["breadth"]["flat"] == 0
    assert result["breadth"]["not_traded_or_unavailable"] == 1


@pytest.mark.parametrize("bad", [0, float("nan"), float("inf"), None])
def test_missing_or_invalid_prices_are_never_flat(bad):
    rows = official_rows()
    rows[0]["Close"] = bad
    result = normalize_stock_summary(rows, as_of="2026-10-02")
    assert result["records"][0]["return_1d"] is None
    assert result["records"][0]["market_cap"] is None
    assert result["breadth"]["traded_count"] == 0


def test_duplicate_or_future_observations_fail():
    rows = official_rows()
    with pytest.raises(ValueError, match="Duplicate"):
        normalize_stock_summary(rows + [deepcopy(rows[0])], as_of="2026-10-02")
    rows[0]["Last Trading Date"] = "05 Oct 2026"
    with pytest.raises(ValueError, match="Future"):
        normalize_stock_summary(rows, as_of="2026-10-02")


def test_dated_classifications_and_unmapped_stock_are_preserved():
    reference = [{"ticker": "BBCA.JK", "taxonomy": {"sector": "Financials"}, "source_as_of": "2026-08-27"}]
    result = normalize_stock_summary(official_rows(), as_of="2026-10-02", classifications=reference)
    assert result["classification_count"] == 1
    assert result["records"][1]["taxonomy"] == {}
    reference[0]["source_as_of"] = "2026-10-05"
    with pytest.raises(ValueError, match="Future classification"):
        normalize_stock_summary(official_rows(), as_of="2026-10-02", classifications=reference)


def test_multiple_voting_security_is_visible_but_not_a_tradable_stock():
    rows = official_rows()
    rows.append({**rows[0], "Stock Code": "GOTOM", "Company Name": "MVS GoTo Gojek Tokopedia Tbk.", "Volume": 0})
    result = normalize_stock_summary(rows, as_of="2026-10-02")
    assert result["listed_count"] == 3
    mvs = next(r for r in result["records"] if r["ticker"] == "GOTOM.JK")
    assert not mvs["analysis_requested"]
    assert mvs["instrument_type"] == "MULTIPLE_VOTING_SHARES"
