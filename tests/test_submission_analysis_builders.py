"""Boundary checks for the release-bound breadth calculations."""
from __future__ import annotations

import pandas as pd
import pytest

from scripts.build_market_breadth import (
    _breaks_range,
    _calendar_window_sessions,
    _covers_calendar_window_start,
    _complete_history_tickers,
    _directional_snapshot,
)


def test_directional_counts_and_value_shares_reconcile_and_keep_constituents():
    rows = [
        {"ticker": "UP.JK", "company_name": "Up Ltd", "return_1d": 5.0, "value_idr": 100.0},
        {"ticker": "FLAT.JK", "company_name": "Flat Ltd", "return_1d": 0.0, "value_idr": 0.0},
        {"ticker": "DOWN.JK", "company_name": "Down Ltd", "return_1d": -2.0, "value_idr": 300.0},
        {"ticker": "NO-CLOSE.JK", "company_name": "No comparable close", "return_1d": None, "value_idr": 1_000.0},
    ]

    result = _directional_snapshot(rows)

    assert {key: len(value) for key, value in result["categories"].items()} == {
        "advancing": 1, "unchanged": 1, "declining": 1,
    }
    assert len(result["moving"]) == 3
    assert result["denominator_idr"] == 400
    assert result["coverage_count"] == 3
    assert result["value_shares"] == {"advancing": 25.0, "unchanged": 0.0, "declining": 75.0}
    assert result["constituents"]["advancing"][0]["ticker"] == "UP.JK"
    assert result["constituents"]["declining"][0]["return_1d_pct"] == -2.0


def test_zero_value_denominator_keeps_shares_unavailable():
    rows = [
        {"ticker": "UP.JK", "return_1d": 1.0, "value_idr": 0},
        {"ticker": "DOWN.JK", "return_1d": -1.0, "value_idr": 0},
    ]

    result = _directional_snapshot(rows)

    assert result["denominator_idr"] == 0
    assert result["value_shares"] == {"advancing": None, "unchanged": None, "declining": None}


def test_new_highs_and_lows_require_a_strict_break():
    assert not _breaks_range(10.0, [8.0, 10.0], side="high")
    assert _breaks_range(10.01, [8.0, 10.0], side="high")
    assert not _breaks_range(8.0, [8.0, 10.0], side="low")
    assert _breaks_range(7.99, [8.0, 10.0], side="low")
    assert not _breaks_range(10.0, [], side="high")
    with pytest.raises(ValueError, match="unsupported"):
        _breaks_range(10.0, [9.0], side="flat")


def test_high_low_denominator_excludes_incomplete_price_histories():
    close = pd.DataFrame(
        [[10.0, 11.0, 12.0], [20.0, None, 22.0]],
        index=["COMPLETE.JK", "GAP.JK"],
        columns=["2026-09-29", "2026-09-30", "2026-10-01"],
    )

    assert _complete_history_tickers(close, {"COMPLETE.JK", "GAP.JK", "ABSENT.JK"}, list(close.columns)) == ["COMPLETE.JK"]
    assert _complete_history_tickers(close, {"COMPLETE.JK"}, []) == []


def test_52_week_window_accepts_a_non_trading_calendar_cutoff():
    sessions = ["2025-09-30", "2025-10-02", "2025-10-06", "2026-10-02"]
    cutoff = "2025-10-04"  # Saturday; the next observed session is 6 October.

    assert _covers_calendar_window_start(sessions, cutoff)
    assert _calendar_window_sessions(sessions, cutoff, "2026-10-02") == [
        "2025-10-06",
    ]


def test_52_week_window_is_omitted_when_the_vintage_starts_after_cutoff():
    sessions = ["2025-12-15", "2025-12-16", "2026-10-02"]

    assert not _covers_calendar_window_start(sessions, "2025-10-03")
    assert _calendar_window_sessions(sessions, "2025-10-03", "2026-10-02") == sessions[:-1]
