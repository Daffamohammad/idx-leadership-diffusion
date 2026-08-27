"""Provider-contract tests.

Each test pins down the shape of a normalized Sectors payload. If
the upstream Sectors v2 API changes its schema, the corresponding
test will fail loudly (per brief §78).
"""
from __future__ import annotations

import pytest

from idx_leadership.providers.sectors_client import SectorsClient
from idx_leadership.providers.sectors_normalizers import (
    normalize_companies,
    normalize_close_cross_section,
    normalize_foreign_flow,
    normalize_free_float,
    normalize_suspensions,
)
from datetime import date


# ----- /v2/companies/ -----

def test_companies_minimum_schema():
    rows = [
        {
            "symbol": "BBCA",
            "company_name": "PT Bank Central Asia Tbk.",
            "sector": "Financials",
            "sub_sector": "Banks",
            "industry": "Banks",
            "sub_industry": "Banks",
        }
    ]
    df = normalize_companies(rows)
    assert not df.empty
    assert "ticker" in df.columns
    assert "sector" in df.columns
    assert "sub_sector" in df.columns


def test_companies_missing_optional_fields_handled():
    rows = [{"symbol": "ABC"}]
    df = normalize_companies(rows)
    assert df.iloc[0]["ticker"] == "ABC.JK"
    assert df.iloc[0]["sector"] is None


def test_companies_ticker_does_not_double_suffix():
    rows = [{"symbol": "BBCA.JK"}]
    df = normalize_companies(rows)
    assert df.iloc[0]["ticker"] == "BBCA.JK"


def test_companies_empty_input_returns_empty():
    df = normalize_companies([])
    assert df.empty


# ----- /v2/close/ -----

def test_close_minimum_schema():
    rows = [{"symbol": "BBCA.JK", "date": "2026-08-20", "close": 6175}]
    df = normalize_close_cross_section(rows, as_of=date(2026, 8, 20))
    assert "close" in df.columns
    assert "adjusted_close" in df.columns
    assert df.iloc[0]["ticker"] == "BBCA.JK"


def test_close_handles_non_numeric_price():
    rows = [
        {"symbol": "A.JK", "date": "2026-08-20", "close": "abc"},
        {"symbol": "B.JK", "date": "2026-08-20", "close": 100},
    ]
    df = normalize_close_cross_section(rows, as_of=date(2026, 8, 20))
    assert len(df) == 1
    assert df.iloc[0]["ticker"] == "B.JK"


def test_close_handles_empty():
    df = normalize_close_cross_section([], as_of=date(2026, 8, 20))
    assert df.empty


def test_close_response_metadata_columns_preserved():
    rows = [
        {"symbol": "BBCA.JK", "date": "2026-08-20", "close": 6175}
    ]
    df = normalize_close_cross_section(rows, as_of=date(2026, 8, 20))
    # The canonical frame exposes volume and market_cap columns
    # (None if the upstream payload omits them).
    assert "volume" in df.columns
    assert "market_cap" in df.columns
    assert df.iloc[0]["volume"] is None
    assert df.iloc[0]["market_cap"] is None


# ----- /v2/free-float/ -----

def test_free_float_minimum_schema():
    rows = [{"symbol": "BBCA", "company_name": "BCA", "free_float": 0.42}]
    df = normalize_free_float(rows)
    assert df.iloc[0]["ticker"] == "BBCA.JK"
    assert df.iloc[0]["free_float"] == 0.42


def test_free_float_handles_bad_value():
    rows = [{"symbol": "BBCA", "free_float": "x"}]
    df = normalize_free_float(rows)
    assert df.empty


# ----- /v2/foreign-flow/{symbol}/ -----

def test_foreign_flow_minimum_schema():
    payload = {
        "symbol": "BBCA.JK",
        "start": "2025-05-01",
        "end": "2025-05-05",
        "data": [
            {"date": "2025-05-02", "net_foreign_inflow": 199859810000},
        ],
    }
    df = normalize_foreign_flow(payload)
    assert df.iloc[0]["net_foreign_inflow"] == 199859810000
    assert df.iloc[0]["ticker"] == "BBCA.JK"


def test_foreign_flow_empty_data():
    payload = {"symbol": "BBCA.JK", "data": []}
    df = normalize_foreign_flow(payload)
    assert df.empty


# ----- /v2/suspensions/ -----

def test_suspensions_minimum_schema():
    rows = [
        {"symbol": "FLMC.JK", "suspension_date": "2026-07-03", "reason": "x", "pdf_url": "http://x"}
    ]
    df = normalize_suspensions(rows)
    assert df.iloc[0]["ticker"] == "FLMC.JK"
    assert df.iloc[0]["pdf_url"].startswith("http")


def test_suspensions_handles_empty():
    df = normalize_suspensions([])
    assert df.empty


# ----- client behavior -----

def test_client_estimated_cost_unknown_endpoints_does_not_invent(tmp_path):
    """Per brief §12, unknown costs must NOT be fabricated."""
    from idx_leadership.data import RawCache
    from idx_leadership.providers.ledger import RequestLedger
    from idx_leadership.providers.sectors_client import _estimated_credit_cost
    # /v2/companies/ cost is UNKNOWN per docs.
    assert _estimated_credit_cost("/v2/companies/", [{"x": 1}]) == 0.0
    assert _estimated_credit_cost("/v2/company/report/BBCA.JK/", {}) == 0.0
    # The known ones stay explicit.
    assert _estimated_credit_cost("/v2/close/", {"results": [1] * 30}) == 1.0
    assert _estimated_credit_cost("/v2/foreign-flow/{symbol}/", {"data": []}) == 1.0


def test_client_documented_cost_table_only_has_known_endpoints():
    from idx_leadership.providers.sectors_client import DOCUMENTED_COST
    # Ensure we never silently "upgrade" an unknown cost to a number.
    for ep, rule in DOCUMENTED_COST.items():
        assert rule in {"per_page", "per_100_companies", "per_call_1", "unknown_verify"}, (
            f"unexpected rule for {ep}: {rule}"
        )
