"""Diffusion state classification.

Diffusion measures whether leadership is spreading (BROADENING),
stable, or concentrating (NARROWING). The simplest defensible baseline
is the breadth delta vs the prior observation. Thresholds are
configurable and unit-tested.
"""
from __future__ import annotations

from typing import Optional

from ..models import DiffusionState
from ..utils import get_logger

_log = get_logger(__name__)


def classify_diffusion(
    *,
    breadth_delta_pp: Optional[float],
    broadening_threshold_pp: float = 10.0,
    narrowing_threshold_pp: float = -10.0,
    eligible: bool = True,
) -> DiffusionState:
    """Return a diffusion state given the breadth delta (in percentage points)."""
    if not eligible or breadth_delta_pp is None:
        return DiffusionState.UNCONFIRMED
    if breadth_delta_pp >= broadening_threshold_pp:
        return DiffusionState.BROADENING
    if breadth_delta_pp <= narrowing_threshold_pp:
        return DiffusionState.NARROWING
    return DiffusionState.STABLE
