from __future__ import annotations

import argparse
from types import SimpleNamespace

import pandas as pd
import pytest

from idx_leadership.data.quality import QualityReport
from idx_leadership.models import DataQualityStatus
from scripts.build_market_snapshot import (
    _coverage_report,
    _full_live_data_gate,
    _listed_universe_frame,
    _select_analysis_master,
)
from scripts.refresh_and_export import _operator_blockers


def _args(**overrides: object) -> argparse.Namespace:
    values = {
        "full_live": False,
        "allow_live": False,
        "allow_credit_spend": False,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_full_live_requires_both_explicit_acknowledgements():
    blockers = _operator_blockers(_args(full_live=True))

    assert [item["code"] for item in blockers] == [
        "LIVE_ACK_REQUIRED",
        "CREDIT_ACK_REQUIRED",
    ]


def test_bounded_live_also_blocks_missing_credit_acknowledgement():
    blockers = _operator_blockers(_args(allow_live=True))

    assert len(blockers) == 1
    assert blockers[0]["code"] == "CREDIT_ACK_REQUIRED"


def test_full_live_acknowledgements_require_local_api_key(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("SECTORS_API_KEY", raising=False)

    blockers = _operator_blockers(
        _args(full_live=True, allow_live=True, allow_credit_spend=True)
    )

    assert [item["code"] for item in blockers] == ["SECTORS_API_KEY_UNAVAILABLE"]


def test_full_live_acknowledgements_clear_operator_blockers_with_key(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SECTORS_API_KEY", "local-test-only")

    assert _operator_blockers(
        _args(full_live=True, allow_live=True, allow_credit_spend=True)
    ) == []


def _gate_provider(**overrides: object) -> SimpleNamespace:
    values = {
        "security_master_diagnostics": {"pagination_completeness": "COMPLETE", "missing_taxonomy_rows": 0},
        "close_pagination_diagnostics": {"completeness": "COMPLETE"},
        "history_diagnostics": {
            "failed_symbols": [],
            "empty_symbols": [],
            "duplicate_symbol_date_rows": 0,
        },
        "client": SimpleNamespace(max_estimated_credits=1000.0, budget_reserved_credits=4.0),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _complete_gate_inputs() -> dict[str, object]:
    as_of = pd.Timestamp("2026-08-27").date()
    history = pd.DataFrame(
        [
            {"ticker": "AAA.JK", "date": "2026-08-26", "close": 10.0, "adjusted_close": 10.0, "price_basis": "close"},
            {"ticker": "AAA.JK", "date": "2026-08-27", "close": 11.0, "adjusted_close": 11.0, "price_basis": "close"},
        ]
    )
    current_close = pd.DataFrame(
        [{"ticker": "AAA.JK", "date": as_of, "close": 11.0, "adjusted_close": 11.0, "price_basis": "close"}]
    )
    benchmark = pd.DataFrame(
        [{"benchmark_id": "IHSG", "date": as_of, "close": 7000.0, "price_basis": "close", "source": "sectors"}]
    )
    return {
        "master": [object()],
        "history_tickers": ["AAA.JK"],
        "history": history,
        "benchmark": benchmark,
        "current_close": current_close,
        "quality": QualityReport(
            status=DataQualityStatus.READY,
            coverage_pct=100.0,
            requested_securities=1,
            loaded_securities=1,
            usable_securities=1,
            benchmark_latest_date=as_of,
        ),
        "coverage": {"pagination_incomplete": False},
        "expected_price_basis": "close",
        "as_of": as_of,
        "min_history_days": 2,
    }


def test_full_live_data_gate_passes_only_on_complete_source_contract():
    blockers = _full_live_data_gate(
        provider=_gate_provider(),
        **_complete_gate_inputs(),
    )

    assert blockers == []


def test_full_live_gate_rejects_bounded_analysis_scope():
    blockers = _full_live_data_gate(
        provider=_gate_provider(),
        analysis_scope_complete=False,
        **_complete_gate_inputs(),
    )

    assert any(item["code"] == "ANALYSIS_SCOPE_INCOMPLETE" for item in blockers)


def test_full_live_data_gate_reports_blockers_before_any_snapshot_write():
    inputs = _complete_gate_inputs()
    provider = _gate_provider(
        security_master_diagnostics={
            "pagination_completeness": "PARTIAL",
            "missing_taxonomy_rows": 1,
        },
        close_pagination_diagnostics={"completeness": "PARTIAL"},
        history_diagnostics={
            "failed_symbols": [{"ticker": "AAA.JK", "error": "timeout"}],
            "empty_symbols": [],
            "duplicate_symbol_date_rows": 0,
        },
    )
    inputs["benchmark"] = inputs["benchmark"].assign(date="2026-08-26", price_basis="adjusted_close")
    inputs["quality"] = QualityReport(
        status=DataQualityStatus.READY_WITH_GAPS,
        issues=["failed_securities=['AAA.JK']"],
        coverage_pct=0.0,
        requested_securities=1,
        loaded_securities=0,
        usable_securities=0,
        failed_securities=1,
    )

    blockers = _full_live_data_gate(provider=provider, **inputs)
    codes = {item["code"] for item in blockers}

    assert {
        "SECURITY_MASTER_PAGINATION_INCOMPLETE",
        "CLOSE_PAGINATION_INCOMPLETE",
        "HISTORY_INCOMPLETE",
        "PRICE_BASIS_UNCERTAIN",
        "BENCHMARK_DATE_MISMATCH",
        "TAXONOMY_ENRICHMENT_INCOMPLETE",
        "QUALITY_STATUS_NOT_READY",
    } <= codes
    assert all(item["next_action"] for item in blockers)


def test_analysis_selector_keeps_sector_coverage_and_prioritizes_market_cap():
    master = [
        SimpleNamespace(ticker="AAA.JK", sector="Banks", market_cap=100.0),
        SimpleNamespace(ticker="AAB.JK", sector="Banks", market_cap=90.0),
        SimpleNamespace(ticker="CCC.JK", sector="Energy", market_cap=80.0),
        SimpleNamespace(ticker="DDD.JK", sector="Healthcare", market_cap=70.0),
        SimpleNamespace(ticker="EEE.JK", sector="Technology", market_cap=60.0),
    ]

    selected = _select_analysis_master(master, 3)

    assert {row.sector for row in selected} == {"Banks", "Energy", "Healthcare"}
    assert [row.ticker for row in selected] == ["AAA.JK", "CCC.JK", "DDD.JK"]


def test_analysis_selector_is_deterministic_and_does_not_mutate_master():
    master = [
        SimpleNamespace(ticker="ZZZ.JK", sector="Energy", market_cap=10.0),
        SimpleNamespace(ticker="AAA.JK", sector="Banks", market_cap=10.0),
        SimpleNamespace(ticker="BBB.JK", sector="Banks", market_cap=9.0),
    ]

    first = _select_analysis_master(master, 2)
    second = _select_analysis_master(master, 2)

    assert [row.ticker for row in first] == [row.ticker for row in second]
    assert [row.ticker for row in master] == ["ZZZ.JK", "AAA.JK", "BBB.JK"]


def test_analysis_selector_does_not_spend_history_slots_on_non_common_listings():
    master = [
        SimpleNamespace(
            ticker="FUND.JK",
            sector="Funds",
            market_cap=500.0,
            common_equity_status="NON_COMMON_EQUITY",
        ),
        SimpleNamespace(
            ticker="BANK.JK",
            sector="Banks",
            market_cap=100.0,
            common_equity_status="COMMON_EQUITY",
        ),
        SimpleNamespace(
            ticker="ENERGY.JK",
            sector="Energy",
            market_cap=90.0,
            common_equity_status="COMMON_EQUITY",
        ),
    ]

    selected = _select_analysis_master(master, 2)

    assert [row.ticker for row in selected] == ["BANK.JK", "ENERGY.JK"]


def test_listed_universe_preserves_unrequested_names_with_explicit_status():
    master = [
        SimpleNamespace(ticker="AAA.JK", sector="Banks", group_id="Banks"),
        SimpleNamespace(ticker="BBB.JK", sector="Energy", group_id="Energy"),
    ]
    analysis = pd.DataFrame(
        [
            {
                "ticker": "AAA.JK",
                "eligible": True,
                "exclusion_reason": None,
                "acquisition_status": "ACQUIRED",
            }
        ]
    )

    listed = _listed_universe_frame(master, analysis)

    assert listed["ticker"].tolist() == ["AAA.JK", "BBB.JK"]
    assert listed.loc[listed["ticker"] == "AAA.JK", "analysis_requested"].item()
    assert listed.loc[listed["ticker"] == "BBB.JK", "analysis_status"].item() == "NOT_REQUESTED"


def test_coverage_separates_full_listing_from_bounded_analysis_scope():
    provider = SimpleNamespace(
        security_master_diagnostics={
            "unique_rows": 4,
            "pagination": [{"completeness": "COMPLETE"}],
        },
        close_pagination_diagnostics={"completeness": "COMPLETE"},
        history_diagnostics={},
        client=SimpleNamespace(max_http_requests=400, http_requests_made=12),
    )
    analysis_universe = pd.DataFrame(
        [
            {
                "ticker": "AAA.JK",
                "sector": "Banks",
                "subsector": "Banks",
                "industry": "Banks",
                "subindustry": "Banks",
                "eligible": True,
                "exclusion_reason": None,
                "acquisition_status": "ACQUIRED",
            },
            {
                "ticker": "CCC.JK",
                "sector": "Energy",
                "subsector": "Energy",
                "industry": "Energy",
                "subindustry": "Energy",
                "eligible": True,
                "exclusion_reason": None,
                "acquisition_status": "ACQUIRED",
            },
        ]
    )
    quality = QualityReport(
        status=DataQualityStatus.READY,
        coverage_pct=100.0,
        requested_securities=2,
        loaded_securities=2,
        usable_securities=2,
        benchmark_latest_date=pd.Timestamp("2026-08-27").date(),
    )

    coverage = _coverage_report(
        master=[object(), object(), object(), object()],
        analysis_master=[object(), object()],
        universe=analysis_universe,
        history=pd.DataFrame(
            [
                {"ticker": "AAA.JK", "date": "2026-08-27"},
                {"ticker": "CCC.JK", "date": "2026-08-27"},
            ]
        ),
        quality=quality,
        as_of=pd.Timestamp("2026-08-27").date(),
        provider=provider,
        requested_history_tickers=["AAA.JK", "CCC.JK"],
        min_history_days=1,
    )

    assert coverage["security_master_total"] == 4
    assert coverage["used_count"] == 2
    assert coverage["full_accessible_universe_listed"] is True
    assert coverage["analysis_scope"] == "BOUNDED_DEMO"
    assert "Full accessible universe listed" in coverage["discovered_universe_disclosure"]


def test_coverage_does_not_call_a_page_capped_listing_full_universe():
    provider = SimpleNamespace(
        security_master_diagnostics={
            "unique_rows": 4,
            "pagination": [{"completeness": "PARTIAL"}],
        },
        close_pagination_diagnostics={"completeness": "COMPLETE"},
        history_diagnostics={},
        client=SimpleNamespace(max_http_requests=400, http_requests_made=12),
    )
    universe = pd.DataFrame(
        [
            {
                "ticker": "AAA.JK",
                "sector": "Banks",
                "subsector": "Banks",
                "industry": "Banks",
                "subindustry": "Banks",
                "eligible": True,
                "exclusion_reason": None,
                "acquisition_status": "ACQUIRED",
            }
        ]
    )
    quality = QualityReport(
        status=DataQualityStatus.READY,
        coverage_pct=100.0,
        requested_securities=1,
        loaded_securities=1,
        usable_securities=1,
    )

    coverage = _coverage_report(
        master=[object(), object(), object(), object()],
        analysis_master=[object(), object(), object(), object()],
        universe=universe,
        history=pd.DataFrame([{"ticker": "AAA.JK", "date": "2026-08-27"}]),
        quality=quality,
        as_of=pd.Timestamp("2026-08-27").date(),
        provider=provider,
        requested_history_tickers=["AAA.JK"],
        min_history_days=1,
    )

    assert coverage["analysis_scope"] == "PAGE_CAPPED"
    assert coverage["is_prefix_sample"] is True
    assert coverage["full_accessible_universe_listed"] is False
