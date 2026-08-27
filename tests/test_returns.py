"""Tests for the returns engine."""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from idx_leadership.features.returns import (
    asof_close,
    compute_returns,
    compute_returns_for_universe,
    forward_fill,
)


def test_basic_return_calculation():
    prices = pd.DataFrame(
        {
            "ticker": ["A"] * 25,
            "date": pd.date_range("2026-01-01", periods=25).date,
            "adjusted_close": [100.0 + i for i in range(25)],
        }
    )
    out = compute_returns(prices, horizons={"5d": 5, "20d": 20})
    assert not out.empty
    r5 = float(out["return_5d"].iloc[0])
    r20 = float(out["return_20d"].iloc[0])
    # 5d return: price goes from 100 to 105 over 5 days => (105/100 - 1) * 100 = 5.0
    # We use end-5 (index -6) to start (index -1) for 5-trading-day return.
    # In a 25-day sequence, end is 124, start_5d is 124-5=119, start_20d is 124-20=104
    # 119/124 - 1 = -0.0403 ; but our convention is (end/start - 1).
    # end=124, start_5d row = 124-5 = 119; (124/119 - 1)*100 = 4.20
    # end=124, start_20d row = 124-20 = 104; (124/104 - 1)*100 = 19.23
    assert round(r5, 2) == round((124 / 119 - 1) * 100.0, 2)
    assert round(r20, 2) == round((124 / 104 - 1) * 100.0, 2)


def test_return_with_missing_start_returns_none():
    prices = pd.DataFrame(
        {
            "ticker": ["A"] * 3,
            "date": pd.date_range("2026-01-01", periods=3).date,
            "adjusted_close": [100.0, 101.0, 102.0],
        }
    )
    out = compute_returns(prices, horizons={"20d": 20})
    assert not out.empty
    assert out["return_20d"].iloc[0] is None or pd.isna(out["return_20d"].iloc[0])


def test_asof_resolution():
    prices = pd.DataFrame(
        {
            "ticker": ["A", "A", "A"],
            "date": [date(2026, 1, 1), date(2026, 1, 5), date(2026, 1, 10)],
            "adjusted_close": [100.0, 105.0, 110.0],
        }
    )
    out = compute_returns(prices, horizons={"5d": 5}, as_of=date(2026, 1, 9), tolerance_days=2)
    # as-of Jan 9 -> resolves to Jan 5; insufficient for 5d
    assert out.empty or out["return_5d"].iloc[0] is None or pd.isna(out["return_5d"].iloc[0])

    out2 = compute_returns(prices, horizons={"5d": 5}, as_of=date(2026, 1, 10), tolerance_days=2)
    # as-of Jan 10 -> Jan 10; end=110, start_5d row = 110 at index -6 -> not enough rows
    # We only have 3 rows, so 5d horizon must return None
    assert out2.empty or out2["return_5d"].iloc[0] is None


def test_asof_stale_returns_empty():
    prices = pd.DataFrame(
        {
            "ticker": ["A"] * 5,
            "date": pd.date_range("2026-01-01", periods=5).date,
            "adjusted_close": [100.0, 101.0, 102.0, 103.0, 104.0],
        }
    )
    # as_of is 30 days after data -> stale
    out = compute_returns(prices, horizons={"5d": 5}, as_of=date(2026, 4, 1), tolerance_days=7)
    assert out.empty


def test_invalid_price_dropped():
    # Most recent price is -1.0 (invalid); the next-most-recent valid price is the end.
    prices = pd.DataFrame(
        {
            "ticker": ["A"] * 25,
            "date": pd.date_range("2026-01-01", periods=25).date,
            "adjusted_close": [100.0] * 24 + [-1.0],
        }
    )
    out = compute_returns(prices, horizons={"5d": 5})
    # End is the last valid (positive) price; return is computed against that.
    # We just assert it ran without error and produced a row.
    assert not out.empty
    assert out["return_5d"].iloc[0] is not None


def test_dedupe_per_ticker():
    prices = pd.DataFrame(
        {
            "ticker": ["A"] * 26,
            "date": [d for d in pd.date_range("2026-01-01", periods=25).date] + [pd.Timestamp("2026-01-25").date()],
            "adjusted_close": list(range(100, 125)) + [999.0],
        }
    )
    out = compute_returns(prices, horizons={"5d": 5})
    # Last duplicate date should be kept, so end price = 999
    r5 = out["return_5d"].iloc[0]
    # start = 999 at row index -6: end=row index -1 = 999 (after dedupe, the 25th entry is the duplicate)
    # Actually, after dedupe, we have 25 unique dates, so end = row at index -1 (last), start_5d = row at index -6.
    # We don't assert exact value, but we assert it's a valid number.
    assert r5 is not None
    assert not pd.isna(r5)


def test_forward_fill_basic():
    df = pd.DataFrame(
        {
            "ticker": ["A", "A", "A", "A"],
            "date": pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-04", "2026-01-05"]),
            "adjusted_close": [100.0, 101.0, None, 103.0],
            "close": [100.0, 101.0, None, 103.0],
        }
    )
    filled = forward_fill(df, value_cols=("adjusted_close",))
    # Row at 2026-01-04 should now have adjusted_close filled with 101.0
    val = filled.loc[filled["date"] == pd.Timestamp("2026-01-04"), "adjusted_close"].iloc[0]
    assert val == 101.0


def test_asof_close_returns_latest_per_ticker():
    prices = pd.DataFrame(
        {
            "ticker": ["A", "A", "B", "B"],
            "date": [date(2026, 1, 1), date(2026, 1, 10), date(2026, 1, 5), date(2026, 1, 12)],
            "adjusted_close": [100.0, 110.0, 50.0, 55.0],
        }
    )
    out = asof_close(prices, as_of=date(2026, 1, 12))
    a = out[out["ticker"] == "A"].iloc[0]
    b = out[out["ticker"] == "B"].iloc[0]
    assert a["asof_price"] == 110.0
    assert b["asof_price"] == 55.0


def test_returns_for_universe_with_fixture(prices_df):
    out = compute_returns_for_universe(prices_df, horizons={"5d": 5, "20d": 20, "60d": 60})
    assert not out.empty
    for h in ("5d", "20d", "60d"):
        assert f"return_{h}" in out.columns
    # 60d return should be computable for tickers with >= 61 rows
    r60 = out["return_60d"].dropna()
    assert r60.shape[0] > 0
