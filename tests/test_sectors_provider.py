"""Tests for the Sectors provider and its normalizers."""
from __future__ import annotations

import pandas as pd
import pytest

from idx_leadership.providers.sectors import SectorsProvider
from idx_leadership.providers.sectors_normalizers import (
    normalize_companies,
    normalize_close_cross_section,
    normalize_free_float,
    normalize_foreign_flow,
    normalize_suspensions,
)
from datetime import date


def test_normalize_companies_basic():
    rows = [
        {
            "symbol": "BBCA",
            "company_name": "PT Bank Central Asia Tbk.",
            "sector": "Financials",
            "sub_sector": "Banks",
            "industry": "Banks",
            "sub_industry": "Banks",
            "market_cap": 753611199412500,
            "listing_board": "Main",
        }
    ]
    df = normalize_companies(rows)
    assert len(df) == 1
    assert df.iloc[0]["ticker"] == "BBCA.JK"
    assert df.iloc[0]["sector"] == "Financials"
    assert df.iloc[0]["industry"] == "Banks"


def test_normalize_companies_symbol_already_dot_jk():
    rows = [{"symbol": "TLKM.JK", "company_name": "x", "sector": "Telecom"}]
    df = normalize_companies(rows)
    assert df.iloc[0]["ticker"] == "TLKM.JK"


def test_normalize_companies_skips_empty_symbol():
    rows = [{"symbol": "", "sector": "Financials"}]
    df = normalize_companies(rows)
    assert df.empty


def test_normalize_close_cross_section():
    rows = [
        {"symbol": "BBCA.JK", "date": "2026-08-20", "close": 6175},
        {"symbol": "TLKM.JK", "date": "2026-08-20", "close": 3200},
    ]
    df = normalize_close_cross_section(rows, as_of=date(2026, 8, 20))
    assert set(df["ticker"]) == {"BBCA.JK", "TLKM.JK"}
    assert df.iloc[0]["adjusted_close"] == 6175  # treated as raw (G011)


def test_normalize_close_cross_section_rejects_bad_price():
    rows = [
        {"symbol": "A.JK", "date": "2026-08-20", "close": "abc"},
        {"symbol": "B.JK", "date": "2026-08-20", "close": 100},
    ]
    df = normalize_close_cross_section(rows, as_of=date(2026, 8, 20))
    assert len(df) == 1
    assert df.iloc[0]["ticker"] == "B.JK"


def test_normalize_free_float():
    rows = [
        {"symbol": "PADI", "company_name": "Padi", "free_float": 0.999},
        {"symbol": "BBCA", "company_name": "BCA", "free_float": "bad"},
    ]
    df = normalize_free_float(rows)
    assert len(df) == 1
    assert df.iloc[0]["ticker"] == "PADI.JK"
    assert df.iloc[0]["free_float"] == 0.999


def test_normalize_foreign_flow():
    payload = {
        "symbol": "BBCA.JK",
        "start": "2025-05-01",
        "end": "2025-05-05",
        "data": [
            {"date": "2025-05-02", "net_foreign_inflow": 199859810000},
            {"date": "2025-05-05", "net_foreign_inflow": -50000000000},
        ],
    }
    df = normalize_foreign_flow(payload)
    assert len(df) == 2
    assert df.iloc[0]["ticker"] == "BBCA.JK"
    assert df.iloc[0]["net_foreign_inflow"] == 199859810000
    assert df.iloc[1]["net_foreign_inflow"] < 0


def test_normalize_suspensions():
    rows = [
        {"symbol": "FLMC.JK", "suspension_date": "2026-07-03", "reason": "Test", "pdf_url": "http://x"},
    ]
    df = normalize_suspensions(rows)
    assert len(df) == 1
    assert df.iloc[0]["ticker"] == "FLMC.JK"


def test_sectors_provider_without_key_blocks_live():
    p = SectorsProvider(api_key="")
    from idx_leadership.utils.errors import ProviderError
    with pytest.raises(ProviderError):
        p.get_security_master()


