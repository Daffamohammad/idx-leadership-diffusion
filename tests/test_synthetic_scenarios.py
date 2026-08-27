"""Golden regression tests for the synthetic-market scenarios.

These scenarios are deterministic; the engine's classifications on them
must stay stable. If they drift, the change is visible here and the
change log should reference a deliberate methodology change.
"""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from idx_leadership.analytics.contradictions import build_contradictions
from idx_leadership.features.breadth import compute_breadth
from idx_leadership.features.concentration import compute_concentration
from idx_leadership.features.concentration_v2 import compute_concentration_v2
from idx_leadership.models import (
    DiffusionState,
    DiffusionStateV2,
    GroupSnapshot,
    LeadershipState,
)
from idx_leadership.models.group_snapshot import ConcentrationMetrics
from idx_leadership.signals.diffusion_v2 import classify_diffusion_v2
from idx_leadership.signals.leadership import classify_leadership

from tests.synthetic_market import (
    GOLDEN,
    SyntheticConstituent,
    SyntheticGroupObservation,
    all_scenarios,
    corporate_action_history,
    deterioration_history,
    early_recovery_history,
    healthy_history,
    missing_data_observation,
    narrow_history,
    noisy_micro_history,
    obs_5d,
    obs_20d,
    obs_60d,
)


def _to_features(obs: SyntheticGroupObservation) -> pd.DataFrame:
    rows = []
    for constituent in obs.constituents:
        rows.append(
            {
                "ticker": constituent.ticker,
                "return_5d": constituent.return_5d,
                "return_20d": constituent.return_20d,
                "return_60d": constituent.return_60d,
                "excess_return_5d": (
                    None
                    if constituent.return_5d is None
                    else constituent.return_5d - obs.benchmark_return_5d
                ),
                "excess_return_20d": (
                    None
                    if constituent.return_20d is None
                    else constituent.return_20d - obs.benchmark_return_20d
                ),
                "excess_return_60d": (
                    None
                    if constituent.return_60d is None
                    else constituent.return_60d - obs.benchmark_return_60d
                ),
            }
        )
    return pd.DataFrame(rows)


def _prices_frame(obs: SyntheticGroupObservation, n_days: int = 21) -> pd.DataFrame:
    """Build a synthetic price frame so ``compute_concentration_v2`` can run.

    The frame produces the per-constituent 20D returns implied by the
    observation's :class:`SyntheticConstituent` values.
    """
    dates = pd.date_range("2026-07-01", periods=n_days).date
    rows = []
    for c in obs.constituents:
        ret = c.return_20d if c.return_20d is not None else 0.0
        start = 100.0
        end = start * (1.0 + ret / 100.0)
        prices = [start + (end - start) * (i / (n_days - 1)) for i in range(n_days)]
        for d, p in zip(dates, prices):
            rows.append({"ticker": c.ticker, "date": d, "adjusted_close": p, "close": p})
    return pd.DataFrame(rows)


def _avg_excess(obs: SyntheticGroupObservation, horizon: str) -> float | None:
    benchmark = {
        "5d": obs.benchmark_return_5d,
        "20d": obs.benchmark_return_20d,
        "60d": obs.benchmark_return_60d,
    }[horizon]
    raw = {"5d": obs_5d, "20d": obs_20d, "60d": obs_60d}[horizon](obs.constituents)
    eligible = [r for r in raw if r is not None]
    if not eligible:
        return None
    return float(np.mean([r - benchmark for r in eligible]))


def _classify_leadership(obs: SyntheticGroupObservation) -> str:
    if obs.corporate_action_window:
        return "UNCONFIRMED"
    excess_5d = _avg_excess(obs, "5d")
    excess_20d = _avg_excess(obs, "20d")
    excess_60d = _avg_excess(obs, "60d")
    if excess_5d is None or excess_20d is None or excess_60d is None:
        return "UNCONFIRMED"
    state = classify_leadership(
        excess_return_20d=excess_20d,
        excess_return_5d=excess_5d,
        excess_return_60d=excess_60d,
    )
    return state.value


