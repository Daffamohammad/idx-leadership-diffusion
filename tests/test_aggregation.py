"""Tests for group aggregation."""
from __future__ import annotations

import tempfile
import shutil
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from idx_leadership.aggregation.groups import (
    aggregate_history,
    build_group_snapshots,
    rank_groups,
)
from idx_leadership.features.relative_strength import compute_excess_returns
from idx_leadership.models import GroupSnapshot, LeadershipState
from idx_leadership.signals.diffusion_v2 import DiffusionStateV2


def test_build_group_snapshots_basic(prices_df, benchmark_df, taxonomy_df):
    as_of = date(2026, 8, 20)
    features = compute_excess_returns(prices_df, benchmark_df, horizons={"5d": 5, "20d": 20, "60d": 60}, as_of=as_of)
    snaps = build_group_snapshots(
        features=features,
        taxonomy=taxonomy_df,
        snapshot_date=as_of,
        prices=prices_df,
        horizons={"5d": 5, "20d": 20, "60d": 60},
        min_constituents=1,  # relax for the small fixture
        min_coverage_pct=0.0,
    )
    assert len(snaps) > 0
    gids = {s.group_id for s in snaps}
    assert "Financials" in gids
    assert "Telecom" in gids
    assert "Industrial" in gids
    assert "Consumer" in gids


def test_group_snapshot_preserves_taxonomy_path_when_features_include_taxonomy(
    prices_df, benchmark_df, taxonomy_df
):
    """A shared feature/taxonomy frame must not suffix away the hierarchy."""
    as_of = date(2026, 8, 20)
    features = compute_excess_returns(
        prices_df,
        benchmark_df,
        horizons={"5d": 5, "20d": 20, "60d": 60},
        as_of=as_of,
    ).merge(taxonomy_df[["ticker", "sector", "subsector"]], on="ticker", how="left")

    snapshots = build_group_snapshots(
        features=features,
        taxonomy=taxonomy_df,
        snapshot_date=as_of,
        prices=prices_df,
        horizons={"5d": 5, "20d": 20, "60d": 60},
        min_constituents=1,
        min_coverage_pct=0.0,
    )

    financials = next(item for item in snapshots if item.group_id == "Financials")
    assert financials.taxonomy_path == ["Financials", "Banks"]


def test_rank_groups_assigns_ranks(prices_df, benchmark_df, taxonomy_df):
    as_of = date(2026, 8, 20)
    features = compute_excess_returns(prices_df, benchmark_df, horizons={"5d": 5, "20d": 20, "60d": 60}, as_of=as_of)
    snaps = build_group_snapshots(
        features=features,
        taxonomy=taxonomy_df,
        snapshot_date=as_of,
        prices=prices_df,
        horizons={"5d": 5, "20d": 20, "60d": 60},
        min_constituents=1,
        min_coverage_pct=0.0,
    )
    snaps = rank_groups(snaps)
    # All groups that are not UNCONFIRMED should have a leadership_rank
    ranks = [s.leadership_rank for s in snaps if s.leadership_rank is not None]
    assert len(ranks) > 0
    # Ranks must be 1..N and unique
    assert sorted(ranks) == list(range(1, len(ranks) + 1))


def test_aggregate_history_long_format(prices_df, benchmark_df, taxonomy_df):
    as_of = date(2026, 8, 20)
    features = compute_excess_returns(prices_df, benchmark_df, horizons={"5d": 5, "20d": 20, "60d": 60}, as_of=as_of)
    snaps = build_group_snapshots(
        features=features,
        taxonomy=taxonomy_df,
        snapshot_date=as_of,
        prices=prices_df,
        horizons={"5d": 5, "20d": 20, "60d": 60},
        min_constituents=1,
        min_coverage_pct=0.0,
    )
    snaps = rank_groups(snaps)
    long = aggregate_history({as_of: snaps})
    assert not long.empty
    assert "leadership_state" in long.columns
    assert "diffusion_state" in long.columns


def test_build_group_snapshots_uses_configured_v2_engines(
    prices_df, benchmark_df, taxonomy_df
):
    """The configured v2 contract must reach the group model, not just metadata."""
    as_of = date(2026, 8, 20)
    features = compute_excess_returns(
        prices_df,
        benchmark_df,
        horizons={"5d": 5, "20d": 20, "60d": 60},
        as_of=as_of,
    )
    previous = [
        GroupSnapshot(
            snapshot_date=date(2026, 8, 13),
            group_id="Financials",
            breadth_outperforming=0.0,
        )
    ]

    snaps = build_group_snapshots(
        features=features,
        taxonomy=taxonomy_df,
        snapshot_date=as_of,
        prices=prices_df,
        horizons={"5d": 5, "20d": 20, "60d": 60},
        min_constituents=1,
        min_coverage_pct=0.0,
        previous_groups=previous,
        method_version="methodology-v2",
        feature_version="features-v2",
        diffusion_mode="group_size_aware",
        concentration_mode="absolute_move_v2",
    )
    financials = next(s for s in snaps if s.group_id == "Financials")

    assert financials.method_version == "methodology-v2"
    assert financials.feature_version == "features-v2"
    assert financials.concentration.convention == "absolute_move_v2"
    assert financials.concentration.hhi_contribution is not None
    assert financials.diffusion_state_v2 == DiffusionStateV2.BROADENING_FIRM
    # The legacy field remains a deliberate v1 projection for old consumers.
    assert financials.diffusion_state.value == "BROADENING"


