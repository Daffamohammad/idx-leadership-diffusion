"""Tests for the breadth engine."""
from __future__ import annotations

import pandas as pd
import pytest

from idx_leadership.features.breadth import compute_breadth


def _features(rows):
    return pd.DataFrame(rows)


def test_all_positive():
    feats = _features(
        [
            {"ticker": "A", "return_20d": 5.0, "excess_return_20d": 3.0, "excess_return_5d": 1.0, "excess_return_60d": 0.0},
            {"ticker": "B", "return_20d": 2.0, "excess_return_20d": 1.0, "excess_return_5d": 0.5, "excess_return_60d": -0.5},
            {"ticker": "C", "return_20d": -1.0, "excess_return_20d": -2.0, "excess_return_5d": -0.5, "excess_return_60d": 0.0},
        ]
    )
    r = compute_breadth(feats, total_constituents=3)
    assert r.positive_return_share == round((2 / 3) * 100, 2)
    assert r.benchmark_outperformance_share == round((2 / 3) * 100, 2)
    assert r.usable_constituents == 3
    assert r.missing_constituents == 0


def test_missing_constituents():
    feats = _features(
        [
            {"ticker": "A", "return_20d": 5.0, "excess_return_20d": 3.0, "excess_return_5d": 1.0, "excess_return_60d": 0.0},
        ]
    )
    r = compute_breadth(feats, total_constituents=4)
    assert r.usable_constituents == 1
    assert r.missing_constituents == 3


def test_empty_features():
    r = compute_breadth(pd.DataFrame(), total_constituents=5)
    assert r.usable_constituents == 0
    assert r.total_constituents == 5
    assert r.missing_constituents == 5


def test_zero_eligible_constituents():
    r = compute_breadth(pd.DataFrame(), total_constituents=0)
    assert r.usable_constituents == 0
    assert r.total_constituents == 0
    assert r.missing_constituents == 0


def test_breadth_bounded_invariant():
    feats = _features(
        [
            {"ticker": "A", "return_20d": 5.0, "excess_return_20d": 3.0, "excess_return_5d": 1.0, "excess_return_60d": 0.0},
            {"ticker": "B", "return_20d": -2.0, "excess_return_20d": -1.0, "excess_return_5d": -0.5, "excess_return_60d": 0.0},
        ]
    )
    r = compute_breadth(feats, total_constituents=2)
    assert 0.0 <= r.positive_return_share <= 100.0
    assert 0.0 <= r.benchmark_outperformance_share <= 100.0


def test_threshold_edge_case():
    feats = _features(
        [
            {"ticker": "A", "return_20d": 5.0, "excess_return_20d": 3.0, "excess_return_5d": 0.0, "excess_return_60d": 0.0},
            {"ticker": "B", "return_20d": 5.0, "excess_return_20d": 3.0, "excess_return_5d": 0.0, "excess_return_60d": 0.0},
        ]
    )
    r = compute_breadth(feats, total_constituents=2)
    # Both improve vs 60d baseline equally -> improving count = 0
    assert r.improving_count == 0
    # Both positive
    assert r.positive_count == 2


def test_each_metric_exposes_its_own_denominator_contract():
    feats = _features(
        [
            {
                "ticker": "A",
                "return_5d": 1.0,
                "return_20d": 2.0,
                "return_60d": 3.0,
                "excess_return_20d": 1.0,
                "excess_return_5d": 2.0,
                "excess_return_60d": 1.0,
            },
            {
                "ticker": "B",
                "return_5d": -1.0,
                "return_20d": -2.0,
                "return_60d": None,
                "excess_return_20d": None,
                "excess_return_5d": 0.0,
                "excess_return_60d": 1.0,
            },
            {
                "ticker": "C",
                "return_5d": None,
                "return_20d": None,
                "return_60d": None,
                "excess_return_20d": -1.0,
                "excess_return_5d": None,
                "excess_return_60d": None,
            },
        ]
    )
    result = compute_breadth(feats, total_constituents=4)

    positive = result.metric("positive_return")
    assert (positive.numerator, positive.eligible_denominator) == (1, 2)
    assert (positive.missing_count, positive.total_count) == (2, 4)
    outperformance = result.metric("benchmark_outperformance")
    assert (outperformance.numerator, outperformance.eligible_denominator) == (1, 2)
    assert outperformance.missing_count == 2
    medium = result.metric("medium_horizon_positive_return")
    assert (medium.numerator, medium.eligible_denominator, medium.missing_count) == (
        1,
        1,
        3,
    )


def test_all_missing_is_undefined_not_zero_breadth():
    feats = _features(
        [
            {"ticker": "A", "return_20d": None, "excess_return_20d": None},
            {"ticker": "B", "return_20d": None, "excess_return_20d": None},
        ]
    )
    result = compute_breadth(feats, total_constituents=2)
    metric = result.metric("positive_return")
    assert metric.share is None
    assert metric.status == "UNDEFINED_NO_ELIGIBLE"
    assert (metric.numerator, metric.eligible_denominator, metric.missing_count) == (
        0,
        0,
        2,
    )


def test_stale_and_newly_listed_constituents_are_missing_evidence():
    feats = _features(
        [
            {"ticker": "A", "return_20d": 5.0, "is_stale": False},
            {"ticker": "B", "return_20d": 4.0, "is_stale": True},
            {"ticker": "NEW", "return_20d": None, "is_stale": False},
        ]
    )
    result = compute_breadth(
        feats, total_constituents=4, stale_col="is_stale"
    )
    metric = result.metric("positive_return")
    assert metric.share == 100.0
    assert metric.eligible_denominator == 1
    assert metric.missing_count == 3


def test_mixed_benchmark_dates_are_excluded_from_outperformance():
    feats = _features(
        [
            {
                "ticker": "A",
                "return_20d": 2.0,
                "excess_return_20d": 1.0,
                "as_of": "2026-08-20",
                "benchmark_as_of": "2026-08-20",
            },
            {
                "ticker": "B",
                "return_20d": 2.0,
                "excess_return_20d": 1.0,
                "as_of": "2026-08-20",
                "benchmark_as_of": "2026-08-19",
            },
        ]
    )
    result = compute_breadth(
        feats,
        total_constituents=2,
        observation_date_col="as_of",
        benchmark_date_col="benchmark_as_of",
    )
    metric = result.metric("benchmark_outperformance")
    assert (metric.numerator, metric.eligible_denominator, metric.missing_count) == (
        1,
        1,
        1,
    )


def test_missing_metric_column_reports_unavailable_with_full_counts():
    result = compute_breadth(
        _features([{"ticker": "A", "return_20d": 1.0}]),
        total_constituents=1,
    )
    metric = result.metric("benchmark_outperformance")
    assert metric.status == "UNAVAILABLE"
    assert metric.share is None
    assert metric.total_count == metric.missing_count == 1