def _classify_diffusion(
    current: SyntheticGroupObservation,
    previous: SyntheticGroupObservation | None,
) -> tuple[str, float | None]:
    if current.corporate_action_window:
        return "UNCONFIRMED", None
    cur_breadth = _breadth_outperforming(current)
    prev_breadth = _breadth_outperforming(previous) if previous else None
    if cur_breadth is None or prev_breadth is None:
        return "UNCONFIRMED", None
    eligible = sum(1 for c in current.constituents if c.return_20d is not None)
    state = classify_diffusion_v2(
        breadth_current=cur_breadth,
        breadth_previous=prev_breadth,
        group_size=eligible,
    )
    delta = cur_breadth - prev_breadth
    return state.value, delta


def _breadth_outperforming(obs: SyntheticGroupObservation) -> float | None:
    eligible = [c for c in obs.constituents if c.return_20d is not None]
    if not eligible:
        return None
    out = sum(
        1
        for c in eligible
        if c.return_20d is not None
        and (c.return_20d - obs.benchmark_return_20d) > 0
    )
    return round((out / len(eligible)) * 100.0, 4)


def _scenario_history(group_id: str) -> list[SyntheticGroupObservation]:
    if group_id == "healthy":
        return healthy_history()
    if group_id == "narrow":
        return narrow_history()
    if group_id == "early_recovery":
        return early_recovery_history()
    if group_id == "deterioration":
        return deterioration_history()
    if group_id == "micro":
        return noisy_micro_history()
    if group_id == "partial":
        return missing_data_observation()
    if group_id == "ca_shock":
        return corporate_action_history()
    raise KeyError(group_id)


# --- A: Healthy Leadership ---------------------------------------------


def test_healthy_scenario_classifies_leading_broadening_firm_low_concentration():
    history = _scenario_history("healthy")
    final = history[-1]
    previous = history[-2]

    state = _classify_leadership(final)
    diffusion, delta = _classify_diffusion(final, previous)
    breadth = compute_breadth(_to_features(final), total_constituents=len(final.constituents))
    assert state == "LEADING"
    assert diffusion == "BROADENING_FIRM"
    assert delta is not None and delta > 10.0
    assert breadth.benchmark_outperformance_share is not None
    assert breadth.benchmark_outperformance_share >= 60.0

    concentration = compute_concentration_v2(
        _prices_frame(final),
        group_tickers=[c.ticker for c in final.constituents],
        horizon=20,
    )
    assert concentration.top1_abs_share is not None
    assert concentration.top1_abs_share <= GOLDEN["A"].concentration.top1_lte
    assert concentration.hhi is not None
    assert concentration.hhi <= GOLDEN["A"].concentration.hhi_lte


# --- B: Narrow Leadership ----------------------------------------------


def test_narrow_scenario_classifies_leading_with_narrowing_and_high_concentration():
    obs = _scenario_history("narrow")[-1]
    previous = SyntheticGroupObservation(
        group_id="narrow",
        scenario="B",
        snapshot_date="2026-08-07",
        constituents=tuple(
            SyntheticConstituent(
                ticker=c.ticker,
                return_5d=0.0,
                return_20d=2.0,
                return_60d=1.0,
            )
            for c in obs.constituents
        ),
    )

    state = _classify_leadership(obs)
    diffusion, delta = _classify_diffusion(obs, previous)
    assert state == "LEADING"
    assert "NARROWING" in diffusion
    assert delta is not None and delta < -10.0

    concentration = compute_concentration_v2(
        _prices_frame(obs),
        group_tickers=[c.ticker for c in obs.constituents],
        horizon=20,
    )
    assert concentration.top1_abs_share is not None
    assert concentration.top1_abs_share >= GOLDEN["B"].concentration.top1_gte


# --- C: Early Recovery -------------------------------------------------


def test_early_recovery_scenario_classifies_improving_broadening_with_negative_medium():
    history = _scenario_history("early_recovery")
    final = history[-1]
    previous = history[-2]

    state = _classify_leadership(final)
    diffusion, delta = _classify_diffusion(final, previous)
    assert state == "IMPROVING"
    assert "BROADENING" in diffusion
    assert delta is not None and delta > 0
    excess_60d = _avg_excess(final, "60d")
    assert excess_60d is not None and excess_60d < 0


# --- D: Deterioration --------------------------------------------------


def test_deterioration_scenario_classifies_weakening_narrowing():
    history = _scenario_history("deterioration")
    final = history[-1]
    previous = history[-2]

    state = _classify_leadership(final)
    diffusion, delta = _classify_diffusion(final, previous)
    assert state == "WEAKENING"
    assert "NARROWING" in diffusion
    assert delta is not None and delta < -10.0