def test_group_denominators_retain_constituents_missing_features(
    prices_df, benchmark_df, taxonomy_df
):
    as_of = date(2026, 8, 20)
    features = compute_excess_returns(
        prices_df,
        benchmark_df,
        horizons={"5d": 5, "20d": 20, "60d": 60},
        as_of=as_of,
    )
    features = features[features["ticker"] != "BBCA.JK"]

    snapshots = build_group_snapshots(
        features=features,
        taxonomy=taxonomy_df,
        snapshot_date=as_of,
        prices=prices_df,
        horizons={"5d": 5, "20d": 20, "60d": 60},
        min_constituents=1,
        min_coverage_pct=0.0,
    )

    financials = next(s for s in snapshots if s.group_id == "Financials")
    assert financials.constituent_count == 4
    assert financials.eligible_count == 3
    assert financials.missing_count == 1
    assert financials.breadth_missing_count == 1


def test_group_snapshots_keep_taxonomy_groups_when_features_are_empty(
    prices_df, taxonomy_df
):
    """A failed acquisition must produce explicit group-level data gaps."""
    snapshots = build_group_snapshots(
        features=pd.DataFrame(),
        taxonomy=taxonomy_df,
        snapshot_date=date(2026, 8, 20),
        prices=prices_df.iloc[0:0],
        horizons={"5d": 5, "20d": 20, "60d": 60},
        min_constituents=1,
        min_coverage_pct=0.0,
    )

    assert {snapshot.group_id for snapshot in snapshots} == {
        "Financials",
        "Telecom",
        "Industrial",
        "Consumer",
    }
    assert all(snapshot.leadership_state == LeadershipState.UNCONFIRMED for snapshot in snapshots)
    assert all(snapshot.eligible_count == 0 for snapshot in snapshots)
    assert all(snapshot.missing_count == snapshot.constituent_count for snapshot in snapshots)


def test_leadership_classification_uses_primary_20d_excess_return(
    prices_df, taxonomy_df
):
    """A negative 20D return with positive acceleration is IMPROVING, not LEADING."""
    features = pd.DataFrame(
        [
            {
                "ticker": "BBCA.JK",
                "return_20d": 1.0,
                "excess_return_20d": -2.0,
                "excess_return_5d": 5.0,
                "excess_return_60d": 0.0,
            }
        ]
    )
    snapshots = build_group_snapshots(
        features=features,
        taxonomy=taxonomy_df,
        snapshot_date=date(2026, 8, 20),
        prices=prices_df,
        horizons={"5d": 5, "20d": 20, "60d": 60},
        min_constituents=1,
        min_coverage_pct=0.0,
    )

    financials = next(s for s in snapshots if s.group_id == "Financials")
    assert financials.leadership_state == LeadershipState.IMPROVING


def test_paired_breadth_delta_uses_identical_names(prices_df, benchmark_df, taxonomy_df):
    """Breadth deltas compare the same names at both dates when stored cohorts exist."""
    as_of = date(2026, 8, 20)
    features = compute_excess_returns(
        prices_df,
        benchmark_df,
        horizons={"5d": 5, "20d": 20, "60d": 60},
        as_of=as_of,
    )
    first = build_group_snapshots(
        features=features,
        taxonomy=taxonomy_df,
        snapshot_date=as_of,
        prices=prices_df,
        horizons={"5d": 5, "20d": 20, "60d": 60},
        min_constituents=1,
        min_coverage_pct=0.0,
    )
    base = next(s for s in first if s.group_id == "Financials")
    assert base.breadth_eligible_tickers
    assert set(base.breadth_outperforming_tickers) <= set(base.breadth_eligible_tickers)

    # Ragged second run: BBCA.JK loses its 20D reading, so the paired
    # comparison must exclude it from both ends.
    ragged = features[features["ticker"] != "BBCA.JK"]
    second = build_group_snapshots(
        features=ragged,
        taxonomy=taxonomy_df,
        snapshot_date=as_of,
        prices=prices_df,
        horizons={"5d": 5, "20d": 20, "60d": 60},
        min_constituents=1,
        min_coverage_pct=0.0,
        previous_groups=first,
    )
    current = next(s for s in second if s.group_id == "Financials")
    assert "BBCA.JK" not in current.breadth_eligible_tickers
    paired = sorted(set(current.breadth_eligible_tickers) & set(base.breadth_eligible_tickers))
    assert paired
    current_count = len(set(current.breadth_outperforming_tickers) & set(paired))
    previous_count = len(set(base.breadth_outperforming_tickers) & set(paired))
    expected = round(current_count / len(paired) * 100.0, 2) - round(
        previous_count / len(paired) * 100.0, 2
    )
    assert current.breadth_delta == pytest.approx(expected)


def test_concentration_excludes_tickers_without_20d_readings(prices_df, benchmark_df, taxonomy_df):
    """Concentration runs over the actual 20D return cohort, not all members."""
    as_of = date(2026, 8, 20)
    features = compute_excess_returns(
        prices_df,
        benchmark_df,
        horizons={"5d": 5, "20d": 20, "60d": 60},
        as_of=as_of,
    )
    full = build_group_snapshots(
        features=features,
        taxonomy=taxonomy_df,
        snapshot_date=as_of,
        prices=prices_df,
        horizons={"5d": 5, "20d": 20, "60d": 60},
        min_constituents=1,
        min_coverage_pct=0.0,
        concentration_mode="absolute_move_v2",
    )
    ragged = build_group_snapshots(
        features=features[features["ticker"] != "BBCA.JK"],
        taxonomy=taxonomy_df,
        snapshot_date=as_of,
        prices=prices_df,
        horizons={"5d": 5, "20d": 20, "60d": 60},
        min_constituents=1,
        min_coverage_pct=0.0,
        concentration_mode="absolute_move_v2",
    )
    before = next(s for s in full if s.group_id == "Financials").concentration.contributor_count
    after = next(s for s in ragged if s.group_id == "Financials").concentration.contributor_count
    assert after == before - 1
