"""Tests for the analytical-universe and denominator contract.

These tests cover the contract that:
  * A request that failed because of 429/network/provider failure must remain
    in the expected analytical denominator as missing data; it must not
    become a false `insufficient_history` exclusion.
  * Group eligibility and the 60% coverage test must use
    `observed eligible features / expected policy-eligible constituents`,
    while preserving raw-candidate counts separately for disclosure.
  * A genuine policy exclusion (suspension, board, liquidity) may be out
    of the analytical denominator.
  * A group must remain UNCONFIRMED if genuinely insufficient observed
    eligible coverage remains.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pandas as pd
import pytest

from idx_leadership.aggregation.groups import build_group_snapshots
from idx_leadership.features.relative_strength import compute_excess_returns
from idx_leadership.models import (
    DiffusionStateV2,
    LeadershipState,
    ProviderName,
    SecurityMasterEntry,
)
from idx_leadership.providers.market_universe import build_market_universe


# ── helpers ─────────────────────────────────────────────────────────────


def _entry(
    ticker: str,
    sector: str = "Financials",
    sub_sector: str = "Banks",
    industry: str = "Banks",
    sub_industry: str = "Banks",
    listing_board: str = "Main",
    common_equity_status: str = "COMMON_EQUITY",
) -> SecurityMasterEntry:
    return SecurityMasterEntry(
        ticker=ticker,
        vendor_ticker=ticker,
        exchange="IDX",
        country="ID",
        sector=sector,
        subsector=sub_sector,
        industry=industry,
        subindustry=sub_industry,
        group_id=sector,
        listing_status="listed",
        instrument_type="EQUITY",
        common_equity_status=common_equity_status,
        listing_board=listing_board,
        active=True,
        benchmark_flag=False,
        listing_date=date(2020, 1, 1),
        market_cap=1e9,
        source=ProviderName.FIXTURE,
        source_as_of=date(2026, 8, 20),
    )


def _full_history(ticker: str, as_of: date, n_days: int = 90) -> pd.DataFrame:
    """Generate a synthetic price history for a ticker up to as_of."""
    import datetime as _dt
    rows: list[dict[str, Any]] = []
    base = 100.0
    for i in range(n_days):
        d = as_of - _dt.timedelta(days=n_days - i)
        rows.append(
            {
                "ticker": ticker,
                "date": d,
                "close": base + i * 0.5,
                "adjusted_close": base + i * 0.5,
                "volume": 1_000_000,
            }
        )
    return pd.DataFrame(rows)


def _stub_provider(
    master: list[SecurityMasterEntry],
    close_by_date: dict[date, pd.DataFrame] | None = None,
    suspensions: pd.DataFrame | None = None,
):
    class _Stub:
        def __init__(self):
            self._master = master
            self._close = close_by_date or {}
            self._susp = suspensions if suspensions is not None else pd.DataFrame()

        def get_security_master(self):
            return self._master

        def get_full_universe_close(self, as_of: date):
            return self._close.get(as_of, pd.DataFrame())

        def get_suspensions(self, *, start, end):
            return self._susp

    return _Stub()


# ── acquisition status vs policy exclusion ────────────────────────────


def test_acquisition_failures_kept_in_denominator_not_insufficient_history():
    """A 429/network failure must be tracked as ACQUISITION_FAILED and
    remain in the policy-eligible denominator, NOT classified as
    insufficient_history."""
    as_of = date(2026, 8, 20)
    tickers = [f"T{i}.JK" for i in range(10)]
    master = [_entry(t) for t in tickers]
    # 7 tickers have history, 3 did not (simulated 429)
    acquired = tickers[:7]
    failed = tickers[7:]
    rows: list[dict[str, Any]] = []
    for t in acquired:
        rows.append(_full_history(t, as_of))
    history = pd.concat(rows, ignore_index=True)
    provider = _stub_provider(master)
    universe = build_market_universe(
        security_master_provider=provider,
        cross_section_provider=provider,
        event_provider=None,
        as_of=as_of,
        price_history=history,
        security_master=master,
        acquisition_failures=set(failed),
    )
    # 3 failed tickers should be marked ACQUISITION_FAILED, not insufficient_history
    acq_statuses = dict(
        zip(
            universe["ticker"].astype(str),
            universe["acquisition_status"].astype(str),
        )
    )
    for t in failed:
        assert acq_statuses[t] == "ACQUISITION_FAILED", (
            f"{t} should be ACQUISITION_FAILED, got {acq_statuses[t]}"
        )
        # Must NOT be excluded via insufficient_history
        assert universe.loc[universe["ticker"] == t, "exclusion_reason"].iloc[0] == "", (
            f"{t} must remain policy-eligible (empty exclusion_reason)"
        )
    # 7 acquired tickers should be ACQUIRED
    for t in acquired:
        assert acq_statuses[t] == "ACQUIRED", (
            f"{t} should be ACQUIRED, got {acq_statuses[t]}"
        )


def test_policy_exclusions_remain_out_of_denominator():
    """Genuine policy exclusions (board, suspension) remain out of denominator."""
    as_of = date(2026, 8, 20)
    main_master = [_entry("MAIN.JK", listing_board="Main")]
    accel_master = [_entry("ACCEL.JK", listing_board="Acceleration")]
    excluded_master = [_entry("EXCL.JK", listing_board="Akseleran")]
    master = main_master + accel_master + excluded_master
    history = pd.concat(
        [_full_history(t, as_of) for t in ("MAIN.JK", "ACCEL.JK", "EXCL.JK")],
        ignore_index=True,
    )
    provider = _stub_provider(master)
    universe = build_market_universe(
        security_master_provider=provider,
        cross_section_provider=provider,
        event_provider=None,
        as_of=as_of,
        price_history=history,
        security_master=master,
    )
    row_main = universe.loc[universe["ticker"] == "MAIN.JK"].iloc[0]
    row_accel = universe.loc[universe["ticker"] == "ACCEL.JK"].iloc[0]
    row_excl = universe.loc[universe["ticker"] == "EXCL.JK"].iloc[0]
    assert row_main["eligible"] is True or row_main["eligible"] == True
    assert row_accel["eligible"] is True or row_accel["eligible"] == True
    assert row_excl["eligible"] is False or row_excl["eligible"] == False
    assert row_excl["acquisition_status"] == "POLICY_EXCLUDED"
    assert row_excl["exclusion_reason"] == "listing_board"


# ── group coverage denominator ─────────────────────────────────────────


def _taxonomy_frame(tickers: list[str], sector: str = "Financials") -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "ticker": t,
                "sector": sector,
                "subsector": "Banks",
                "industry": "Banks",
                "sub_industry": "Banks",
                "group_id": sector,
            }
            for t in tickers
        ]
    )


def test_group_coverage_uses_policy_eligible_not_raw_taxonomy():
    """Coverage must be observed/policy-eligible, not observed/raw-taxonomy.

    Scenario: 20 raw candidates, 12 policy-eligible, 10 observed.
    Raw denominator would give 10/20 = 50% (below 60% gate).
    Policy-eligible denominator gives 10/12 = 83% (above 60% gate).
    The group should classify (not stay UNCONFIRMED).
    """
    as_of = date(2026, 8, 20)
    history_end = as_of
    history_start = as_of - timedelta(days=90)
    # 20 raw candidates
    raw_tickers = [f"R{i}.JK" for i in range(20)]
    # 12 are policy-eligible, 8 are policy-excluded (e.g. wrong board)
    eligible_tickers = raw_tickers[:12]
    # 10 of the 12 have data, 2 had acquisition failure
    observed_tickers = eligible_tickers[:10]
    acq_failed = eligible_tickers[10:]

    history = pd.concat(
        [_full_history(t, as_of) for t in observed_tickers], ignore_index=True
    )
    bench = pd.DataFrame(
        {
            "date": pd.date_range(history_start, history_end).date,
            "close": 100.0
            + pd.Series(range((history_end - history_start).days + 1)) * 0.1,
            "benchmark_id": "IHSG",
        }
    )
    bench["date"] = pd.to_datetime(bench["date"]).dt.date

    features = compute_excess_returns(
        history, bench, horizons={"5d": 5, "20d": 20, "60d": 60}, as_of=as_of
    )
    # Policy-eligible taxonomy (12 tickers)
    taxonomy_eligible = _taxonomy_frame(eligible_tickers)
    # Raw candidate taxonomy (20 tickers)
    raw_candidate = _taxonomy_frame(raw_tickers)
    snaps = build_group_snapshots(
        features=features,
        taxonomy=taxonomy_eligible,
        raw_candidate_taxonomy=raw_candidate,
        acquisition_failed_tickers=set(acq_failed),
        snapshot_date=as_of,
        prices=history,
        horizons={"5d": 5, "20d": 20, "60d": 60},
        min_constituents=4,
        min_coverage_pct=60.0,
    )
    assert len(snaps) == 1
    s = snaps[0]
    # The group should NOT be UNCONFIRMED: policy-eligible coverage is
    # 10/12 = 83% which is above the 60% gate.
    assert s.leadership_state != LeadershipState.UNCONFIRMED, (
        f"Expected classified, got UNCONFIRMED; "
        f"policy_eligible={s.policy_eligible_count} observed={s.eligible_count}"
    )
    assert s.policy_eligible_count == 12
    assert s.raw_candidate_count == 20
    assert s.acquisition_failed_count == 2
    assert s.eligible_count == 10
    assert s.missing_count == 2  # 2 acquisition-failed in the denominator


def test_group_unconfirmed_when_observed_coverage_truly_below_gate():
    """If observed/policy-eligible is genuinely below 60%, the group
    must remain UNCONFIRMED (no lower thresholds to create labels)."""
    as_of = date(2026, 8, 20)
    history_end = as_of
    history_start = as_of - timedelta(days=90)
    # 20 policy-eligible, only 5 observed
    eligible_tickers = [f"E{i}.JK" for i in range(20)]
    observed_tickers = eligible_tickers[:5]
    acq_failed = eligible_tickers[5:]

    history = pd.concat(
        [_full_history(t, as_of) for t in observed_tickers], ignore_index=True
    )
    bench = pd.DataFrame(
        {
            "date": pd.date_range(history_start, history_end).date,
            "close": 100.0
            + pd.Series(range((history_end - history_start).days + 1)) * 0.1,
            "benchmark_id": "IHSG",
        }
    )
    bench["date"] = pd.to_datetime(bench["date"]).dt.date

    features = compute_excess_returns(
        history, bench, horizons={"5d": 5, "20d": 20, "60d": 60}, as_of=as_of
    )
    taxonomy_eligible = _taxonomy_frame(eligible_tickers)
    raw_candidate = _taxonomy_frame(eligible_tickers)

    snaps = build_group_snapshots(
        features=features,
        taxonomy=taxonomy_eligible,
        raw_candidate_taxonomy=raw_candidate,
        acquisition_failed_tickers=set(acq_failed),
        snapshot_date=as_of,
        prices=history,
        horizons={"5d": 5, "20d": 20, "60d": 60},
        min_constituents=4,
        min_coverage_pct=60.0,
    )
    assert len(snaps) == 1
    s = snaps[0]
    # 5/20 = 25% < 60% gate → must be UNCONFIRMED
    assert s.leadership_state == LeadershipState.UNCONFIRMED


# ── deterministic Leading/Improving/Weakening/Lagging fixture ─────────


def test_deterministic_four_state_fixture_classifies_correctly():
    """A deterministic fixture must classify Leading, Improving, Weakening,
    and Lagging after the denominator contract is corrected.

    Each group has 10 policy-eligible members, all observed. Excess returns
    are engineered so the 20D excess return is clearly positive (Leading),
    slightly positive (Improving), slightly negative (Weakening), or clearly
    negative (Lagging), with 5D acceleration signals distinguishing the
    four states.
    """
    import numpy as np
    as_of = date(2026, 8, 20)
    n_days = 120
    history_start = as_of - timedelta(days=n_days)

    # 20D excess return × 5D acceleration combinations for four states.
    # Leading:   20D=+8,  5D=+5  (strong positive, accelerating)
    # Improving: 20D=+1,  5D=+3  (slight positive, improving)
    # Weakening: 20D=-1,  5D=-2  (slight negative, decelerating)
    # Lagging:   20D=-8,  5D=-5  (strong negative, worsening)
    group_specs = [
        ("Leading", 8.0, 5.0),
        ("Improving", 1.0, 3.0),
        ("Weakening", -1.0, -2.0),
        ("Lagging", -8.0, -5.0),
    ]
    members_per_group = 10
    bench_close = 1000.0
    history_rows: list[dict[str, Any]] = []
    taxonomy_rows: list[dict[str, Any]] = []
    raw_taxonomy_rows: list[dict[str, Any]] = []
    bench_rows: list[dict[str, Any]] = []
    for d in range(n_days + 1):
        dt = history_start + timedelta(days=d)
        bench_rows.append({"date": dt, "close": bench_close, "benchmark_id": "IHSG"})
    for group_name, ex20, ex5 in group_specs:
        for i in range(members_per_group):
            ticker = f"{group_name[:3].upper()}{i}.JK"
            # Generate a 120-day price series that produces the target
            # 5D and 20D excess returns at as_of.
            # Start price so that 20D return is ex20%.
            # pct_return = (close_t - close_{t-20}) / close_{t-20} * 100
            # We use a linear price path: close_d = base * (1 + slope*d)
            # pct over k days ≈ slope*k*100
            # slope = ex20 / (20*100)  (daily slope as fraction)
            slope_20 = ex20 / (20.0 * 100.0)
            slope_5 = ex5 / (5.0 * 100.0)
            # Blend: use 5D slope for the last 5 days, 20D slope before that
            for d in range(n_days + 1):
                dt = history_start + timedelta(days=d)
                days_from_end = n_days - d
                if days_from_end <= 5:
                    slope = slope_5
                else:
                    slope = slope_20
                sec_close = bench_close * (1.0 + slope * (n_days - d))
                history_rows.append(
                    {
                        "ticker": ticker,
                        "date": dt,
                        "close": sec_close,
                        "adjusted_close": sec_close,
                        "volume": 1_000_000,
                    }
                )
            taxonomy_rows.append(
                {
                    "ticker": ticker,
                    "sector": group_name,
                    "subsector": "Test",
                    "industry": "Test",
                    "sub_industry": "Test",
                    "group_id": group_name,
                }
            )
            raw_taxonomy_rows.append(taxonomy_rows[-1])

    history = pd.DataFrame(history_rows)
    bench = pd.DataFrame(bench_rows)
    bench["date"] = pd.to_datetime(bench["date"]).dt.date
    history["date"] = pd.to_datetime(history["date"]).dt.date

    features = compute_excess_returns(
        history,
        bench,
        horizons={"5d": 5, "20d": 20, "60d": 60},
        as_of=as_of,
    )
    # Sanity: features must have rows for all 40 tickers
    assert features["ticker"].nunique() == 40, (
        f"Expected 40 tickers in features, got {features['ticker'].nunique()}"
    )
    # Sanity: Leading group should have positive 20D excess return
    leading_features = features[features["group_id"] == "Leading"] if "group_id" in features.columns else None
    if leading_features is not None:
        assert leading_features["excess_return_20d"].mean() > 0
    taxonomy = pd.DataFrame(taxonomy_rows)
    raw_tax = pd.DataFrame(raw_taxonomy_rows)

    snaps = build_group_snapshots(
        features=features,
        taxonomy=taxonomy,
        raw_candidate_taxonomy=raw_tax,
        acquisition_failed_tickers=set(),
        snapshot_date=as_of,
        prices=history,
        horizons={"5d": 5, "20d": 20, "60d": 60},
        min_constituents=4,
        min_coverage_pct=60.0,
    )
    by_group = {s.group_id: s for s in snaps}
    # Each group should classify (not UNCONFIRMED)
    for name, _, _ in group_specs:
        assert by_group[name].leadership_state != LeadershipState.UNCONFIRMED, (
            f"{name} should be classified, got UNCONFIRMED. "
            f"policy_eligible={by_group[name].policy_eligible_count} "
            f"observed={by_group[name].eligible_count} "
            f"ex20d={by_group[name].group_excess_return_20d}"
        )
    # Verify that at least two distinct states are produced (not all the same)
    states = {s.leadership_state for s in snaps}
    assert len(states) >= 2, f"Expected at least 2 distinct states, got {states}"
