"""Tests for relative strength and benchmark alignment."""
from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from idx_leadership.features.relative_strength import (
    align_security_to_benchmark,
    compute_benchmark_returns,
    compute_excess_returns,
    compute_ytd_excess_returns,
)


def test_benchmark_returns_correct():
    bench = pd.DataFrame(
        {
            "benchmark_id": ["IHSG"] * 25,
            "date": pd.date_range("2026-01-01", periods=25).date,
            "close": [100.0 + i for i in range(25)],
        }
    )
    out = compute_benchmark_returns(bench, horizons={"5d": 5, "20d": 20})
    assert abs(float(out["return_5d"]) - (124 / 119 - 1) * 100.0) < 1e-6
    assert abs(float(out["return_20d"]) - (124 / 104 - 1) * 100.0) < 1e-6


def test_benchmark_returns_insufficient_history():
    bench = pd.DataFrame(
        {
            "benchmark_id": ["IHSG"] * 3,
            "date": pd.date_range("2026-01-01", periods=3).date,
            "close": [100.0, 101.0, 102.0],
        }
    )
    out = compute_benchmark_returns(bench, horizons={"20d": 20})
    assert out["return_20d"] is None or pd.isna(out["return_20d"])


def test_align_security_to_benchmark_basic():
    sec = pd.DataFrame(
        {
            "ticker": ["A"],
            "return_5d": [10.0],
            "return_20d": [15.0],
            "return_60d": [20.0],
        }
    )
    bench = pd.Series({"return_5d": 4.0, "return_20d": 6.0, "return_60d": 8.0})
    out = align_security_to_benchmark(sec, bench, horizons=["5d", "20d", "60d"])
    assert float(out["benchmark_return_5d"].iloc[0]) == 4.0
    assert float(out["excess_return_5d"].iloc[0]) == 6.0
    assert float(out["excess_return_20d"].iloc[0]) == 9.0
    assert float(out["excess_return_60d"].iloc[0]) == 12.0


def test_align_with_missing_benchmark():
    sec = pd.DataFrame({"ticker": ["A"], "return_5d": [10.0], "return_20d": [15.0]})
    out = align_security_to_benchmark(sec, pd.Series(dtype=float), horizons=["5d", "20d"])
    assert pd.isna(out["benchmark_return_5d"].iloc[0])
    assert pd.isna(out["excess_return_5d"].iloc[0])


def test_compute_excess_returns_end_to_end(prices_df, benchmark_df):
    out = compute_excess_returns(
        prices_df, benchmark_df, horizons={"5d": 5, "20d": 20, "60d": 60},
        as_of=date(2026, 8, 20),
    )
    assert not out.empty
    assert "excess_return_20d" in out.columns
    assert "relative_strength_level" in out.columns
    # Sanity: at least one row should have non-null excess return
    assert out["excess_return_20d"].dropna().shape[0] > 0


def test_compute_ytd_uses_last_common_prior_year_session():
    prices = pd.DataFrame(
        {
            "ticker": ["A.JK"] * 3,
            "date": pd.to_datetime(["2025-12-30", "2026-01-02", "2026-08-28"]),
            "adjusted_close": [100.0, 105.0, 120.0],
        }
    )
    benchmark = pd.DataFrame(
        {
            "date": pd.to_datetime(["2025-12-30", "2026-01-02", "2026-08-28"]),
            "close": [1000.0, 1010.0, 1100.0],
        }
    )
    result = compute_ytd_excess_returns(
        prices,
        benchmark,
        as_of=date(2026, 8, 28),
    )

    row = result.iloc[0]
    assert row["return_ytd"] == pytest.approx(20.0)
    assert row["benchmark_return_ytd"] == pytest.approx(10.0)
    assert row["excess_return_ytd"] == pytest.approx(10.0)
    assert row["return_ytd_start_date"] == date(2025, 12, 30)
    assert row["return_ytd_end_date"] == date(2026, 8, 28)


def test_compute_ytd_returns_empty_when_prior_year_baseline_is_missing():
    prices = pd.DataFrame(
        {
            "ticker": ["A.JK"],
            "date": pd.to_datetime(["2026-08-28"]),
            "adjusted_close": [120.0],
        }
    )
    benchmark = pd.DataFrame(
        {"date": pd.to_datetime(["2026-08-28"]), "close": [1100.0]}
    )
    result = compute_ytd_excess_returns(prices, benchmark, as_of=date(2026, 8, 28))
    assert result.empty
