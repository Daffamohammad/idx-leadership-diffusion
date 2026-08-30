from __future__ import annotations

import argparse
from types import SimpleNamespace

import pandas as pd
import pytest

from idx_leadership.data.quality import QualityReport
from idx_leadership.models import DataQualityStatus
from scripts.build_market_snapshot import _full_live_data_gate
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
