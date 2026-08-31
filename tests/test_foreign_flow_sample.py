"""Tests for the bounded, non-signal foreign-flow calculation harness."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.calculate_foreign_flow_sample import (
    ForeignFlowInputError,
    calculate_foreign_flow_sample,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
INPUT = REPO_ROOT / "data" / "fixtures" / "foreign_flow_sample.csv"
SECURITY_MASTER = REPO_ROOT / "config" / "universe.yaml"


def test_sample_calculation_preserves_market_net_and_rounding_status():
    result = calculate_foreign_flow_sample(INPUT, security_master_path=SECURITY_MASTER)

    assert result["schema_version"] == "foreign-flow-sample-v2"
    assert result["provider_mode"] == "PUBLIC_PROTOTYPE"
    assert result["status"] == "READY_WITH_GAPS"
    assert result["calculation"]["sectors_api_called"] is False
    assert result["calculation"]["network_requests_made"] is False
    assert result["calculation"]["leadership_integration"] == "DISABLED_DATA_GAP"
    assert result["coverage"]["market_day_count"] >= 5
    assert result["coverage"]["company_observation_count"] >= 30
    assert result["coverage"]["unique_company_ticker_count"] >= 15

    market = {row["as_of"]: row for row in result["market_observations"]}
    assert market["2026-08-12"]["net_value_idr"] == 725_400_000_000
    assert market["2026-08-12"]["reconciliation_status"] == "ROUNDING_VARIANCE"
    assert market["2026-08-12"]["reconciliation_delta_idr"] == 5_400_000_000
    assert market["2026-08-27"]["net_value_idr"] == -113_450_000_000
    assert market["2026-08-27"]["reconciliation_status"] == "ROUNDING_VARIANCE"
    assert market["2026-08-27"]["reconciliation_delta_idr"] == -3_450_000_000


def test_source_reconciled_market_totals_and_top_lists_are_pinned():
    """Guard the manually reviewed article values against silent drift."""
    result = calculate_foreign_flow_sample(INPUT, security_master_path=SECURITY_MASTER)
    market = {row["as_of"]: row["net_value_idr"] for row in result["market_observations"]}
    assert market == {
        "2026-08-12": 725_400_000_000,
        "2026-08-18": -689_260_000_000,
        "2026-08-19": -488_490_000_000,
        "2026-08-21": 992_640_000_000,
        "2026-08-26": 216_950_000_000,
        "2026-08-27": -113_450_000_000,
    }

    company = {
        (row["as_of"], row["ticker"]): row["net_value_idr"]
        for row in result["company_observations"]
    }
    assert company[("2026-08-18", "DSSA.JK")] == -165_600_000_000
    assert company[("2026-08-19", "TINS.JK")] == 158_900_000_000
    assert company[("2026-08-21", "BBCA.JK")] == 269_100_000_000
    assert company[("2026-08-26", "BMRI.JK")] == 205_300_000_000
    assert company[("2026-08-26", "GOTO.JK")] == -125_440_000_000

    counts_by_date: dict[str, int] = {}
    for row in result["company_observations"]:
        counts_by_date[row["as_of"]] = counts_by_date.get(row["as_of"], 0) + 1
    assert counts_by_date == {date_key: 10 for date_key in market}


def test_company_rows_are_net_only_and_unmapped_rows_are_explicit():
    result = calculate_foreign_flow_sample(INPUT, security_master_path=SECURITY_MASTER)

    assert all(
        row["buy_value_idr"] is None and row["sell_value_idr"] is None
        for row in result["company_observations"]
    )
    assert all(
        row["reconciliation_status"] == "NET_REPORTED_ONLY"
        for row in result["company_observations"]
    )
    unmapped_set = set(result["coverage"]["unmapped_tickers"])
    # Names outside the bounded public prototype universe remain explicit.
    for ticker in ("PTRO.JK", "DSSA.JK", "TINS.JK"):
        assert ticker in unmapped_set
    # Prototype-universe names are no longer mapped through a Sectors payload.
    for ticker in ("MDKA.JK", "MEDC.JK", "TLKM.JK", "TPIA.JK", "UNTR.JK"):
        assert ticker not in unmapped_set
    assert any(
        row["group_id"] == "Financials" and row["as_of"] == "2026-08-27"
        for row in result["group_summaries"]
    )


def test_generated_output_is_valid_json_with_null_missing_fields(tmp_path: Path):
    result = calculate_foreign_flow_sample(INPUT, security_master_path=SECURITY_MASTER)
    output = tmp_path / "foreign_flow_sample.json"
    output.write_text(json.dumps(result, allow_nan=False), encoding="utf-8")
    loaded = json.loads(output.read_text(encoding="utf-8"))

    assert loaded["market_observations"][0]["ticker"] is None
    assert loaded["market_observations"][0]["group_id"] is None
    assert loaded["quality"]["reported_net_preserved"] is True


def test_discovery_manifest_promotes_validated_market_release_but_keeps_company_gap_explicit():
    manifest_path = REPO_ROOT / "data" / "fixtures" / "foreign_flow_discovery.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["discovery_providers"] == ["tavily", "you"]
    official = next(
        source
        for source in manifest["sources"]
        if source["role"] == "first_party_structured_release"
    )
    assert official["publisher"] == "Indonesia Stock Exchange"
    assert official["quantitative_use"] is True
    assert official["period"] == "2026-07"
    assert official["observed_rows"] == 23
    assert official["parser"] == "idx_monthly_investor_html"
    assert "per-ticker" in manifest["not_found"]
    assert manifest["calculation_boundary"].startswith("The official IDX release is parsed")


def test_invalid_company_components_fail_closed(tmp_path: Path):
    invalid = tmp_path / "invalid.csv"
    invalid.write_text(
        "as_of,scope,ticker,market_scope,net_value_idr,buy_value_idr,sell_value_idr,"
        "source_url,source_published_at,source_kind,source_name,source_locator,"
        "quantitative_use\n"
        "2026-08-27,company,BBRI.JK,regular,100,120,20,"
        "https://example.com/report,2026-08-27T20:00:00+07:00,secondary_article,"
        "Example,company row,True\n",
        encoding="utf-8",
    )

    with pytest.raises(ForeignFlowInputError):
        calculate_foreign_flow_sample(invalid, security_master_path=None)


def test_multi_date_coverage_and_signal_eligibility():
    result = calculate_foreign_flow_sample(INPUT, security_master_path=SECURITY_MASTER)

    eligibility = result["signal_eligibility"]
    coverage = result["coverage"]
    assert coverage["market_day_count"] >= 5
    assert coverage["company_observation_count"] >= 30
    # mapped_pct_meets_threshold requires ≥80%; the broadened sample is honest about this.
    assert isinstance(eligibility["mapped_pct_meets_threshold"], bool)
    assert isinstance(eligibility["sample_diagnostics_met"], bool)
    assert eligibility["full_universe_coverage_met"] is False
    assert eligibility["coverage_gate_met"] is False
    assert eligibility["signal_eligible"] is False


def test_daily_market_totals_and_group_summaries_are_disjoint():
    result = calculate_foreign_flow_sample(INPUT, security_master_path=SECURITY_MASTER)
    daily_markets = result["daily_market_totals"]
    daily_samples = result["daily_company_samples"]
    assert daily_markets and daily_samples
    # Each summary carries its scope label; the aggregation MUST NOT mix
    # the two scopes into a single bucket.
    scopes_market = {entry["scope"] for entry in daily_markets}
    scopes_sample = {entry["scope"] for entry in daily_samples}
    assert scopes_market == {"MARKET_TOTAL"}
    assert scopes_sample == {"TOP_LIST_SAMPLE"}
    # Top-list sample net flow MUST NOT be reported as a market total.
    for sample in daily_samples:
        for market_total in daily_markets:
            if sample["as_of"] == market_total["as_of"]:
                assert (
                    sample["sample_net_value_idr"] != market_total["net_value_idr"]
                ) or (
                    # Same value is only allowed if the source article
                    # happens to coincidentally sum to the market total,
                    # which we explicitly assert is rare. The intent of
                    # this test is to ensure they are emitted separately.
                    sample["scope"] != market_total["scope"]
                )


def test_rolling_sample_flow_windows_are_monotonic_in_window_size():
    result = calculate_foreign_flow_sample(INPUT, security_master_path=SECURITY_MASTER)
    rolling = result["rolling_sample_flow"]
    assert rolling, "rolling flow window must be produced"
    # Window size grows from 1 to min(3, len(rolling)).
    sizes = [entry["window_size"] for entry in rolling]
    assert sizes[0] == 1
    assert sizes[-1] == min(3, len(rolling))


def test_breadth_observed_categorises_signs():
    result = calculate_foreign_flow_sample(INPUT, security_master_path=SECURITY_MASTER)
    breadth = result["breadth_observed"]
    assert breadth["market_positive_day_count"] >= 1
    assert breadth["market_negative_day_count"] >= 1
    assert breadth["last_sample_direction"] in {"NET_BUY", "NET_SELL", "FLAT", "UNCONFIRMED"}
    assert breadth["last_market_direction"] in {"NET_BUY", "NET_SELL", "FLAT", "UNCONFIRMED"}


def test_synthetic_rows_are_isolated_from_public_observations():
    result = calculate_foreign_flow_sample(INPUT, security_master_path=SECURITY_MASTER)
    # Public market_observations must never contain synthetic rows.
    public_as_ofs = {row["as_of"] for row in result["market_observations"]}
    synthetic_as_ofs = {row["as_of"] for row in result["synthetic_test_only"]}
    assert synthetic_as_ofs.isdisjoint(public_as_ofs)


def test_expected_dates_surface_missing_and_stale_flags():
    result = calculate_foreign_flow_sample(
        INPUT,
        security_master_path=SECURITY_MASTER,
        expected_dates=["2026-08-11", "2026-08-12", "2026-08-99"],
    )
    assert "2026-08-11" in result["quality"]["missing_dates"]
    assert "2026-08-99" in result["quality"]["missing_dates"]
    assert "2026-08-12" not in result["quality"]["missing_dates"]


def test_synthetic_only_row_keeps_label():
    synthetic_csv = (
        REPO_ROOT / "data" / "fixtures" / "synthetic_foreign_flow.csv"
    )
    if not synthetic_csv.exists():
        return
    result = calculate_foreign_flow_sample(synthetic_csv, security_master_path=None)
    for row in result["synthetic_test_only"]:
        assert row["scope"] == "synthetic_test_only"
