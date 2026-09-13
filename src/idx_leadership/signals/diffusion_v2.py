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
"""
from __future__ import annotations

import math
from typing import Optional

from ..models.enums import DiffusionStateV2


def constituent_floor(group_size: int, fraction: float = 0.10, minimum: int = 2) -> int:
    """Minimum number of constituents that must change direction for the
    classification to be considered firm."""
    if group_size <= 0:
        return minimum
    return max(minimum, int(math.ceil(fraction * group_size)))


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
) -> DiffusionStateV2:
    """Group-size-aware diffusion classification.

    `breadth_current` and `breadth_previous` are in 0–100 (% of
    constituents outperforming the benchmark). Returns the v2 state.
    """
    if not eligible or breadth_current is None or breadth_previous is None:
        return DiffusionStateV2.UNCONFIRMED
    try:
        import math

        if not math.isfinite(float(breadth_current)) or not math.isfinite(
            float(breadth_previous)
        ):
            return DiffusionStateV2.UNCONFIRMED
    except (TypeError, ValueError):
        return DiffusionStateV2.UNCONFIRMED
    delta_pp = float(breadth_current) - float(breadth_previous)
    floor = constituent_floor(group_size, fraction=fraction, minimum=minimum_constituents)
    # The breadth delta in pp must imply at least `floor` constituents
    # changed direction. With `group_size` constituents total, each pp
    # corresponds to `group_size / 100` constituents; we need
    # `delta_pp * group_size / 100 >= floor`.
    implied = abs(delta_pp) * group_size / 100.0
    if delta_pp >= broadening_threshold_pp and implied >= floor:
        return DiffusionStateV2.BROADENING_FIRM
    if delta_pp <= narrowing_threshold_pp and implied >= floor:
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
