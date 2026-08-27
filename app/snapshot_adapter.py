"""Adapters from persisted snapshot rows to validated UI models."""
from __future__ import annotations

from typing import Any, Mapping

import pandas as pd

from idx_leadership.models import (
    ConcentrationMetrics,
    DiffusionState,
    DiffusionStateV2,
    GroupSnapshot,
    LeadershipState,
)


def _optional(value: Any) -> Any:
    """Convert pandas missing scalars to ``None`` before Pydantic validation."""
    if value is None:
        return None
    try:
        missing = pd.isna(value)
    except (TypeError, ValueError):
        return value
    if missing is pd.NA:
        return None
    try:
        return None if bool(missing) else value
    except (TypeError, ValueError):
        return value


def _enum_or_default(enum_type, value: Any, default):
    value = _optional(value)
    if value is None:
        return default
    try:
        return enum_type(value)
    except (TypeError, ValueError):
        return default


def _optional_enum(enum_type, value: Any):
    value = _optional(value)
    if value is None:
        return None
    try:
        return enum_type(value)
    except (TypeError, ValueError):
        return None


def _as_list(value: Any) -> list[str]:
    """Normalize a serialized taxonomy path without guessing a hierarchy."""
    value = _optional(value)
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(part) for part in value if _optional(part) is not None]
    return [str(value)]


def row_to_group_snapshot(row: Mapping[str, Any] | pd.Series) -> GroupSnapshot:
    """Build a ``GroupSnapshot`` from a parquet/csv row.

    Pandas represents nullable numeric parquet fields as ``NaN``. The
    canonical Pydantic models intentionally use ``None`` for missing
    values, so the adapter normalizes the boundary explicitly.
    """
    return GroupSnapshot(
        snapshot_date=_optional(row.get("snapshot_date")),
        taxonomy_level=_optional(row.get("taxonomy_level")) or "sector",
        taxonomy_path=_as_list(row.get("taxonomy_path")),
        group_id=row["group_id"],
        group_name=_optional(row.get("group_name")),
        constituent_count=int(_optional(row.get("constituent_count")) or 0),
        eligible_count=int(_optional(row.get("eligible_count")) or 0),
        missing_count=int(_optional(row.get("missing_count")) or 0),
        leadership_state=_enum_or_default(
            LeadershipState,
            row.get("leadership_state"),
            LeadershipState.UNCONFIRMED,
        ),
        diffusion_state=_enum_or_default(
            DiffusionState,
            row.get("diffusion_state"),
            DiffusionState.UNCONFIRMED,
        ),
        diffusion_state_v2=_optional_enum(
            DiffusionStateV2,
            row.get("diffusion_state_v2"),
        ),
        group_return_equal_weight=_optional(row.get("group_return_equal_weight")),
        group_excess_return=_optional(row.get("group_excess_return")),
        group_excess_return_5d=_optional(row.get("group_excess_return_5d")),
        group_excess_return_20d=_optional(row.get("group_excess_return_20d")),
        group_excess_return_60d=_optional(row.get("group_excess_return_60d")),
        breadth_positive=_optional(row.get("breadth_positive")),
        breadth_outperforming=_optional(row.get("breadth_outperforming")),
        breadth_delta=_optional(row.get("breadth_delta")),
        breadth_total_count=int(_optional(row.get("breadth_total_count")) or 0),
        breadth_eligible_count=int(_optional(row.get("breadth_eligible_count")) or 0),
        breadth_missing_count=int(_optional(row.get("breadth_missing_count")) or 0),
        breadth_positive_count=int(_optional(row.get("breadth_positive_count")) or 0),
        breadth_outperforming_count=int(
            _optional(row.get("breadth_outperforming_count")) or 0
        ),
        breadth_improving_count=int(_optional(row.get("breadth_improving_count")) or 0),
        concentration=ConcentrationMetrics(
            top1_contribution_share=_optional(row.get("top1_contribution_share")),
            top3_contribution_share=_optional(row.get("top3_contribution_share")),
            top5_contribution_share=_optional(row.get("top5_contribution_share")),
            top1_signed_share=_optional(row.get("top1_signed_share")),
            top3_signed_share=_optional(row.get("top3_signed_share")),
            hhi_contribution=_optional(row.get("hhi_contribution")),
            contributor_count=int(_optional(row.get("contributor_count")) or 0),
            convention=_optional(row.get("convention")) or "absolute_move",
            status=_optional(row.get("concentration_status")) or "UNDEFINED",
            signed_attribution_status=(
                _optional(row.get("signed_attribution_status")) or "UNDEFINED"
            ),
        ),
        leadership_rank=_optional(row.get("leadership_rank")),
        change_rank=_optional(row.get("change_rank")),
        leadership_persistence=int(_optional(row.get("leadership_persistence")) or 1),
        diffusion_persistence=int(_optional(row.get("diffusion_persistence")) or 1),
        method_version=_optional(row.get("method_version")) or "methodology-v1",
        feature_version=_optional(row.get("feature_version")) or "features-v1",
    )
