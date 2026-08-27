"""Leadership state classification.

Provisional four-state model + UNCONFIRMED:

- LEADING:    excess_return_20d > 0 and acceleration >= threshold
- IMPROVING:  excess_return_20d <= 0 and acceleration >= threshold
- LAGGING:    excess_return_20d <= 0 and acceleration <  threshold
- WEAKENING:  excess_return_20d > 0 and acceleration <  threshold

`acceleration` = excess_return_5d - excess_return_60d (pp).
All inputs optional; UNCONFIRMED returned on insufficient data or
ineligible groups.
"""
from __future__ import annotations

from typing import Optional

from ..models import LeadershipState
from ..utils import get_logger

_log = get_logger(__name__)


def classify_leadership(
    *,
    excess_return_20d: Optional[float],
    excess_return_5d: Optional[float],
    excess_return_60d: Optional[float],
    acceleration_threshold_pp: float = 1.0,
    excess_return_improving: float = 0.0,
    excess_return_leading: float = 0.0,
    eligible: bool = True,
) -> LeadershipState:
    if not eligible:
        return LeadershipState.UNCONFIRMED
    if excess_return_20d is None or excess_return_5d is None or excess_return_60d is None:
        return LeadershipState.UNCONFIRMED
    try:
        acceleration = float(excess_return_5d) - float(excess_return_60d)
    except (TypeError, ValueError):
        return LeadershipState.UNCONFIRMED
    improving = acceleration >= acceleration_threshold_pp
    if excess_return_20d > excess_return_leading and improving:
        return LeadershipState.LEADING
    if excess_return_20d <= excess_return_improving and improving:
        return LeadershipState.IMPROVING
    if excess_return_20d <= excess_return_improving and not improving:
        return LeadershipState.LAGGING
    if excess_return_20d > excess_return_leading and not improving:
        return LeadershipState.WEAKENING
    # A deliberate neutral buffer between different configured sign
    # thresholds is unconfirmed, never silently forced into a quadrant.
    return LeadershipState.UNCONFIRMED
