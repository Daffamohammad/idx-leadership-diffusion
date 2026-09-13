"""Golden financial datasets — tiny, hand-verifiable, independent of fixtures.

Each expected value below was computed by hand from the stated inputs.
If the implementation changes semantics, these tests must fail loudly
rather than be re-blessed.
"""
from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from idx_leadership.aggregation.groups import rank_groups
from idx_leadership.features.breadth import compute_breadth
from idx_leadership.features.concentration_v2 import compute_concentration_v2
from idx_leadership.features.relative_strength import (
    compute_excess_returns,
    compute_ytd_excess_returns,
)
from idx_leadership.features.returns import compute_returns
from idx_leadership.models import GroupSnapshot


def _prices(rows):
    return pd.DataFrame(rows)


def test_golden_simple_return_is_exact():
    # 100.0 -> 110.0 over exactly 5 sessions => +10.0%
    closes = [100.0, 102.0, 101.0, 103.0, 105.0, 110.0]
    base = date(2026, 8, 13)
    prices = _prices(
        [
            {
                "ticker": "A.JK",
                "date": (pd.Timestamp(base) + pd.Timedelta(days=i)).date(),
                "adjusted_close": c,
            }
            for i, c in enumerate(closes)
        ]
    )
    out = compute_returns(prices, horizons={"5d": 5})
    assert out.iloc[0]["return_5d"] == pytest.approx(10.0)
    assert out.iloc[0]["return_5d_start_date"] == base


def test_golden_insufficient_history_is_none_not_zero():
    closes = [100.0, 101.0, 102.0]  # only 3 rows: 5d needs 6
    base = date(2026, 8, 18)
    prices = _prices(
        [
            {
                "ticker": "A.JK",
                "date": (pd.Timestamp(base) + pd.Timedelta(days=i)).date(),
                "adjusted_close": c,
            }
            for i, c in enumerate(closes)
        ]
    )
    out = compute_returns(prices, horizons={"5d": 5})
    assert out.iloc[0]["return_5d"] is None


def test_golden_excess_is_percentage_point_difference():
    # Security +10%, benchmark +4% => excess +6pp (simple difference).
    base = date(2026, 8, 13)
    sec = [100.0, 102.0, 101.0, 103.0, 105.0, 110.0]
    bench = [1000.0, 1005.0, 1003.0, 1010.0, 1020.0, 1040.0]
    prices = _prices(
        [
            {
                "ticker": "A.JK",
                "date": (pd.Timestamp(base) + pd.Timedelta(days=i)).date(),
                "adjusted_close": c,
            }
            for i, c in enumerate(sec)
        ]
    )
    benchmark = _prices(
        [
            {
                "benchmark_id": "IHSG",
                "date": (pd.Timestamp(base) + pd.Timedelta(days=i)).date(),
                "close": c,
            }
            for i, c in enumerate(bench)
        ]
    )
    out = compute_excess_returns(
        prices, benchmark, horizons={"5d": 5}, as_of=date(2026, 8, 18)
    )
    assert out.iloc[0]["return_5d"] == pytest.approx(10.0)
    assert out.iloc[0]["benchmark_return_5d"] == pytest.approx(4.0)
    assert out.iloc[0]["excess_return_5d"] == pytest.approx(6.0)


def test_golden_ytd_uses_mutual_baseline():
    # Common Dec-30 baseline 100/1000; ends Jan-05 110/1040 => +10%/+4%.
    sec = [
        ("2025-12-30", 100.0),
        ("2026-01-02", 105.0),
        ("2026-01-05", 110.0),
    ]
    bench = [
        ("2025-12-30", 1000.0),
        ("2026-01-02", 1020.0),
        ("2026-01-05", 1040.0),
    ]
    prices = _prices(
        [
            {"ticker": "A.JK", "date": pd.Timestamp(d).date(), "adjusted_close": c}
            for d, c in sec
        ]
    )
    benchmark = _prices(
        [
            {
                "benchmark_id": "IHSG",
                "date": pd.Timestamp(d).date(),
                "close": c,
            }
            for d, c in bench
        ]
    )
    out = compute_ytd_excess_returns(
        prices, benchmark, as_of=date(2026, 1, 5)
    )
    assert len(out) == 1
    assert out.iloc[0]["return_ytd"] == pytest.approx(10.0)
    assert out.iloc[0]["benchmark_return_ytd"] == pytest.approx(4.0)
    assert out.iloc[0]["excess_return_ytd"] == pytest.approx(6.0)
    assert out.iloc[0]["return_ytd_start_date"] == date(2025, 12, 30)


