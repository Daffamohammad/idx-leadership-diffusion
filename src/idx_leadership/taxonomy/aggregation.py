"""Aggregation engine for taxonomies.

Given a :class:`Taxonomy` and a price history per ticker (plus an IHSG
benchmark series), compute one :class:`TaxonomyAggregate` per taxonomy
group. Calculations are intentionally identical across sector, Konglo,
and themes so the same map surface can render any taxonomy.

Outputs (per group):

* ``equal_weight_return_20d`` and ``equal_weight_return_60d`` — mean of
  ticker-level returns in the group, equally weighted.
* ``excess_return_20d`` / ``excess_return_60d`` — group return minus the
  IHSG benchmark return over the same horizon.
* ``breadth_outperforming`` — fraction of group members whose 20D excess
  return is positive.
* ``breadth_delta`` — change in breadth vs a comparable prior snapshot
  (only when one is supplied).
* ``leadership_state`` / ``diffusion_state`` — derived from the same
  thresholds used in the existing leadership pipeline.
* ``map_x`` / ``map_y`` — coordinates in the leadership quadrant space.
* ``off_scale`` — true when the cell sits outside the visible map
  rectangle.
* ``data_quality`` — ``READY`` / ``READY_WITH_GAPS`` / ``DATA_GAP``
  / ``UNAVAILABLE``.

Inputs use a long-form ``prices`` DataFrame (``ticker``, ``date``,
``close``) and ``benchmark`` DataFrame (``date``, ``close``). The
horizon is computed from the most recent date in the price series
forward.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any, Iterable, Mapping

import pandas as pd

from ..features.relative_strength import (
    compute_benchmark_returns,
    compute_excess_returns,
)
from ..signals.diffusion_v2 import classify_diffusion_v2, to_v1_state
from ..signals.leadership import classify_leadership
from .models import MembershipType, Taxonomy, TaxonomyKind, TaxonomyMembership

_HORIZONS = {"5d": 5, "20d": 20, "60d": 60}


@dataclass
class TaxonomyAggregate:
    taxonomy_id: str
    taxonomy_version: str
    taxonomy_kind: str
    taxonomy_group_id: str
    taxonomy_group_name: str
    constituent_count: int
    eligible_constituent_count: int
    coverage_pct: float
    equal_weight_return_20d: float | None
    equal_weight_return_60d: float | None
    excess_return_20d: float | None
    excess_return_60d: float | None
    benchmark_return_20d: float | None
    benchmark_return_60d: float | None
    breadth_outperforming: float | None
    prev_breadth_outperforming: float | None
    breadth_delta: float | None
    leadership_state: str
    diffusion_state: str
    concentration_top3: float | None
    map_x: float | None
    map_y: float | None
    off_scale: bool
    data_quality: str
    prototype: bool
    membership_kind_breakdown: dict[str, int] = field(default_factory=dict)
    sample_foreign_flow_idr: int | None = None
    sample_foreign_flow_direction: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _round_or_none(value: float | None, places: int = 4) -> float | None:
    if value is None or not _is_finite(value):
        return None
    return round(float(value), places)


def _is_finite(value: float | int | None) -> bool:
    if value is None:
        return False
    try:
        return float(value) == float(value)
    except (TypeError, ValueError):
        return False


def _as_of_date(value: date | str | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    try:
        return pd.Timestamp(value).date()
    except (TypeError, ValueError):
        return None


def _finite_mean(frame: pd.DataFrame, column: str) -> float | None:
    if column not in frame.columns:
        return None
    values = pd.to_numeric(frame[column], errors="coerce").dropna()
    return float(values.mean()) if not values.empty else None


def _previous_breadth_value(
    previous: Mapping[Any, float] | None,
    *,
    group_id: str,
    previous_as_of: date | str | None,
) -> float | None:
    if previous is None:
        return None
    direct = previous.get(group_id)
    if direct is not None:
        return float(direct)
    if previous_as_of is None:
        return None
    dated = previous.get((group_id, str(previous_as_of)))
    return float(dated) if dated is not None else None


def _map_xy(excess: float | None, breadth: float | None) -> tuple[float | None, float | None, bool]:
    """Convert (excess_return_20d, breadth_outperforming) to map coordinates.

    Returns ``(map_x, map_y, off_scale)``. Coordinates are anchored to
    the same scale used by :mod:`app.web.src.data.mapGeometry`: x in
    [-15, 15] and y in [0, 100]. Values outside the visible window set
    ``off_scale`` to ``True`` but the coordinates are still reported.
    """
    if excess is None or breadth is None:
        return None, None, False
    map_x = max(-15.0, min(15.0, float(excess)))
    map_y = max(0.0, min(100.0, float(breadth)))
    off_scale = bool(
        (excess < -15.0 or excess > 15.0 or breadth < 0 or breadth > 100)
    )
    return map_x, map_y, off_scale


def _group_breakdown(memberships: Iterable[TaxonomyMembership]) -> dict[str, int]:
    breakdown = {"PRIMARY": 0, "SECONDARY": 0, "EXCLUDED": 0}
    for membership in memberships:
        breakdown[membership.membership_type.value] = (
            breakdown.get(membership.membership_type.value, 0) + 1
        )
    return breakdown


def aggregate_taxonomy(
    taxonomy: Taxonomy,
    prices: pd.DataFrame,
    benchmark: pd.DataFrame,
    *,
    as_of: date | str | None = None,
    prev_breadth: Mapping[Any, float] | None = None,
    prev_as_of: date | str | None = None,
    foreign_flow_by_group: Mapping[str, dict[str, Any]] | None = None,
    price_col: str | None = None,
    min_eligible_constituents: int = 2,
    min_coverage_pct: float = 60.0,
) -> list[TaxonomyAggregate]:
    """Aggregate one taxonomy using canonical trading-session returns.

    All observations are filtered at ``as_of`` before feature calculation.
    The 5/20/60-day horizons are trading-session offsets implemented by the
    same return engine used by the primary sector pipeline.
    """
    def empty_results() -> list[TaxonomyAggregate]:
        return [
            _empty_aggregate(taxonomy, group_id, taxonomy.members_of(group_id))
            for group_id in taxonomy.groups()
        ]

    # A taxonomy is still useful when no price rows were acquired: callers
    # need one explicit DATA_GAP aggregate per group rather than an empty
    # response that looks like the taxonomy was never evaluated.
    if prices is None or prices.empty:
        return empty_results()
    required_price_cols = {"ticker", "date", "close"}
    if not required_price_cols.issubset(set(prices.columns)):
        return empty_results()
    prices = prices.copy()
    prices["date"] = pd.to_datetime(prices["date"], errors="coerce")
    prices["ticker"] = prices["ticker"].astype(str).str.upper()
    resolved_price_col = price_col
    if resolved_price_col not in prices.columns:
        resolved_price_col = (
            "adjusted_close" if "adjusted_close" in prices.columns else "close"
        )
    if resolved_price_col not in prices.columns:
        return empty_results()
    prices[resolved_price_col] = pd.to_numeric(
        prices[resolved_price_col], errors="coerce"
    )
    prices = prices.dropna(subset=["date", resolved_price_col])
    prices = prices[prices[resolved_price_col] > 0]
    if prices.empty:
        return empty_results()

    resolved_as_of = _as_of_date(as_of)
    if resolved_as_of is not None:
        prices = prices[prices["date"].dt.date <= resolved_as_of]
        if prices.empty:
            return empty_results()

    benchmark_df = benchmark.copy() if benchmark is not None else pd.DataFrame()
    if not benchmark_df.empty and "date" in benchmark_df.columns:
        benchmark_df = benchmark_df.assign(
            date=pd.to_datetime(benchmark_df["date"], errors="coerce")
        )
        benchmark_df = benchmark_df.dropna(subset=["date", "close"])
        benchmark_df["close"] = pd.to_numeric(
            benchmark_df["close"], errors="coerce"
        )
        benchmark_df = benchmark_df[benchmark_df["close"] > 0]
        if resolved_as_of is not None:
            benchmark_df = benchmark_df[
                benchmark_df["date"].dt.date <= resolved_as_of
            ]

    features = compute_excess_returns(
        prices,
        benchmark_df,
        horizons=_HORIZONS,
        as_of=resolved_as_of,
        security_price_col=resolved_price_col,
        benchmark_price_col="close",
    )
    benchmark_returns = compute_benchmark_returns(
        benchmark_df,
        horizons=_HORIZONS,
        as_of=resolved_as_of,
        price_col="close",
    )
    benchmark_20d = benchmark_returns.get("return_20d")
    benchmark_60d = benchmark_returns.get("return_60d")
    benchmark_20d = (
        float(benchmark_20d) if _is_finite(benchmark_20d) else None
    )
    benchmark_60d = (
        float(benchmark_60d) if _is_finite(benchmark_60d) else None
    )

    aggregates: list[TaxonomyAggregate] = []
    groups = taxonomy.groups()
    foreign_lookup = foreign_flow_by_group or {}

    for group_id in groups:
        members = taxonomy.members_of(group_id)
        primary_tickers = sorted({m.ticker for m in members})
        if not primary_tickers:
            continue
        group_features = features[features["ticker"].isin(primary_tickers)].copy()
        eligible_features = group_features.dropna(
            subset=["return_20d", "excess_return_20d"]
        )
        eligible_count = int(eligible_features["ticker"].nunique())
        constituent_count = len(primary_tickers)
        coverage_pct = (
            100.0 * eligible_count / constituent_count if constituent_count else 0.0
        )
        if eligible_features.empty:
            aggregates.append(_empty_aggregate(taxonomy, group_id, members))
            continue
        group_20d = _finite_mean(eligible_features, "return_20d")
        group_60d = _finite_mean(group_features, "return_60d")
        excess_5d = _finite_mean(group_features, "excess_return_5d")
        excess_20d = _finite_mean(eligible_features, "excess_return_20d")
        excess_60d = _finite_mean(group_features, "excess_return_60d")

        # Breadth = fraction of members whose 20D excess > 0
        breadth = (
            float((eligible_features["excess_return_20d"] > 0).mean() * 100.0)
            if eligible_count
            else None
        )

        prev_breadth_value = _previous_breadth_value(
            prev_breadth,
            group_id=group_id,
            previous_as_of=prev_as_of,
        )
        breadth_delta: float | None = None
        if breadth is not None and prev_breadth_value is not None:
            breadth_delta = breadth - prev_breadth_value

        group_is_eligible = (
            eligible_count >= min_eligible_constituents
            and coverage_pct >= min_coverage_pct
        )
        leadership = classify_leadership(
            excess_return_20d=excess_20d,
            excess_return_5d=excess_5d,
            excess_return_60d=excess_60d,
            eligible=group_is_eligible,
        ).value
        diffusion = to_v1_state(
            classify_diffusion_v2(
                breadth_current=breadth,
                breadth_previous=prev_breadth_value,
                group_size=constituent_count,
                eligible=group_is_eligible,
            )
        )
        map_x, map_y, off_scale = _map_xy(excess_20d, breadth)

        # Concentration (top3 share) requires per-ticker returns within
        # the 20D horizon. If unavailable, leave as None.
        concentration: float | None = None
        absolute_returns = (
            pd.to_numeric(eligible_features["return_20d"], errors="coerce")
            .dropna()
            .abs()
            .sort_values(ascending=False)
        )
        if not absolute_returns.empty and float(absolute_returns.sum()) > 0:
            concentration = float(
                100.0 * absolute_returns.head(3).sum() / absolute_returns.sum()
            )

        if breadth is None or excess_20d is None or eligible_count == 0:
            data_quality = "DATA_GAP"
        elif (
            not group_is_eligible
            or coverage_pct < 100.0
            or prev_breadth_value is None
        ):
            data_quality = "READY_WITH_GAPS"
        else:
            data_quality = "READY"

        flow_context = foreign_lookup.get(group_id)
        sample_flow_idr = (
            int(flow_context.get("net_value_idr"))
            if isinstance(flow_context, Mapping)
            and isinstance(flow_context.get("net_value_idr"), (int, float))
            else None
        )
        flow_direction = (
            str(flow_context.get("direction")) if isinstance(flow_context, Mapping) else None
        )

        aggregate = TaxonomyAggregate(
            taxonomy_id=taxonomy.taxonomy_id,
            taxonomy_version=taxonomy.taxonomy_version,
            taxonomy_kind=taxonomy.taxonomy_kind.value,
            taxonomy_group_id=group_id,
            taxonomy_group_name=members[0].taxonomy_group_name or group_id,
            constituent_count=constituent_count,
            eligible_constituent_count=eligible_count,
            coverage_pct=round(coverage_pct, 2),
            equal_weight_return_20d=_round_or_none(group_20d, 4),
            equal_weight_return_60d=_round_or_none(group_60d, 4),
            excess_return_20d=_round_or_none(excess_20d, 4),
            excess_return_60d=_round_or_none(excess_60d, 4),
            benchmark_return_20d=_round_or_none(benchmark_20d, 4),
            benchmark_return_60d=_round_or_none(benchmark_60d, 4),
            breadth_outperforming=_round_or_none(breadth, 2),
            prev_breadth_outperforming=_round_or_none(prev_breadth_value, 2),
            breadth_delta=_round_or_none(breadth_delta, 2),
            leadership_state=leadership,
            diffusion_state=diffusion,
            concentration_top3=_round_or_none(concentration, 2),
            map_x=_round_or_none(map_x, 3),
            map_y=_round_or_none(map_y, 3),
            off_scale=off_scale,
            data_quality=data_quality,
            prototype=taxonomy.source_kind.value
            != "PRIMARY_INDEX",
            membership_kind_breakdown=_group_breakdown(members),
            sample_foreign_flow_idr=sample_flow_idr,
            sample_foreign_flow_direction=flow_direction,
        )
        aggregates.append(aggregate)

    if as_of is not None:
        aggregates.sort(key=lambda a: a.taxonomy_group_name)
    return aggregates


def _empty_aggregate(
    taxonomy: Taxonomy, group_id: str, members: list[TaxonomyMembership]
) -> TaxonomyAggregate:
    return TaxonomyAggregate(
        taxonomy_id=taxonomy.taxonomy_id,
        taxonomy_version=taxonomy.taxonomy_version,
        taxonomy_kind=taxonomy.taxonomy_kind.value,
        taxonomy_group_id=group_id,
        taxonomy_group_name=(members[0].taxonomy_group_name if members else group_id),
        constituent_count=len({m.ticker for m in members}),
        eligible_constituent_count=0,
        coverage_pct=0.0,
        equal_weight_return_20d=None,
        equal_weight_return_60d=None,
        excess_return_20d=None,
        excess_return_60d=None,
        benchmark_return_20d=None,
        benchmark_return_60d=None,
        breadth_outperforming=None,
        prev_breadth_outperforming=None,
        breadth_delta=None,
        leadership_state="UNCONFIRMED",
        diffusion_state="UNCONFIRMED",
        concentration_top3=None,
        map_x=None,
        map_y=None,
        off_scale=False,
        data_quality="DATA_GAP",
        prototype=taxonomy.source_kind.value != "PRIMARY_INDEX",
        membership_kind_breakdown=_group_breakdown(members),
    )


def build_taxonomy_payload(
    taxonomy: Taxonomy,
    aggregates: list[TaxonomyAggregate],
    *,
    as_of: date | str | None,
    benchmark_id: str = "^JKSE",
) -> dict[str, Any]:
    """Wrap a :class:`Taxonomy` and its aggregates into a serializable dict."""
    return {
        "schema_version": "taxonomy-view-v2",
        "taxonomy_id": taxonomy.taxonomy_id,
        "taxonomy_name": taxonomy.taxonomy_name,
        "taxonomy_version": taxonomy.taxonomy_version,
        "taxonomy_kind": taxonomy.taxonomy_kind.value,
        "source_kind": taxonomy.source_kind.value,
        "source_as_of": taxonomy.source_as_of.isoformat() if taxonomy.source_as_of else None,
        "membership_policy": taxonomy.membership_policy,
        "provider_mode": taxonomy.provider_mode,
        "benchmark_id": benchmark_id,
        "as_of": str(as_of) if as_of else None,
        "coverage": taxonomy._coverage_payload(),
        # Keep the source-backed membership records beside the aggregates so
        # downstream group detail views can explain who belongs to a
        # prototype taxonomy without reverse-engineering the YAML registry.
        "memberships": [membership.to_dict() for membership in taxonomy.memberships],
        "groups": [aggregate.to_dict() for aggregate in aggregates],
    }
