"""Offline tests for the official IDX statistics parser."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from idx_leadership.providers.idx_statistics import (
    IDX_SOURCE_REGISTRY,
    IDXStatisticsError,
    build_monthly_investor_url,
    manual_price_fallback_contract_matches,
    parse_idx_daily_indices_html,
    parse_idx_monthly_investor_html,
    parse_idx_statistics_listing_html,
    parse_idx_stock_summary_html,
)
from scripts.refresh_idx_statistics import main


SOURCE_URL = build_monthly_investor_url(2026, 7)


def _release_html() -> str:
    return """
    <html><body>
      <h1>Table Daily Trading by Type of Investor - Juli 2026</h1>
      <h4>Foreign Selling</h4>
      <table>
        <tr><th>Date</th><th>Foreign Investor Sell - Foreign Investor Buy</th><th>Foreign Investor Sell - Domestic Investor Buy</th></tr>
        <tr><th>Volume</th><th>Value (IDR)</th><th>Freq. (x)</th><th>Volume</th><th>Value (IDR)</th><th>Freq. (x)</th></tr>
        <tr><td>30 Jul 2026</td><td>1.000</td><td>2.000</td><td>3</td><td>4.000</td><td>5.000</td><td>6</td></tr>
        <tr><td>31 Jul 2026</td><td>1.100</td><td>2.100</td><td>4</td><td>4.100</td><td>5.100</td><td>7</td></tr>
        <tr><td>Total</td><td>2.100</td><td>4.100</td><td>7</td><td>8.100</td><td>10.100</td><td>13</td></tr>
      </table>
      <h4>Domestic Selling</h4>
      <table>
        <tr><th>Date</th><th>Domestic Investor Sell - Foreign Investor Buy</th><th>Domestic Investor Sell - Domestic Investor Buy</th></tr>
        <tr><th>Volume</th><th>Value (IDR)</th><th>Freq. (x)</th><th>Volume</th><th>Value (IDR)</th><th>Freq. (x)</th></tr>
        <tr><td>30 Jul 2026</td><td>2.000</td><td>6.000</td><td>8</td><td>9.000</td><td>10.000</td><td>11</td></tr>
        <tr><td>31 Jul 2026</td><td>2.200</td><td>6.200</td><td>9</td><td>9.200</td><td>10.200</td><td>12</td></tr>
        <tr><td>Total</td><td>4.200</td><td>12.200</td><td>17</td><td>18.200</td><td>20.200</td><td>23</td></tr>
      </table>
    </body></html>
    """


def test_monthly_url_matches_the_user_supplied_filter():
    assert SOURCE_URL.endswith(
        "?filter=eyJ5ZWFyIjoiMjAyNiIsIm1vbnRoIjoiNyIsInF1YXJ0ZXIiOjAsInR5cGUiOiJtb250aGx5In0%3D"
    )


def test_parser_derives_net_foreign_from_cross_investor_columns():
    payload = parse_idx_monthly_investor_html(
        _release_html(),
        source_url=SOURCE_URL,
        retrieved_at="2026-08-31T00:00:00+00:00",
    )

    assert payload["schema_version"] == "idx-investor-trading-v1"
    assert payload["status"] == "READY"
    assert payload["release"]["period"] == {"year": 2026, "month": 7, "label": "Juli 2026"}
    assert payload["release"]["trading_day_count"] == 2
    assert payload["daily"][0]["net_foreign_value_idr"] == 1_000
    assert payload["daily"][1]["net_foreign_value_idr"] == 1_100
    assert payload["totals"]["net_foreign_value_idr"] == 2_100
    assert payload["totals"]["direction"] == "NET_BUY"
    assert all(payload["quality"]["reconciliation"].values())
    assert payload["source"]["retrieved_at"] == "2026-08-31T00:00:00+00:00"


def test_parser_fails_closed_when_the_two_tables_do_not_share_dates():
    html = _release_html().replace("31 Jul 2026", "29 Jul 2026", 1)
    with pytest.raises(IDXStatisticsError, match="different trading dates"):
        parse_idx_monthly_investor_html(html, source_url=SOURCE_URL)


def test_statistics_listing_extracts_first_party_daily_pdf_links():
    html = """
    <table><tr><th>Tanggal</th><th>Perihal</th><th>Unduh</th></tr>
      <tr><td>28 Aug 2026</td><td>IDX Daily Statistics - 28 August 2026</td>
        <td><a href="/Media/liskz5kp/ds_260828.pdf">PDF</a></td></tr>
    </table>
    """
    payload = parse_idx_statistics_listing_html(
        html,
        source_url="https://www.idx.co.id/id/data-pasar/laporan-statistik/statistik/",
        retrieved_at="2026-08-31T00:00:00+00:00",
    )
    assert payload["status"] == "READY"
    assert payload["publications"][0]["as_of"] == "2026-08-28"
    assert payload["publications"][0]["url"].endswith("ds_260828.pdf")
    assert payload["quality"]["search_agent_role"] == "DISCOVERY_ONLY"


def test_cli_does_not_write_when_reconciliation_fails(tmp_path: Path):
    bad_html = _release_html().replace("<td>10.100</td>", "<td>10.101</td>")
    input_path = tmp_path / "release.html"
    output_path = tmp_path / "release.json"
    input_path.write_text(bad_html, encoding="utf-8")

    result = main(
        [
            "--year",
            "2026",
            "--month",
            "7",
            "--html-file",
            str(input_path),
            "--output",
            str(output_path),
        ]
    )

    assert result == 2
    assert not output_path.exists()


def test_parser_output_is_json_serializable():
    payload = parse_idx_monthly_investor_html(_release_html(), source_url=SOURCE_URL)
    assert json.loads(json.dumps(payload, allow_nan=False))["provider"] == "IDX"


def test_source_registry_covers_the_six_official_idx_lanes():
    assert set(IDX_SOURCE_REGISTRY) == {
        "statistics",
        "investor_flow",
        "daily_indices",
        "industry_summary",
        "digital_statistics",
        "stock_summary",
    }
    assert all(spec.url.startswith("https://www.idx.co.id/") for spec in IDX_SOURCE_REGISTRY.values())


def test_digital_table_parser_keeps_missing_and_malformed_numeric_as_gaps():
    payload = parse_idx_daily_indices_html(
        """
        <table>
          <tr><th>Date</th><th>Close</th><th>Change (%)</th></tr>
          <tr><td>28 Aug 2026</td><td>1.234,50</td><td>bad</td></tr>
          <tr><td>31 Aug 2026</td><td>—</td><td>1,25</td></tr>
        </table>
        """,
        retrieved_at="2026-08-31T00:00:00+00:00",
    )
    assert payload["status"] == "READY_WITH_GAPS"
    assert payload["records"][0]["close"] == pytest.approx(1234.5)
    assert payload["records"][0]["change"] is None
    assert payload["quality"]["malformed_numeric_count"] == 1
    assert payload["artifact"]["content_sha256"]


def test_stock_summary_is_display_only_and_never_analytical():
    payload = parse_idx_stock_summary_html(
        """
        <table>
          <tr><th>Symbol</th><th>Close</th></tr>
          <tr><td>BBCA</td><td>9.000</td></tr>
        </table>
        """,
        as_of="2026-08-28",
    )
    assert payload["mode"] == "current_display_only"
    assert payload["quantitative_use"] is False
    assert payload["observations"][0]["ticker"] == "BBCA.JK"
    assert payload["observations"][0]["close"] == pytest.approx(9000)


def test_manual_price_contract_requires_full_contract_match():
    contract = {
        "provider_mode": "IDX_OFFICIAL",
        "universe_version": "u1",
        "taxonomy_version": "t1",
        "price_basis": "close",
    }
    assert manual_price_fallback_contract_matches(contract, dict(contract))
    assert not manual_price_fallback_contract_matches(
        contract, {**contract, "price_basis": "adjusted_close"}
    )