def test_golden_breadth_counts_and_denominators():
    # 5 constituents, 4 observed: 3 outperforming => 75.0, missing 1.
    features = pd.DataFrame(
        {
            "ticker": ["A", "B", "C", "D"],
            "excess_return_20d": [5.0, 3.0, 1.0, -2.0],
        }
    )
    result = compute_breadth(features, total_constituents=5)
    metric = result.metric("benchmark_outperformance")
    assert metric.share == 75.0
    assert metric.numerator == 3
    assert metric.eligible_denominator == 4
    assert metric.missing_count == 1
    assert metric.total_count == 5


def test_golden_single_name_concentration_is_total():
    base = date(2026, 7, 1)
    prices = _prices(
        [
            {
                "ticker": "ONLY.JK",
                "date": (pd.Timestamp(base) + pd.Timedelta(days=i)).date(),
                "adjusted_close": 100.0 + i,
            }
            for i in range(25)
        ]
    )
    result = compute_concentration_v2(
        prices, group_tickers=["ONLY.JK"], horizon=20, as_of=date(2026, 7, 25)
    )
    assert result.top1_abs_share == 1.0
    assert result.hhi == 1.0
    assert result.status == "DEFINED"


def test_golden_ranking_is_deterministic_with_ties():
    def snap(group_id, excess):
        return GroupSnapshot(
            snapshot_date=date(2026, 8, 20),
            taxonomy_level="sector",
            group_id=group_id,
            group_name=group_id,
            constituent_count=10,
            eligible_count=10,
            group_excess_return=excess,
            breadth_outperforming=50.0,
            breadth_delta=0.0,
            leadership_state="LEADING",
            diffusion_state="STABLE",
            concentration={},
        )

    first = {s.group_id: s.leadership_rank for s in rank_groups(
        [snap("B", 5.0), snap("A", 5.0), snap("C", 1.0)]
    )}
    second = {s.group_id: s.leadership_rank for s in rank_groups(
        [snap("B", 5.0), snap("A", 5.0), snap("C", 1.0)]
    )}
    assert first == second
    assert first["C"] == 3
    assert sorted([first["A"], first["B"]]) == [1, 2]


def test_claim_permissions_and_wording_guard():
    from idx_leadership.analytics.claim_gates import (
        assert_no_market_wide_phrasing,
        claim_permissions,
        market_scope,
    )

    live_complete = {
        "coverage_state": "COMPLETE",
        "coverage_gate_60pct_met": True,
        "provider_mode": "SECTORS_LIVE",
    }
    assert market_scope(live_complete) == "market-wide"
    assert market_scope({}) == "within the tracked universe"
    assert market_scope({"coverage_state": "COMPLETE"}) == "within the tracked universe"

    perms = claim_permissions(live_complete, has_ytd_baseline=True)
    assert perms["market_wide_narrative"]["status"] == "PERMITTED"
    assert perms["foreign_flow"]["status"] == "BLOCKED"

    gapped = claim_permissions({"coverage_state": "PARTIAL_SYMBOLS"})
    assert gapped["market_wide_narrative"]["status"] == "BLOCKED"
    assert gapped["breadth"]["status"] == "CAVEAT"
    assert "tracked universe" in gapped["breadth"]["reason"]

    assert_no_market_wide_phrasing("Leadership strengthened as participation broadened.")
    for banned in ("market-wide breadth", "Full Universe rally", "all stocks rose"):
        try:
            assert_no_market_wide_phrasing(banned)
        except ValueError:
            pass
        else:
            raise AssertionError(f"phrasing not caught: {banned}")