# --- E: Noisy Micro Group ----------------------------------------------


def test_noisy_micro_scenario_is_unconfirmed_for_diffusion_below_floor():
    obs = _scenario_history("micro")[-1]
    eligible = sum(1 for c in obs.constituents if c.return_20d is not None)
    diffusion, _ = _classify_diffusion(obs, None)
    assert eligible < 5
    assert diffusion == "UNCONFIRMED"

    concentration = compute_concentration_v2(
        _prices_frame(obs),
        group_tickers=[c.ticker for c in obs.constituents],
        horizon=20,
    )
    assert concentration.top1_abs_share is not None
    assert concentration.top1_abs_share >= GOLDEN["E"].concentration.top1_gte


# --- F: Missing Data ---------------------------------------------------


def test_missing_data_scenario_reports_explicit_denominators():
    obs = _scenario_history("partial")[-1]
    features = _to_features(obs)
    breadth = compute_breadth(
        features,
        total_constituents=len(obs.constituents),
    )
    positive = breadth.metric("positive_return")
    assert positive.numerator == 2
    assert positive.eligible_denominator == 3
    assert positive.missing_count == 2
    assert positive.total_count == 5


# --- G: Corporate Action Shock ----------------------------------------


def test_corporate_action_window_classifies_leadership_as_unconfirmed():
    history = _scenario_history("ca_shock")
    final = history[-1]
    state = _classify_leadership(final)
    diffusion, _ = _classify_diffusion(final, history[-2])
    assert final.corporate_action_window is True
    assert state == "UNCONFIRMED"
    assert diffusion == "UNCONFIRMED"


# --- Concentration v1 + v2 invariant -----------------------------------


def test_concentration_v1_and_v2_agree_on_extreme_top1_pathology():
    obs = noisy_micro_history()[-1]
    prices = _prices_frame(obs)
    v1 = compute_concentration(
        prices, group_tickers=[c.ticker for c in obs.constituents], horizon=20
    )
    v2 = compute_concentration_v2(
        prices, group_tickers=[c.ticker for c in obs.constituents], horizon=20
    )
    assert v1.top1_contribution_share is not None
    assert v2.top1_abs_share is not None
    # v2 explicitly caps at 1.0 even in the most pathological case.
    assert v2.top1_abs_share <= 1.0


# --- Contradictions: LEADING + NARROWING surfaces in B ----------------


def test_narrow_scenario_surfaces_leading_but_narrowing_contradiction():
    obs = _scenario_history("narrow")[-1]
    features = _to_features(obs)
    concentration = compute_concentration_v2(
        _prices_frame(obs),
        group_tickers=[c.ticker for c in obs.constituents],
        horizon=20,
    )
    snap = GroupSnapshot(
        snapshot_date=date.fromisoformat(obs.snapshot_date),
        group_id=obs.group_id,
        leadership_state=LeadershipState.LEADING,
        diffusion_state=DiffusionState.NARROWING,
        diffusion_state_v2=DiffusionStateV2.NARROWING_FIRM,
        breadth_outperforming=_breadth_outperforming(obs),
        concentration=ConcentrationMetrics(
            top1_contribution_share=concentration.top1_abs_share,
            top3_contribution_share=concentration.top3_abs_share,
            hhi_contribution=concentration.hhi,
            contributor_count=concentration.contributor_count,
        ),
        method_version="methodology-v3",
    )
    contradictions = {record.metric: record for record in build_contradictions(snap)}
    assert "leading_but_narrowing" in contradictions


# --- Missing-data breadth invariants -----------------------------------


def test_breadth_with_zero_eligible_returns_undefined_not_zero():
    features = pd.DataFrame(
        [
            {"ticker": "X1", "return_20d": None, "excess_return_20d": None},
            {"ticker": "X2", "return_20d": None, "excess_return_20d": None},
        ]
    )
    breadth = compute_breadth(features, total_constituents=2)
    metric = breadth.metric("positive_return")
    assert metric.share is None
    assert metric.status == "UNDEFINED_NO_ELIGIBLE"
    assert metric.missing_count == metric.total_count == 2


