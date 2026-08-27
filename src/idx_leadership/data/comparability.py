"""Compatibility checks for point-in-time snapshot comparisons.

State changes are meaningful only when both observations were produced under
the same provider mode and compatible analytical definitions.  This module is
pure and intentionally independent from the snapshot reader so it can be used
by the pipeline, UI, export tools, and tests.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping

from pydantic import BaseModel


@dataclass(frozen=True)
class SnapshotComparability:
    comparable: bool
    status: str
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _mapping(value: Mapping[str, Any] | BaseModel) -> Mapping[str, Any]:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    return value


def _value(value: Mapping[str, Any], key: str) -> Any:
    raw = value.get(key)
    return getattr(raw, "value", raw)


def assess_snapshot_comparability(
    current: Mapping[str, Any] | BaseModel,
    previous: Mapping[str, Any] | BaseModel,
    *,
    require_chronology: bool = True,
) -> SnapshotComparability:
    """Return explicit reasons when two snapshot manifests cannot be compared."""

    cur = _mapping(current)
    prev = _mapping(previous)
    reasons: list[str] = []
    warnings: list[str] = []

    cur_mode = _value(cur, "provider_mode")
    prev_mode = _value(prev, "provider_mode")
    if cur_mode is not None and prev_mode is not None:
        if cur_mode != prev_mode:
            reasons.append(f"provider mode differs: {prev_mode} -> {cur_mode}")
    elif _value(cur, "provider") != _value(prev, "provider"):
        reasons.append(
            f"provider differs: {_value(prev, 'provider')} -> {_value(cur, 'provider')}"
        )
    else:
        warnings.append("provider_mode missing on a legacy manifest; provider identity used")

    exact_fields = (
        "method_version",
        "feature_version",
        "leadership_version",
        "diffusion_version",
        "concentration_version",
        "eligibility_version",
        "universe_version",
        "taxonomy_version",
    )
    for key in exact_fields:
        current_value = _value(cur, key)
        previous_value = _value(prev, key)
        if current_value is None or previous_value is None:
            warnings.append(f"{key} missing on a legacy manifest")
        elif current_value != previous_value:
            reasons.append(f"{key} differs: {previous_value} -> {current_value}")

    if require_chronology:
        current_date = _value(cur, "as_of") or _value(cur, "snapshot_date")
        previous_date = _value(prev, "as_of") or _value(prev, "snapshot_date")
        if current_date is not None and previous_date is not None:
            if str(previous_date) >= str(current_date):
                reasons.append(
                    f"previous snapshot is not earlier: previous={previous_date} current={current_date}"
                )

    return SnapshotComparability(
        comparable=not reasons,
        status="COMPATIBLE" if not reasons else "INCOMPATIBLE",
        reasons=reasons,
        warnings=warnings,
    )

