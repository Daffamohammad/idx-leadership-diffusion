"""Group-level aggregation.

Produces a list of `GroupSnapshot` objects from a per-security feature
DataFrame, taxonomy, and a previous GroupSnapshot list (for delta
calculations).
"""
from __future__ import annotations

from datetime import date
from typing import Optional

import numpy as np
import pandas as pd

from ..features.breadth import compute_breadth
from ..features.concentration import compute_concentration
from ..features.concentration_v2 import compute_concentration_v2
from ..models import (
    ConcentrationMetrics,
    DiffusionState,
    EligibilityStatus,
    GroupSnapshot,
    LeadershipState,
)
from ..signals.diffusion import classify_diffusion
from ..signals.diffusion_v2 import classify_diffusion_v2, to_v1_state
from ..signals.leadership import classify_leadership
from ..utils import get_logger

_log = get_logger(__name__)


def _finite_mean(frame: pd.DataFrame, column: str) -> float | None:
    if column not in frame.columns:
        return None
    values = pd.to_numeric(frame[column], errors="coerce").dropna()
    return float(values.mean()) if not values.empty else None


def build_group_snapshots(
    *,
    features: pd.DataFrame,
    taxonomy: pd.DataFrame,
    snapshot_date: date,
    prices: pd.DataFrame,
    horizons: dict[str, int],
    min_constituents: int = 4,
    min_coverage_pct: float = 60.0,
    raw_candidate_taxonomy: pd.DataFrame | None = None,
    acquisition_failed_tickers: set[str] | None = None,
    previous_groups: Optional[list[GroupSnapshot]] = None,
    broadening_threshold_pp: float = 10.0,
    narrowing_threshold_pp: float = -10.0,
    acceleration_threshold_pp: float = 1.0,
    excess_return_improving: float = 0.0,
    excess_return_leading: float = 0.0,
    concentration_horizon: int = 20,
    method_version: str = "methodology-v1",
    feature_version: str = "features-v1",
    diffusion_mode: str = "legacy",
    diffusion_constituent_fraction: float = 0.10,
    diffusion_minimum_constituents: int = 2,
    concentration_mode: str = "absolute_move",
    concentration_signed_denominator_epsilon: float = 1e-8,
    concentration_signed_min_net_to_gross: float = 0.05,
    concentration_price_col: str = "adjusted_close",
    taxonomy_level: str = "sector",
) -> list[GroupSnapshot]:
    """Build group snapshots for all groups in the taxonomy.

    Returns a list of `GroupSnapshot` (Pydantic) for downstream
    serialization.

    The taxonomy frame is the **policy-eligible** universe: the set on
    which the 60% coverage gate is evaluated. The raw candidate taxonomy
    is tracked separately for disclosure. Acquisition-failed tickers
    remain in the denominator and count toward `missing_count` rather
    than being silently dropped.
    """
    if taxonomy is None or taxonomy.empty:
        return []

    # Keep the taxonomy as the left-hand side of the join.  Feature-only rows
    # are not policy-eligible constituents and must not create an artificial
    # UNCLASSIFIED group (or dilute any group's denominator).  A completely
    # empty feature frame is still a valid data-gap snapshot: the taxonomy
    # remains the denominator and every metric below resolves to None.
    feature_frame = features.copy() if features is not None else pd.DataFrame()
    if "ticker" not in feature_frame.columns:
        feature_frame = pd.DataFrame(columns=["ticker"])

    # The taxonomy frame is the policy-eligible universe: this is the
    # denominator for the 60% coverage gate. The raw candidate count is
    # tracked separately for disclosure.
    taxonomy_base = taxonomy.drop_duplicates(subset=["ticker"], keep="last")
    raw_base = (
        raw_candidate_taxonomy.drop_duplicates(subset=["ticker"], keep="last")
        if raw_candidate_taxonomy is not None and not raw_candidate_taxonomy.empty
        else taxonomy_base
    )
    acq_fail = {str(t) for t in (acquisition_failed_tickers or set())}
    # The live runner keeps taxonomy columns alongside feature columns so it
    # can reuse one canonical frame for coverage, sensitivity, and export.
    # Drop those duplicate presentation columns before the join; otherwise
    # pandas suffixes them and taxonomy_path silently loses its hierarchy.
    feature_columns = [
        column
        for column in feature_frame.columns
        if column == "ticker" or column not in taxonomy_base.columns
    ]
    feature_frame = (
        feature_frame[feature_columns]
        .drop_duplicates(subset=["ticker"], keep="last")
        .copy()
    )
    merged = taxonomy_base.merge(
        feature_frame, on="ticker", how="left"
    )
    merged["group_id"] = merged["group_id"].fillna("UNCLASSIFIED")
    # Missing feature columns are intentionally represented as NaN so a
    # missing acquisition remains visible without turning a data-gap run into
    # a KeyError in the metric calculations.
    for column in (
        "return_5d",
        "return_20d",
        "return_60d",
        "return_ytd",
        "excess_return_5d",
        "excess_return_20d",
        "excess_return_60d",
        "excess_return_ytd",
        "benchmark_return_ytd",
        "return_ytd_start_date",
    ):
        if column not in merged.columns:
            merged[column] = np.nan

    prev_by_group: dict[str, GroupSnapshot] = {}
    if previous_groups:
        for g in previous_groups:
            prev_by_group[g.group_id] = g

    out: list[GroupSnapshot] = []
    for group_id, gdf in merged.groupby("group_id"):
        # The policy-eligible universe is the denominator. We treat the
        # taxonomy frame as policy-eligible (the caller filters it). The
        # raw candidate taxonomy is used only for disclosure counts.
        total_constituents = int(gdf["ticker"].nunique())
        n_observed = int(gdf["return_20d"].notna().sum())
        n_acq_failed = int(gdf["ticker"].astype(str).isin(acq_fail).sum())
        if (
            raw_candidate_taxonomy is not None
            and not raw_candidate_taxonomy.empty
            and "group_id" in raw_candidate_taxonomy.columns
        ):
            raw_candidates = int(
                raw_candidate_taxonomy.loc[
                    raw_candidate_taxonomy["group_id"].fillna("UNCLASSIFIED")
                    == group_id,
                    "ticker",
                ].nunique()
            )
        else:
            raw_candidates = total_constituents
        eligible_flag = _is_eligible(
            n_total=total_constituents,
            n_eligible=n_observed,
            min_constituents=min_constituents,
            min_coverage_pct=min_coverage_pct,
        )

        # Equal-weight group return & excess return at primary horizon
        ret20 = gdf["return_20d"].dropna()
        ex20 = gdf["excess_return_20d"].dropna()
        group_return = float(ret20.mean()) if not ret20.empty else None
        group_excess = float(ex20.mean()) if not ex20.empty else None
        # Other horizons for evidence only
        ex5 = gdf["excess_return_5d"].dropna()
        ex60 = gdf["excess_return_60d"].dropna()
        g_ex5 = float(ex5.mean()) if not ex5.empty else None
        g_ex60 = float(ex60.mean()) if not ex60.empty else None
        ytd_features = gdf.dropna(subset=["return_ytd", "excess_return_ytd"])
        group_ytd = (
            float(pd.to_numeric(ytd_features["return_ytd"], errors="coerce").dropna().mean())
            if not ytd_features.empty
            else None
        )
        group_excess_ytd = (
            float(pd.to_numeric(ytd_features["excess_return_ytd"], errors="coerce").dropna().mean())
            if not ytd_features.empty
            else None
        )
        benchmark_ytd = _finite_mean(ytd_features, "benchmark_return_ytd")
        ytd_start_values = (
            ytd_features["return_ytd_start_date"].dropna()
            if "return_ytd_start_date" in ytd_features.columns
            else pd.Series(dtype=object)
        )
        ytd_start_date = ytd_start_values.iloc[0] if not ytd_start_values.empty else None

        # Breadth (uses features on the group slice)
        breadth = compute_breadth(
            gdf,
            total_constituents=total_constituents,
        )
        core_breadth = breadth.metric("benchmark_outperformance")

        prev_breadth = prev_by_group.get(group_id)
        if prev_breadth is not None and prev_breadth.breadth_outperforming is not None and breadth.benchmark_outperformance_share is not None:
            breadth_delta = float(breadth.benchmark_outperformance_share) - float(prev_breadth.breadth_outperforming)
            breadth_change_count = breadth.outperforming_count - prev_breadth.breadth_outperforming_count
        else:
            breadth_delta = None
            breadth_change_count = None

        # Concentration
        group_tickers = gdf["ticker"].unique().tolist()
        if concentration_mode == "absolute_move_v2":
            conc_v2 = compute_concentration_v2(
                prices,
                group_tickers=group_tickers,
                horizon=concentration_horizon,
                as_of=snapshot_date,
                signed_denominator_epsilon=concentration_signed_denominator_epsilon,
                signed_min_net_to_gross=concentration_signed_min_net_to_gross,
                price_col=concentration_price_col,
            )
            conc_metrics = ConcentrationMetrics(
                top1_contribution_share=conc_v2.top1_abs_share,
                top3_contribution_share=conc_v2.top3_abs_share,
                top5_contribution_share=conc_v2.top5_abs_share,
                top1_signed_share=conc_v2.top1_signed_share,
                top3_signed_share=conc_v2.top3_signed_share,
                hhi_contribution=conc_v2.hhi,
                contributor_count=conc_v2.contributor_count,
                convention=conc_v2.convention,
                status=conc_v2.status,
                signed_attribution_status=conc_v2.signed_attribution_status,
            )
        else:
            conc = compute_concentration(
                prices,
                group_tickers=group_tickers,
                horizon=concentration_horizon,
                as_of=snapshot_date,
            )
            conc_metrics = ConcentrationMetrics(
                top1_contribution_share=conc.top1_contribution_share,
                top3_contribution_share=conc.top3_contribution_share,
                top5_contribution_share=conc.top5_contribution_share,
                hhi_contribution=conc.hhi_contribution,
                contributor_count=conc.contributor_count,
                convention=conc.convention,
            )

        # Leadership (requires all three horizons; otherwise UNCONFIRMED
        # by construction in classify_leadership — no silent fallback).
        leadership_state = classify_leadership(
            excess_return_20d=group_excess,
            excess_return_5d=g_ex5,
            excess_return_60d=g_ex60,
            acceleration_threshold_pp=acceleration_threshold_pp,
            excess_return_improving=excess_return_improving,
            excess_return_leading=excess_return_leading,
            eligible=eligible_flag,
        )
        # Diffusion. Keep the v1 projection for existing consumers, while
        # retaining the richer v2 state when the configured mode enables it.
        diffusion_state_v2 = None
        if diffusion_mode == "group_size_aware":
            diffusion_state_v2 = classify_diffusion_v2(
                breadth_current=breadth.benchmark_outperformance_share,
                breadth_previous=(
                    prev_breadth.breadth_outperforming
                    if prev_breadth is not None
                    else None
                ),
                group_size=total_constituents,
                broadening_threshold_pp=broadening_threshold_pp,
                narrowing_threshold_pp=narrowing_threshold_pp,
                fraction=diffusion_constituent_fraction,
                minimum_constituents=diffusion_minimum_constituents,
                eligible=eligible_flag,
                breadth_change_count=breadth_change_count,
            )
            diffusion_state = DiffusionState(to_v1_state(diffusion_state_v2))
        else:
            diffusion_state = classify_diffusion(
                breadth_delta_pp=breadth_delta,
                broadening_threshold_pp=broadening_threshold_pp,
                narrowing_threshold_pp=narrowing_threshold_pp,
                eligible=eligible_flag,
            )

        # Determine a 'relative_strength_level' for transition math: use the
        # primary-horizon excess return.
        rs_level = group_excess

        taxonomy_path: list[str] = []
        for column in ("sector", "subsector", "industry", "sub_industry"):
            if column not in gdf.columns:
                continue
            values = gdf[column].dropna().astype(str)
            if values.empty:
                continue
            value = values.iloc[0]
            if value and value not in taxonomy_path:
                taxonomy_path.append(value)

        snap = GroupSnapshot(
            snapshot_date=snapshot_date,
            taxonomy_level=taxonomy_level,
            taxonomy_path=taxonomy_path,
            group_id=group_id,
            group_name=group_id,
            constituent_count=total_constituents,
            raw_candidate_count=raw_candidates,
            policy_eligible_count=total_constituents,
            acquisition_failed_count=n_acq_failed,
            eligible_count=breadth.usable_constituents,
            missing_count=breadth.missing_constituents,
            group_return_equal_weight=group_return,
            group_excess_return=group_excess,
            group_excess_return_5d=g_ex5,
            group_excess_return_20d=group_excess,
            group_excess_return_60d=g_ex60,
            group_return_ytd=group_ytd,
            group_excess_return_ytd=group_excess_ytd,
            benchmark_return_ytd=benchmark_ytd,
            ytd_start_date=ytd_start_date,
            ytd_eligible_count=int(ytd_features["ticker"].nunique()),
            breadth_positive=breadth.positive_return_share,
            breadth_outperforming=breadth.benchmark_outperformance_share,
            breadth_delta=breadth_delta,
            breadth_total_count=core_breadth.total_count,
            breadth_eligible_count=core_breadth.eligible_denominator,
            breadth_missing_count=core_breadth.missing_count,
            breadth_positive_count=breadth.positive_count,
            breadth_outperforming_count=core_breadth.numerator,
            breadth_improving_count=breadth.improving_count,
            concentration=conc_metrics,
            leadership_state=leadership_state,
            diffusion_state=diffusion_state,
            diffusion_state_v2=diffusion_state_v2,
            leadership_rank=None,
            change_rank=None,
            method_version=method_version,
            feature_version=feature_version,
        )
        # attach convenience field for transition math (not in pydantic model):
        snap.__dict__["relative_strength_level"] = rs_level
        out.append(snap)
    return out


