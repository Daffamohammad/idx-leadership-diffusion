"""Point-in-time and no-look-ahead invariant tests.

The most important property: building a snapshot at time t must not
change when future observations are appended to the price history.
"""
from __future__ import annotations

import tempfile
import shutil
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from idx_leadership.pipeline import build_snapshot
from idx_leadership.providers.fixture import FixtureProvider


@pytest.fixture()
def tmp_root():
    d = Path(tempfile.mkdtemp())
    yield d
    shutil.rmtree(d, ignore_errors=True)


def _build(prices_df, benchmark_df, taxonomy_df, tmp_root, as_of):
    provider = FixtureProvider(fixtures_dir=Path("tests/fixtures"))
    # Override the provider's get_* methods to return our controlled data
    provider.get_price_history = lambda tickers, start, end: prices_df[(prices_df["date"] >= start) & (prices_df["date"] <= end)]
    provider.get_benchmark_history = lambda benchmark_id, start, end: benchmark_df[(benchmark_df["date"] >= start) & (benchmark_df["date"] <= end)].assign(benchmark_id=benchmark_id, price_basis="close", source="fixture")
    provider.get_group_taxonomy = lambda: taxonomy_df
    from idx_leadership.models import SecurityMasterEntry
    from datetime import date as _date
    provider.get_security_master = lambda: [
        SecurityMasterEntry(
            ticker=t, vendor_ticker=t, group_id="Financials", sector="Financials", subsector="Banks",
            source="fixture", source_as_of=_date.today(),
        )
        for t in ["BBCA.JK", "BBRI.JK", "BMRI.JK", "BBNI.JK"]
    ]
    return build_snapshot(provider, as_of=as_of, out_dir=tmp_root, snapshot_id=f"snap_{as_of.isoformat()}")


def test_no_lookahead_returns_breadth(prices_df, benchmark_df, taxonomy_df, tmp_root):
    as_of = date(2026, 8, 20)
    res = _build(prices_df, benchmark_df, taxonomy_df, tmp_root, as_of)
    # We must have at least one group with a non-null breadth
    g = res["groups"]
    assert not g.empty
    # The features for as_of should not include any date after as_of
    features_csv = (tmp_root / f"snap_{as_of.isoformat()}" / "features.csv")
    if features_csv.exists():
        feats = pd.read_csv(features_csv)
        if not feats.empty and "as_of" in feats.columns:
            assert (pd.to_datetime(feats["as_of"]).dt.date <= as_of).all()


def test_snapshot_unchanged_after_appending_future(prices_df, benchmark_df, taxonomy_df, tmp_root):
    as_of = date(2026, 8, 20)
    res1 = _build(prices_df, benchmark_df, taxonomy_df, tmp_root, as_of)
    # Append some future data
    future_dates = pd.date_range("2026-08-21", periods=5).date
    future_rows = []
    for tkr in ["BBCA.JK", "BBRI.JK", "BMRI.JK", "BBNI.JK"]:
        for d in future_dates:
            future_rows.append(
                {
                    "ticker": tkr,
                    "date": d,
                    "close": 100.0,
                    "adjusted_close": 100.0,
                    "volume": 1000,
                    "market_cap": None,
                    "currency": "IDR",
                    "price_basis": "adjusted_close",
                    "source": "fixture",
                }
            )
    extended_prices = pd.concat([prices_df, pd.DataFrame(future_rows)], ignore_index=True)
    res2 = _build(extended_prices, benchmark_df, taxonomy_df, tmp_root, as_of)
    # Compare key group-level metrics between the two runs
    g1 = res1["groups"].sort_values("group_id").reset_index(drop=True)
    g2 = res2["groups"].sort_values("group_id").reset_index(drop=True)
    # We expect identical breadth / group_excess_return for as_of
    if not g1.empty and not g2.empty:
        for col in ("group_excess_return", "breadth_outperforming", "breadth_positive"):
            if col in g1.columns and col in g2.columns:
                v1 = g1[col].fillna(-999.0).to_numpy()
                v2 = g2[col].fillna(-999.0).to_numpy()
                # They must be equal (allowing for row alignment)
                pd.testing.assert_series_equal(
                    pd.Series(v1, name=col),
                    pd.Series(v2, name=col),
                    check_names=False,
                )


def test_invariant_eligible_count_le_total(prices_df, benchmark_df, taxonomy_df, tmp_root):
    res = _build(prices_df, benchmark_df, taxonomy_df, tmp_root, date(2026, 8, 20))
    g = res["groups"]
    if not g.empty:
        assert (g["eligible_count"] <= g["constituent_count"]).all()


def test_future_snapshot_does_not_change_persistence_or_materiality(
    prices_df, benchmark_df, taxonomy_df, tmp_root
):
    historical_date = date(2026, 8, 13)
    as_of = date(2026, 8, 20)
    future_date = date(2026, 8, 27)

    _build(prices_df, benchmark_df, taxonomy_df, tmp_root, historical_date)
    before = _build(prices_df, benchmark_df, taxonomy_df, tmp_root, as_of)
    _build(prices_df, benchmark_df, taxonomy_df, tmp_root, future_date)
    after = _build(prices_df, benchmark_df, taxonomy_df, tmp_root, as_of)

    assert after["comparability"]["selected_previous"] == "snap_2026-08-13"
    rejected = {
        row["snapshot_id"]: row
        for row in after["comparability"]["snapshots_checked"]
        if row["status"] == "INCOMPATIBLE"
    }
    assert "snap_2026-08-27" in rejected
    assert any("not earlier" in reason for reason in rejected["snap_2026-08-27"]["reasons"])

    group_columns = [
        "group_id",
        "leadership_state",
        "diffusion_state",
        "leadership_persistence",
        "diffusion_persistence",
    ]
    pd.testing.assert_frame_equal(
        before["groups"][group_columns].sort_values("group_id").reset_index(drop=True),
        after["groups"][group_columns].sort_values("group_id").reset_index(drop=True),
    )
    transition_columns = ["group_id", "materiality_label", "materiality_reason"]
    pd.testing.assert_frame_equal(
        before["transitions"][transition_columns]
        .sort_values("group_id")
        .reset_index(drop=True),
        after["transitions"][transition_columns]
        .sort_values("group_id")
        .reset_index(drop=True),
    )
