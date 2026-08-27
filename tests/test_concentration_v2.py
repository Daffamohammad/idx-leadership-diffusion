"""Tests for the v2 concentration module."""
from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from idx_leadership.features.concentration_v2 import (
    ConcentrationV2,
    compute_concentration_v2,
)


def _prices(per_ticker_returns, n_days=21):
    dates = pd.date_range("2026-07-01", periods=n_days).date
    rows = []
    for tkr, ret in per_ticker_returns.items():
        start = 100.0
        end = start * (1.0 + ret / 100.0)
        prices = [start + (end - start) * (i / (n_days - 1)) for i in range(n_days)]
        for d, p in zip(dates, prices):
            rows.append({"ticker": tkr, "date": d, "adjusted_close": p, "close": p})
    return pd.DataFrame(rows)


def test_top1_abs_share_capped_at_one():
    prices = _prices({"A": 50.0, "B": 50.0, "C": 50.0, "D": 50.0})
    r = compute_concentration_v2(prices, group_tickers=["A", "B", "C", "D"], horizon=20)
    assert r.top1_abs_share is not None
    assert 0 < r.top1_abs_share <= 1.0


def test_top1_abs_share_equal_contributors():
    prices = _prices({"A": 5.0, "B": 5.0, "C": 5.0, "D": 5.0})
    r = compute_concentration_v2(prices, group_tickers=["A", "B", "C", "D"], horizon=20)
    assert 0.20 < r.top1_abs_share < 0.30
    assert 0.70 < r.top3_abs_share < 0.80


def test_top1_dominates():
    prices = _prices({"A": 100.0, "B": 5.0, "C": 5.0, "D": 5.0})
    r = compute_concentration_v2(prices, group_tickers=["A", "B", "C", "D"], horizon=20)
    assert r.top1_abs_share > 0.7


def test_signed_share_signs():
    prices = _prices({"A": 10.0, "B": -5.0, "C": 0.0})
    r = compute_concentration_v2(prices, group_tickers=["A", "B", "C"], horizon=20)
    assert r.top1_signed_share is not None
    assert r.top1_signed_share > 0


def test_zero_group_move_returns_uncapped_metrics():
    prices = _prices({"A": 0.0, "B": 0.0})
    r = compute_concentration_v2(prices, group_tickers=["A", "B"], horizon=20)
    assert r.top1_abs_share is None
    assert r.top3_abs_share is None
    # Both tickers contributed rows but with zero return.
    assert r.contributor_count == 2


def test_hhi_bounded_at_one():
    prices = _prices({"A": 5.0, "B": 5.0, "C": 5.0, "D": 5.0})
    r = compute_concentration_v2(prices, group_tickers=["A", "B", "C", "D"], horizon=20)
    assert r.hhi is not None
    assert 0 < r.hhi <= 1.0


def test_insufficient_history_drops_contributor():
    # 3 days of data; horizon = 20 -> not enough for any contributor.
    dates = pd.date_range("2026-08-01", periods=3).date
    rows = [
        {"ticker": "A", "date": d, "adjusted_close": 100.0 + i, "close": 100.0 + i}
        for i, d in enumerate(dates)
    ]
    prices = pd.DataFrame(rows)
    r = compute_concentration_v2(prices, group_tickers=["A"], horizon=20)
    # Insufficient history means no contributor passes the filter.
    assert r.contributor_count == 0
    assert r.top1_abs_share is None


def test_concentration_v2_to_dict_keys():
    r = ConcentrationV2(top1_abs_share=0.5, hhi=0.3, contributor_count=4)
    d = r.to_dict()
    assert d["top1_abs_share"] == 0.5
    assert d["convention"] == "absolute_move_v2"
    assert "hhi" in d


def test_top3_abs_share_none_for_2_constituents():
    prices = _prices({"A": 50.0, "B": 50.0})
    r = compute_concentration_v2(prices, group_tickers=["A", "B"], horizon=20)
    assert r.top3_abs_share is None
    assert r.top5_abs_share is None


def test_top1_abs_share_returns_value_for_real_data():
    prices = _prices({"A": 10.0, "B": 5.0, "C": 3.0, "D": 1.0})
    r = compute_concentration_v2(prices, group_tickers=["A", "B", "C", "D"], horizon=20)
    assert r.top1_abs_share is not None
    assert r.contributor_count == 4


def test_near_zero_net_move_disables_signed_but_keeps_absolute_concentration():
    prices = _prices({"A": 10.0, "B": -9.9, "C": 0.1})
    result = compute_concentration_v2(
        prices, group_tickers=["A", "B", "C"], horizon=20
    )
    assert result.status == "DEFINED"
    assert result.absolute_concentration_status == "DEFINED"
    assert result.top1_abs_share is not None
    assert result.hhi is not None
    assert result.signed_attribution_status == "UNDEFINED_UNSTABLE_DENOMINATOR"
    assert result.top1_signed_share is None
    assert result.top3_signed_share is None


def test_negative_group_move_has_defined_signed_attribution():
    prices = _prices({"A": -10.0, "B": -2.0, "C": 1.0})
    result = compute_concentration_v2(
        prices, group_tickers=["A", "B", "C"], horizon=20
    )
    assert result.net_signed_return < 0
    assert result.signed_attribution_status == "DEFINED"
    assert result.top_absolute_contributor == "A"
    assert result.top1_signed_share > 0


def test_exact_cancellation_is_undefined_for_signed_attribution():
    prices = _prices({"A": 10.0, "B": -10.0})
    result = compute_concentration_v2(
        prices, group_tickers=["A", "B"], horizon=20
    )
    assert result.top1_abs_share == 0.5
    assert result.signed_attribution_status == "UNDEFINED_UNSTABLE_DENOMINATOR"
    assert result.top1_signed_share is None


def test_missing_stock_is_counted_without_invalidating_available_contributors():
    prices = _prices({"A": 10.0, "B": 5.0, "C": 2.0})
    result = compute_concentration_v2(
        prices, group_tickers=["A", "B", "C", "MISSING"], horizon=20
    )
    assert result.requested_constituent_count == 4
    assert result.contributor_count == 3
    assert result.missing_constituent_count == 1
    assert result.top3_abs_share == 1.0