def test_sectors_provider_with_fake_transport_returns_master():
    from idx_leadership.providers.ledger import RequestLedger
    ledger = RequestLedger()

    def fake_get(self, path, params=None, use_cache=True):
        return type(
            "R",
            (),
            {
                "payload": {
                    "results": [
                        {
                            "symbol": "BBCA",
                            "company_name": "BCA",
                            "sector": "Financials",
                            "sub_sector": "Banks",
                            "industry": "Banks",
                            "sub_industry": "Banks",
                        }
                    ],
                    "pagination": {"has_next": False},
                },
                "status": 200,
                "endpoint": path,
                "params": params or {},
                "elapsed_ms": 1.0,
                "rows": 1,
                "cache_hit": False,
                "estimated_credit_cost": 0.0,
            },
        )()

    p = SectorsProvider(api_key="K", ledger=ledger)
    p.client.get = fake_get
    rows = p.get_security_master()
    assert len(rows) == 1
    assert rows[0].ticker == "BBCA.JK"
    assert rows[0].sector == "Financials"


def test_sectors_provider_passes_configured_api_root_to_client():
    p = SectorsProvider(api_key="K", base_url="https://example.test/v2")
    assert p.client.base_url == "https://example.test"


def test_sectors_provider_maps_yahoo_ihsg_identifier():
    p = SectorsProvider(api_key="K")
    p.get_full_universe_close = lambda as_of: pd.DataFrame(
        [{"ticker": "IHSG.JK", "date": as_of, "close": 7000.0}]
    )
    result = p.get_benchmark_history(
        "^JKSE", start=date(2026, 8, 20), end=date(2026, 8, 20)
    )
    assert len(result) == 1
    assert result.iloc[0]["benchmark_id"] == "^JKSE"
    assert set(result["close"]) == {7000.0}


def test_sectors_provider_history_uses_business_day_window():
    p = SectorsProvider(api_key="K")
    p.get_full_universe_close = lambda as_of: pd.DataFrame(
        [{"ticker": "BBCA.JK", "date": as_of, "close": 100.0}]
    )
    start = date(2026, 1, 1)
    end = date(2026, 3, 31)
    result = p.get_price_history(["BBCA.JK"], start=start, end=end)
    expected = len(pd.bdate_range(start=start, end=end))
    assert len(result) == expected
    assert result["date"].min() == start
    assert result["date"].max() == end


def test_sectors_provider_pagination_walks_pages():
    from idx_leadership.providers.ledger import RequestLedger
    ledger = RequestLedger()
    call_count = {"n": 0}

    def fake_get(self, path, params=None, use_cache=True):
        call_count["n"] += 1
        offset = int(params.get("offset", 0))
        if offset == 0:
            return type(
                "R",
                (),
                {
                    "payload": {
                        "results": [{"symbol": f"T{i}", "company_name": "x", "sector": "Financials", "sub_sector": "Banks", "industry": "Banks", "sub_industry": "Banks"} for i in range(30)],
                        "pagination": {"has_next": True, "next_offset": 30},
                    },
                    "status": 200,
                    "endpoint": path,
                    "params": params or {},
                    "elapsed_ms": 1.0,
                    "rows": 30,
                    "cache_hit": False,
                    "estimated_credit_cost": 0.0,
                },
            )()
        return type(
            "R",
            (),
            {
                "payload": {
                    "results": [{"symbol": f"T{30+i}", "company_name": "x", "sector": "Financials", "sub_sector": "Banks", "industry": "Banks", "sub_industry": "Banks"} for i in range(5)],
                    "pagination": {"has_next": False},
                },
                "status": 200,
                "endpoint": path,
                "params": params or {},
                "elapsed_ms": 1.0,
                "rows": 5,
                "cache_hit": False,
                "estimated_credit_cost": 0.0,
            },
        )()

    p = SectorsProvider(api_key="K", ledger=ledger)
    p.client.get = lambda path, params=None, use_cache=True: fake_get(p.client, path, params, use_cache)
    rows = p.get_security_master()
    assert len(rows) == 35
    assert call_count["n"] == 2
