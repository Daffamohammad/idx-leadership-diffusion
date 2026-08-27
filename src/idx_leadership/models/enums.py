"""Enums used across the canonical schema."""
from __future__ import annotations

from enum import Enum


class LeadershipState(str, Enum):
    LEADING = "LEADING"
    IMPROVING = "IMPROVING"
    LAGGING = "LAGGING"
    WEAKENING = "WEAKENING"
    UNCONFIRMED = "UNCONFIRMED"


class DiffusionState(str, Enum):
    BROADENING = "BROADENING"
    STABLE = "STABLE"
    NARROWING = "NARROWING"
    UNCONFIRMED = "UNCONFIRMED"


class DiffusionStateV2(str, Enum):
    """Group-size-aware diffusion states.

    ``DiffusionState`` remains the collapsed compatibility view; v2
    snapshots carry this richer state alongside it.
    """

    BROADENING_FIRM = "BROADENING_FIRM"
    BROADENING_FRAGILE = "BROADENING_FRAGILE"
    STABLE = "STABLE"
    NARROWING_FRAGILE = "NARROWING_FRAGILE"
    NARROWING_FIRM = "NARROWING_FIRM"
    UNCONFIRMED = "UNCONFIRMED"


class MaterialityLabel(str, Enum):
    NEW_LEADER = "NEW_LEADER"
    IMPROVING = "IMPROVING"
    BROADENING = "BROADENING"
    NARROWING = "NARROWING"
    DETERIORATING = "DETERIORATING"
    LOSS_OF_LEADERSHIP = "LOSS_OF_LEADERSHIP"
    STABLE = "STABLE"


class EligibilityStatus(str, Enum):
    ELIGIBLE = "ELIGIBLE"
    INELIGIBLE = "INELIGIBLE"
    UNCONFIRMED = "UNCONFIRMED"


class DataQualityStatus(str, Enum):
    READY = "READY"
    READY_WITH_GAPS = "READY_WITH_GAPS"
    STALE = "STALE"
    FAILED = "FAILED"


class PriceBasis(str, Enum):
    ADJUSTED_CLOSE = "adjusted_close"
    CLOSE = "close"


class ProviderName(str, Enum):
    YFINANCE = "yfinance"
    SECTORS = "sectors"
    FIXTURE = "fixture"


class ProviderMode(str, Enum):
    """User-visible execution mode.

    Provider identity and execution mode are intentionally separate.  A
    Sectors-shaped fixture is still a fixture, and a public prototype must
    never be presented as a live Sectors result.
    """

    DEMO_FIXTURE = "DEMO_FIXTURE"
    PUBLIC_PROTOTYPE = "PUBLIC_PROTOTYPE"
    SECTORS_FIXTURE = "SECTORS_FIXTURE"
    SECTORS_LIVE = "SECTORS_LIVE"
