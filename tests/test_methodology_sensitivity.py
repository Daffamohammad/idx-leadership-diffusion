"""Offline horizon and group-size sensitivity tests."""
from __future__ import annotations

import pandas as pd
from pandas.testing import assert_frame_equal

from idx_leadership.analytics.sensitivity import (
    GROUP_SIZES,
    HORIZON_VARIANTS,
    build_group_size_sensitivity,
    build_horizon_state_histories,
    evaluate_horizon_sensitivity,
    recommend_minimum_group_size,
)


def test_constrained_horizon_variants_are_exact_and_non_predictive():
    assert [(v.label, v.short, v.primary, v.long) for v in HORIZON_VARIANTS] == [
        ("5/20/60", 5, 20, 60),
        ("10/20/60", 10, 20, 60),
        ("10/40", 10, 40, 40),
        ("20/60", 20, 20, 60),
    ]


def _state_history(variant: str) -> pd.DataFrame:
    dates = pd.date_range("2026-07-03", periods=4, freq="7D")
    rows = []
    for index, snapshot_date in enumerate(dates):
        states = ["LAGGING", "IMPROVING", "LEADING", "LEADING"]
        if variant == "10/20/60" and index == 1:
            states = ["LAGGING", "LEADING", "LEADING", "LEADING"]
        for group_index, group_id in enumerate(("A", "B", "C"), start=1):
            rows.append(
                {
                    "snapshot_date": snapshot_date,
                    "group_id": group_id,
                    "leadership_state": states[index],
                    "leadership_rank": (
                        4 - group_index
                        if variant == "10/20/60"
                        else group_index
                    ),
                }
            )
    return pd.DataFrame(rows)


def test_horizon_evaluation_reports_agreement_rank_churn_duration_and_coverage():
    histories = {
        "5/20/60": _state_history("5/20/60"),
        "10/20/60": _state_history("10/20/60"),
    }
    summary = evaluate_horizon_sensitivity(histories).set_index("variant")

    assert summary.loc["5/20/60", "state_agreement"] == 1.0
    assert summary.loc["5/20/60", "mean_rank_correlation"] == 1.0
    assert summary.loc["5/20/60", "coverage"] == 1.0
    assert summary.loc["5/20/60", "transition_rate"] > 0
    assert summary.loc["5/20/60", "median_state_duration"] >= 1
    assert summary.loc["10/20/60", "state_agreement"] < 1.0
    assert summary.loc["10/20/60", "mean_rank_correlation"] == -1.0


def test_group_size_harness_covers_required_sizes_and_count_confirmation():
    scenarios, summary = build_group_size_sensitivity(thresholds_pp=(10.0,))
    assert tuple(sorted(summary["group_size"].unique())) == GROUP_SIZES

    small_one_name = scenarios[
        (scenarios["group_size"] == 3)
        & (scenarios["net_changed_constituents"] == 1)
    ].iloc[0]
    assert small_one_name["baseline_state"] == "BROADENING"
    assert small_one_name["candidate_detail_state"] == "BROADENING_FRAGILE"
    assert small_one_name["candidate_state"] == "STABLE"

    large_two_names = scenarios[
        (scenarios["group_size"] == 20)
        & (scenarios["net_changed_constituents"] == 2)
    ].iloc[0]
    assert large_two_names["breadth_delta_pp"] == 10.0
    assert large_two_names["candidate_detail_state"] == "BROADENING_FIRM"
    assert large_two_names["candidate_state"] == "BROADENING"

    candidate, basis = recommend_minimum_group_size()
    assert candidate == 4
    assert "not live IDX validation" in basis


def _price_inputs():
    dates = pd.bdate_range("2026-01-02", periods=75)
    prices = pd.DataFrame(
        [
            {
                "ticker": ticker,
                "date": snapshot_date,
                "adjusted_close": base + slope * index,
            }
            for ticker, base, slope in (("A", 100.0, 1.0), ("B", 100.0, 0.5))
            for index, snapshot_date in enumerate(dates)
        ]
    )
    benchmark = pd.DataFrame(
        {
            "date": dates,
            "close": [100.0 + 0.4 * index for index in range(len(dates))],
        }
    )
    taxonomy = pd.DataFrame(
        {"ticker": ["A", "B"], "group_id": ["G1", "G2"]}
    )
    return dates, prices, benchmark, taxonomy


def test_horizon_history_is_invariant_to_future_price_rows():
    dates, prices, benchmark, taxonomy = _price_inputs()
    as_of = dates[65]
    baseline = build_horizon_state_histories(
        prices=prices,
        benchmark=benchmark,
        taxonomy=taxonomy,
        as_of_dates=[as_of],
        min_constituents=1,
    )["5/20/60"]

    future_dates = pd.bdate_range(dates[-1] + pd.Timedelta(days=1), periods=5)
    future_prices = pd.DataFrame(
        [
            {"ticker": ticker, "date": snapshot_date, "adjusted_close": value}
            for ticker, value in (("A", 1.0), ("B", 10_000.0))
            for snapshot_date in future_dates
        ]
    )
    future_benchmark = pd.DataFrame(
        {"date": future_dates, "close": [10_000.0] * len(future_dates)}
    )
    with_future = build_horizon_state_histories(
        prices=pd.concat([prices, future_prices], ignore_index=True),
        benchmark=pd.concat([benchmark, future_benchmark], ignore_index=True),
        taxonomy=taxonomy,
        as_of_dates=[as_of],
        min_constituents=1,
    )["5/20/60"]

    assert_frame_equal(baseline, with_future)