def rank_groups(snapshots: list[GroupSnapshot]) -> list[GroupSnapshot]:
    """Assign leadership_rank and change_rank in-place; return list sorted by rank."""
    eligible = [s for s in snapshots if s.leadership_state != LeadershipState.UNCONFIRMED]
    eligible.sort(
        key=lambda s: (s.group_excess_return if s.group_excess_return is not None else float("-inf")),
        reverse=True,
    )
    by_group: dict[str, GroupSnapshot] = {s.group_id: s for s in eligible}
    for i, s in enumerate(eligible, start=1):
        s.leadership_rank = i
    # change_rank by breadth_delta
    eligible_delta = [s for s in snapshots if s.breadth_delta is not None]
    eligible_delta.sort(key=lambda s: float(s.breadth_delta), reverse=True)  # type: ignore[arg-type]
    for i, s in enumerate(eligible_delta, start=1):
        s.change_rank = i
    # Sort the whole list by leadership_rank, then by group_id
    snapshots.sort(key=lambda s: (s.leadership_rank if s.leadership_rank else 1_000_000, s.group_id))
    return snapshots


def aggregate_history(snapshots_by_date: dict[date, list[GroupSnapshot]]) -> pd.DataFrame:
    """Flatten a history of group snapshots into a long DataFrame."""
    rows: list[dict] = []
    for d, snaps in snapshots_by_date.items():
        for s in snaps:
            rows.append(
                {
                    "snapshot_date": s.snapshot_date,
                    "group_id": s.group_id,
                    "leadership_state": s.leadership_state.value,
                    "diffusion_state": s.diffusion_state.value,
                    "diffusion_state_v2": (
                        s.diffusion_state_v2.value
                        if s.diffusion_state_v2 is not None
                        else None
                    ),
                    "group_excess_return": s.group_excess_return,
                    "breadth_outperforming": s.breadth_outperforming,
                    "breadth_delta": s.breadth_delta,
                    "leadership_rank": s.leadership_rank,
                    "change_rank": s.change_rank,
                    "top1_contribution_share": s.concentration.top1_contribution_share,
                }
            )
    return pd.DataFrame(rows)


def _is_eligible(*, n_total: int, n_eligible: int, min_constituents: int, min_coverage_pct: float) -> bool:
    if n_total < min_constituents:
        return False
    coverage = (n_eligible / n_total) * 100.0 if n_total else 0.0
    return coverage >= min_coverage_pct
