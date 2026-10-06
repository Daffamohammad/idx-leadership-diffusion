"""Diffusion v2 — group-size-aware diffusion classification.

The groundwork v1 rule (`±10pp` raw breadth delta) is unstable for
small groups. A 10pp move in a 5-stock subsector is a single name
flipping; in a 50-stock sector it is meaningful sector rotation.

v2 adds a **constituent-count change floor** that scales with the
group size. The default is `max(2, ceil(0.10 * group_size))` — at
least 2 constituents or 10% of the group, whichever is larger.

Diffusion state labels are now also **graded**:
  * BROADENING_FIRM   — both the pp and constituent thresholds cleared
  * BROADENING_FRAGILE — pp cleared but constituent floor not met
  * STABLE            — neither
  * NARROWING_FRAGILE — symmetric
  * NARROWING_FIRM    — symmetric
  * UNCONFIRMED       — ineligible

A `conservative=False` flag lets the engine treat FRAGILE as STABLE
for ranking, while the UI still surfaces the FRAGILE distinction.

When the exact change in outperforming constituents is known, the pp
gate and the firm floor are evaluated in exact integer arithmetic.
Percentage-only callers fall back to a bounded-tolerance comparison.
"""
from __future__ import annotations

import math
from fractions import Fraction
from typing import Optional

from ..models.enums import DiffusionStateV2

# Bound for the floating-point reconstruction of a constituent count
# from breadth percentages. The reconstruction error stays below
# ~2.6e-16 * group_size (a few ULPs of the intermediate products), so
# 1e-9 absorbs it for any cohort below ~4 million constituents, while
# a genuinely sub-threshold move sits at least one full constituent
# (1.0) below the firm floor and cannot be promoted.
_IMPLIED_COUNT_TOLERANCE = 1e-9


def constituent_floor(group_size: int, fraction: float = 0.10, minimum: int = 2) -> int:
    """Minimum number of constituents that must change direction for the
    classification to be considered firm."""
    if group_size <= 0:
        return minimum
    exact_share = Fraction(fraction).limit_denominator(10**6) * group_size
    return max(minimum, math.ceil(exact_share))


def classify_diffusion_v2(
    *,
    breadth_current: Optional[float],
    breadth_previous: Optional[float],
    group_size: int,
    broadening_threshold_pp: float = 10.0,
    narrowing_threshold_pp: float = -10.0,
    fraction: float = 0.10,
    minimum_constituents: int = 2,
    eligible: bool = True,
    breadth_change_count: Optional[int] = None,
) -> DiffusionStateV2:
    """Group-size-aware diffusion classification.

    `breadth_current` and `breadth_previous` are in 0–100 (% of
    constituents outperforming the benchmark). Returns the v2 state.

    When `breadth_change_count` (the exact change in outperforming
    constituents) is supplied, both thresholds are evaluated in exact
    integer arithmetic; otherwise the percentages are used with a
    bounded tolerance.
    """
    if not eligible or breadth_current is None or breadth_previous is None:
        return DiffusionStateV2.UNCONFIRMED
    try:
        if not math.isfinite(float(breadth_current)) or not math.isfinite(
            float(breadth_previous)
        ):
            return DiffusionStateV2.UNCONFIRMED
    except (TypeError, ValueError):
        return DiffusionStateV2.UNCONFIRMED
    floor = constituent_floor(group_size, fraction=fraction, minimum=minimum_constituents)
    if breadth_change_count is not None and group_size > 0:
        # Exact path: the raw count change is ground truth, so neither the
        # pp gate nor the firm floor suffers floating-point reconstruction.
        delta_count = int(breadth_change_count)
        delta_x100 = Fraction(delta_count) * 100
        broadening_gate = Fraction(group_size) * Fraction(broadening_threshold_pp)
        narrowing_gate = Fraction(group_size) * Fraction(narrowing_threshold_pp)
        if delta_x100 >= broadening_gate and abs(delta_count) >= floor:
            return DiffusionStateV2.BROADENING_FIRM
        if delta_x100 <= narrowing_gate and abs(delta_count) >= floor:
            return DiffusionStateV2.NARROWING_FIRM
        if delta_x100 >= broadening_gate:
            return DiffusionStateV2.BROADENING_FRAGILE
        if delta_x100 <= narrowing_gate:
            return DiffusionStateV2.NARROWING_FRAGILE
        return DiffusionStateV2.STABLE
    delta_pp = float(breadth_current) - float(breadth_previous)
    # The breadth delta in pp must imply at least `floor` constituents
    # changed direction. With `group_size` constituents total, each pp
    # corresponds to `group_size / 100` constituents; we need
    # `delta_pp * group_size / 100 >= floor`.
    implied = abs(delta_pp) * group_size / 100.0
    if delta_pp >= broadening_threshold_pp and implied >= floor - _IMPLIED_COUNT_TOLERANCE:
        return DiffusionStateV2.BROADENING_FIRM
    if delta_pp <= narrowing_threshold_pp and implied >= floor - _IMPLIED_COUNT_TOLERANCE:
        return DiffusionStateV2.NARROWING_FIRM
    if delta_pp >= broadening_threshold_pp:
        return DiffusionStateV2.BROADENING_FRAGILE
    if delta_pp <= narrowing_threshold_pp:
        return DiffusionStateV2.NARROWING_FRAGILE
    return DiffusionStateV2.STABLE


def to_v1_state(v2: DiffusionStateV2) -> str:
    """Map v2 state to the v1 enum for legacy compatibility."""
    if v2 == DiffusionStateV2.BROADENING_FIRM:
        return "BROADENING"
    if v2 == DiffusionStateV2.BROADENING_FRAGILE:
        return "BROADENING"
    if v2 == DiffusionStateV2.NARROWING_FIRM:
        return "NARROWING"
    if v2 == DiffusionStateV2.NARROWING_FRAGILE:
        return "NARROWING"
    if v2 == DiffusionStateV2.UNCONFIRMED:
        return "UNCONFIRMED"
    return "STABLE"