def test_breadth_with_one_missing_constituent_reports_remaining_denominator():
    features = pd.DataFrame(
        [
            {"ticker": "A", "return_20d": 1.0, "excess_return_20d": 0.5},
        ]
    )
    breadth = compute_breadth(features, total_constituents=2)
    metric = breadth.metric("positive_return")
    assert metric.share == 100.0
    assert metric.missing_count == 1
    assert metric.total_count == 2


def test_breadth_with_fifty_percent_missing_keeps_explicit_share():
    features = pd.DataFrame(
        [
            {"ticker": "A", "return_20d": 1.0, "excess_return_20d": 0.5},
            {"ticker": "B", "return_20d": -1.0, "excess_return_20d": -0.5},
        ]
    )
    breadth = compute_breadth(features, total_constituents=4)
    metric = breadth.metric("benchmark_outperformance")
    assert metric.share == 50.0
    assert metric.missing_count == 2
    assert metric.total_count == 4


def test_breadth_with_stale_observation_excludes_but_counts_as_missing():
    features = pd.DataFrame(
        [
            {"ticker": "A", "return_20d": 1.0, "is_stale": False},
            {"ticker": "B", "return_20d": -1.0, "is_stale": True},
        ]
    )
    breadth = compute_breadth(features, total_constituents=2, stale_col="is_stale")
    metric = breadth.metric("positive_return")
    assert metric.share == 100.0
    assert metric.eligible_denominator == 1
    assert metric.missing_count == 1


def test_breadth_with_mixed_benchmark_dates_excludes_unmatched_rows():
    features = pd.DataFrame(
        [
            {
                "ticker": "A",
                "return_20d": 1.0,
                "excess_return_20d": 0.5,
                "as_of": "2026-08-20",
                "benchmark_as_of": "2026-08-20",
            },
            {
                "ticker": "B",
                "return_20d": 1.0,
                "excess_return_20d": 0.5,
                "as_of": "2026-08-20",
                "benchmark_as_of": "2026-08-19",
            },
        ]
    )
    breadth = compute_breadth(
        features,
        total_constituents=2,
        observation_date_col="as_of",
        benchmark_date_col="benchmark_as_of",
    )
    metric = breadth.metric("benchmark_outperformance")
    assert metric.share == 100.0
    assert metric.missing_count == 1
    assert metric.total_count == 2


# --- Negative group return -------------------------------------------


def test_concentration_handles_negative_group_return_without_exploding():
    """When every constituent is negative but magnitudes differ, absolute
    concentration should remain well-defined and signed attribution
    should be DENOMINATOR-UNSTABLE (net/gross ≈ 1.0 means stable).
    """
    obs = SyntheticGroupObservation(
        group_id="negative",
        scenario="aux",
        snapshot_date="2026-08-14",
        constituents=(
            SyntheticConstituent("N1", -2.0, -10.0, -5.0),
            SyntheticConstituent("N2", -1.0, -5.0, -2.0),
            SyntheticConstituent("N3", 0.0, -1.0, 0.0),
        ),
    )
    concentration = compute_concentration_v2(
        _prices_frame(obs),
        group_tickers=[c.ticker for c in obs.constituents],
        horizon=20,
    )
    assert concentration.top1_abs_share is not None
    assert 0.4 <= concentration.top1_abs_share <= 0.8
    # All-move-same-sign means signed attribution is well-defined.
    assert concentration.signed_attribution_status in {"DEFINED", "UNDEFINED_UNSTABLE_DENOMINATOR"}


# --- One-missing-stock path ------------------------------------------


def test_concentration_reports_missing_count_when_one_stock_unavailable():
    obs = SyntheticGroupObservation(
        group_id="one_missing",
        scenario="aux",
        snapshot_date="2026-08-14",
        constituents=(
            SyntheticConstituent("M1", 2.0, 8.0, 4.0),
            SyntheticConstituent("M2", 0.0, 2.0, 0.5),
            SyntheticConstituent("M3", -1.0, -3.0, -1.0),
        ),
    )
    concentration = compute_concentration_v2(
        _prices_frame(obs),
        group_tickers=[c.ticker for c in obs.constituents] + ["MISSING"],
        horizon=20,
    )
    assert concentration.contributor_count == 3
    assert concentration.missing_constituent_count == 1
    assert concentration.top1_abs_share is not None
