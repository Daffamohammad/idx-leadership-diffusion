"""Tests for the concentration engine."""
from __future__ import annotations

import pandas as pd
import pytest

from idx_leadership.features.concentration import (
    compute_concentration,
    compute_signed_contribution_table,
)


def _prices(per_ticker_returns):
    """Build a price frame with a known return for each ticker at the last 20 days."""
    dates = pd.date_range("2026-07-01", periods=21).date  # 21 trading days
    rows = []
    for tkr, ret in per_ticker_returns.items():
        start = 100.0
        end = start * (1.0 + ret / 100.0)
        # Linear interpolation for the intermediate days
        prices = [start + (end - start) * (i / 20) for i in range(21)]
        for d, p in zip(dates, prices):
            rows.append({"ticker": tkr, "date": d, "adjusted_close": p, "close": p})
    return pd.DataFrame(rows)


def test_equal_contributions_top1_below_one():
    prices = _prices({"A": 5.0, "B": 5.0, "C": 5.0, "D": 5.0})
    r = compute_concentration(prices, group_tickers=["A", "B", "C", "D"], horizon=20)
    # Equal absolute shares => top1 share is 0.25
    assert r.top1_contribution_share is not None
    assert 0.20 < r.top1_contribution_share < 0.30
    assert r.top3_contribution_share is not None
    assert 0.70 < r.top3_contribution_share < 0.80
    assert r.hhi_contribution is not None
    # HHI of [0.25]*4 = 0.25
    assert 0.20 < r.hhi_contribution < 0.30


def test_one_dominant_constituent():
    prices = _prices({"A": 100.0, "B": 5.0, "C": 5.0, "D": 5.0})
    r = compute_concentration(prices, group_tickers=["A", "B", "C", "D"], horizon=20)
    # A dominates the absolute move
    assert r.top1_contribution_share is not None
    assert r.top1_contribution_share > 0.7


def test_zero_group_move_returns_none_for_share():
    # All constituents flat: 0 returns across the board
    prices = _prices({"A": 0.0, "B": 0.0, "C": 0.0})
    r = compute_concentration(prices, group_tickers=["A", "B", "C"], horizon=20)
    # abs_share sums to 0, so all metrics are None
    assert r.top1_contribution_share is None
    assert r.top3_contribution_share is None
    assert r.hhi_contribution is None


def test_signed_contribution_table_signs():
    prices = _prices({"A": 10.0, "B": -5.0, "C": 0.0})
    df = compute_signed_contribution_table(prices, group_tickers=["A", "B", "C"], horizon=20)
    # A's signed share positive, B's negative
    a = df[df["ticker"] == "A"].iloc[0]
    b = df[df["ticker"] == "B"].iloc[0]
    assert a["return"] > 0
    assert b["return"] < 0
    assert a["signed_share"] > 0
    assert b["signed_share"] < 0


def test_concentration_insufficient_history():
    dates = pd.date_range("2026-08-01", periods=3).date
    rows = [
        {"ticker": "A", "date": d, "adjusted_close": 100.0 + i, "close": 100.0 + i}
        for i, d in enumerate(dates)
    ]
    prices = pd.DataFrame(rows)
    r = compute_concentration(prices, group_tickers=["A"], horizon=20)
    assert r.contributor_count == 1
    assert r.top1_contribution_share is None  # insufficient history
