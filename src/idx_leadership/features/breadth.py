"""Breadth primitives with explicit, metric-specific denominators.

Breadth is a family of participation ratios, not one interchangeable number.
Every metric therefore carries its own numerator, eligible denominator,
missing count, and total constituent count. The legacy scalar attributes are
retained for existing pipeline consumers.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Callable, Optional

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class BreadthMetric:
    """One breadth ratio and its complete denominator contract.

    Shares use the repository's existing 0--100 percentage scale. ``None``
    means that no eligible observation exists; it is never coerced to zero.
    """

    share: Optional[float]
    numerator: int
    eligible_denominator: int
    missing_count: int
    total_count: int
    status: str


@dataclass
class BreadthResult:
    positive_return_share: Optional[float] = None
    benchmark_outperformance_share: Optional[float] = None
    improvement_share: Optional[float] = None
    short_horizon_positive_share: Optional[float] = None
    medium_horizon_positive_share: Optional[float] = None
    usable_constituents: int = 0
    total_constituents: int = 0
    missing_constituents: int = 0
    positive_count: int = 0
    outperforming_count: int = 0
    improving_count: int = 0
    metrics: dict[str, BreadthMetric] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    def metric(self, name: str) -> BreadthMetric:
        """Return a named metric, raising a clear error for unknown names."""

        try:
            return self.metrics[name]
        except KeyError as exc:  # pragma: no cover - defensive API guard
            raise KeyError(f"unknown breadth metric: {name}") from exc


def compute_breadth(
    features: pd.DataFrame,
    *,
    total_constituents: int,
    horizon_short: str = "5d",
    horizon_primary: str = "20d",
    horizon_medium: str = "60d",
    excess_col: str | None = None,
    positive_col: str = "return_20d",
    excess_horizon_for_outperf: str = "20d",
    improvement_excess_col: str = "excess_return_5d",
    improvement_baseline_excess_col: str = "excess_return_60d",
    eligibility_col: str | None = None,
    stale_col: str | None = None,
    observation_date_col: str | None = None,
    benchmark_date_col: str | None = None,
) -> BreadthResult:
    """Compute participation measures for one taxonomy group.

    Parameters beyond the legacy API are optional and deterministic:

    * ``eligibility_col`` excludes rows whose value is not truthy;
    * ``stale_col`` excludes rows explicitly marked stale;
    * when both date columns are supplied, security and benchmark dates must
      match. Misalignment is treated as missing evidence, not as a negative
      observation.

    Constituents absent from ``features`` are included in each metric's
    ``missing_count`` through ``total_constituents``.
    """

    total = int(total_constituents)
    if total < 0:
        raise ValueError("total_constituents must be non-negative")

    frame = pd.DataFrame() if features is None else features.copy()
    observed = _observed_constituent_count(frame)
    if observed > total:
        raise ValueError(
            "total_constituents cannot be smaller than the number of "
            f"observed constituents ({total} < {observed})"
        )

    base_eligible = pd.Series(True, index=frame.index, dtype=bool)
    if eligibility_col is not None:
        base_eligible &= _truthy_column(frame, eligibility_col)
    if stale_col is not None:
        base_eligible &= ~_truthy_column(frame, stale_col)
    if observation_date_col is not None or benchmark_date_col is not None:
        if observation_date_col is None or benchmark_date_col is None:
            raise ValueError(
                "observation_date_col and benchmark_date_col must be supplied together"
            )
        observation_dates = _date_column(frame, observation_date_col)
        benchmark_dates = _date_column(frame, benchmark_date_col)
        base_eligible &= (
            observation_dates.notna()
            & benchmark_dates.notna()
            & observation_dates.eq(benchmark_dates)
        )

    primary_positive = _metric_from_column(
        frame,
        column=positive_col,
        total_count=total,
        base_eligible=base_eligible,
        predicate=lambda values: values > 0,
    )
    outperformance = _metric_from_column(
        frame,
        column=excess_col or f"excess_return_{excess_horizon_for_outperf}",
        total_count=total,
        base_eligible=base_eligible,
        predicate=lambda values: values > 0,
    )
    improvement = _metric_from_pair(
        frame,
        left_column=improvement_excess_col,
        right_column=improvement_baseline_excess_col,
        total_count=total,
        base_eligible=base_eligible,
        predicate=lambda left, right: left > right,
    )
    short_positive = _metric_from_column(
        frame,
        column=f"return_{horizon_short}",
        total_count=total,
        base_eligible=base_eligible,
        predicate=lambda values: values > 0,
    )
    # ``horizon_primary`` remains an explicit part of the contract even when
    # callers override ``positive_col`` with a non-standard column.
    primary_horizon_positive = _metric_from_column(
        frame,
        column=f"return_{horizon_primary}",
        total_count=total,
        base_eligible=base_eligible,
        predicate=lambda values: values > 0,
    )
    medium_positive = _metric_from_column(
        frame,
        column=f"return_{horizon_medium}",
        total_count=total,
        base_eligible=base_eligible,
        predicate=lambda values: values > 0,
    )

    metrics = {
        "positive_return": primary_positive,
        "benchmark_outperformance": outperformance,
        "improvement": improvement,
        "short_horizon_positive_return": short_positive,
        "primary_horizon_positive_return": primary_horizon_positive,
        "medium_horizon_positive_return": medium_positive,
    }
    return BreadthResult(
        positive_return_share=primary_positive.share,
        benchmark_outperformance_share=outperformance.share,
        improvement_share=improvement.share,
        short_horizon_positive_share=short_positive.share,
        medium_horizon_positive_share=medium_positive.share,
        usable_constituents=primary_positive.eligible_denominator,
        total_constituents=total,
        missing_constituents=primary_positive.missing_count,
        positive_count=primary_positive.numerator,
        outperforming_count=outperformance.numerator,
        improving_count=improvement.numerator,
        metrics=metrics,
    )


def _observed_constituent_count(frame: pd.DataFrame) -> int:
    if frame.empty:
        return 0
    if "ticker" in frame.columns:
        return int(frame["ticker"].dropna().nunique())
    return int(len(frame))


def _truthy_column(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(False, index=frame.index, dtype=bool)
    values = frame[column]
    if pd.api.types.is_bool_dtype(values.dtype):
        return values.fillna(False).astype(bool)
    if pd.api.types.is_numeric_dtype(values.dtype):
        return pd.to_numeric(values, errors="coerce").fillna(0).ne(0)
    normalized = values.astype("string").str.strip().str.lower()
    return normalized.isin({"1", "true", "yes", "y", "eligible", "stale"})


def _date_column(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(pd.NaT, index=frame.index, dtype="datetime64[ns]")
    return pd.to_datetime(frame[column], errors="coerce").dt.normalize()


def _numeric_column(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(np.nan, index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce").replace(
        [np.inf, -np.inf], np.nan
    )


def _build_metric(
    *,
    numerator: int,
    eligible_denominator: int,
    total_count: int,
    column_available: bool,
) -> BreadthMetric:
    missing = max(0, total_count - eligible_denominator)
    if not column_available:
        status = "UNAVAILABLE"
        share = None
    elif eligible_denominator == 0:
        status = "UNDEFINED_NO_ELIGIBLE"
        share = None
    else:
        status = "DEFINED"
        share = round((numerator / eligible_denominator) * 100.0, 2)
    return BreadthMetric(
        share=share,
        numerator=int(numerator),
        eligible_denominator=int(eligible_denominator),
        missing_count=int(missing),
        total_count=int(total_count),
        status=status,
    )


def _metric_from_column(
    frame: pd.DataFrame,
    *,
    column: str,
    total_count: int,
    base_eligible: pd.Series,
    predicate: Callable[[pd.Series], pd.Series],
) -> BreadthMetric:
    available = column in frame.columns
    values = _numeric_column(frame, column)
    valid = base_eligible & values.notna()
    numerator = int(predicate(values.loc[valid]).sum()) if bool(valid.any()) else 0
    return _build_metric(
        numerator=numerator,
        eligible_denominator=int(valid.sum()),
        total_count=total_count,
        column_available=available,
    )


def _metric_from_pair(
    frame: pd.DataFrame,
    *,
    left_column: str,
    right_column: str,
    total_count: int,
    base_eligible: pd.Series,
    predicate: Callable[[pd.Series, pd.Series], pd.Series],
) -> BreadthMetric:
    available = left_column in frame.columns and right_column in frame.columns
    left = _numeric_column(frame, left_column)
    right = _numeric_column(frame, right_column)
    valid = base_eligible & left.notna() & right.notna()
    numerator = (
        int(predicate(left.loc[valid], right.loc[valid]).sum())
        if bool(valid.any())
        else 0
    )
    return _build_metric(
        numerator=numerator,
        eligible_denominator=int(valid.sum()),
        total_count=total_count,
        column_available=available,
    )
