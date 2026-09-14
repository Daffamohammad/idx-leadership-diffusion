"""Structured data-gap builder (Integration Freeze v1).

The Markdown brief and the Streamlit UI both consume
:class:`DataGap` objects.  The categories and statuses are frozen at
v1.  Adding a new category or status requires a contract version bump
in :class:`GroupEvidence.contract_version`.
"""
from __future__ import annotations

from typing import Iterable

from ..models import (
    DataGap,
    DataGapCategory,
    DataGapStatus,
    GroupSnapshot,
    ProviderMode,
)


def _gap(category: DataGapCategory, status: DataGapStatus, label: str, note: str | None = None) -> DataGap:
    return DataGap(category=category, status=status, label=label, note=note)


def build_data_gaps(
    *,
    provider_mode: ProviderMode,
    has_corporate_action_metadata: bool = False,
) -> list[DataGap]:
    """Return the canonical data-gap list for a snapshot at this provider mode.

    The list is deterministic and ordered so the Markdown render is
    stable.  Categories never appear twice.
    """
    gaps: list[DataGap] = []
    seen: set[DataGapCategory] = set()

    def add(category: DataGapCategory, status: DataGapStatus, label: str, note: str | None = None) -> None:
        if category in seen:
            return
        gaps.append(_gap(category, status, label, note))
        seen.add(category)

    if provider_mode in (ProviderMode.SECTORS_LIVE,):
        # Live run; confirmation layers are reachable but not yet
        # materialised. Keep the machine status, but use neutral product
        # language so the UI describes scope and provenance rather than
        # exposing an internal quality label.
        add(DataGapCategory.FUNDAMENTALS, DataGapStatus.DATA_GAP, "Fundamentals source is not attached for this scope")
        add(DataGapCategory.FOREIGN_FLOW, DataGapStatus.DATA_GAP, "Foreign-flow source is not attached for this scope")
        add(DataGapCategory.BROKER_ACTIVITY, DataGapStatus.NOT_INTEGRATED, "Broker activity is outside the current scope")
        add(DataGapCategory.FREE_FLOAT, DataGapStatus.NOT_APPLIED, "Free-float weighting is not used; equal-weight method is active")
        if has_corporate_action_metadata:
            add(DataGapCategory.CORPORATE_ACTIONS, DataGapStatus.READY, "Corporate-action metadata present (annotation-only per D018)")
        else:
            add(DataGapCategory.CORPORATE_ACTIONS, DataGapStatus.DATA_GAP, "Corporate-action metadata is not attached")
    else:
        # Non-live modes (PUBLIC_PROTOTYPE, SECTORS_FIXTURE, DEMO_FIXTURE).
        add(DataGapCategory.FUNDAMENTALS, DataGapStatus.DATA_GAP, "Fundamentals source is not attached for this scope")
        add(DataGapCategory.FOREIGN_FLOW, DataGapStatus.DATA_GAP, "Foreign-flow source is not attached for this scope")
        add(DataGapCategory.BROKER_ACTIVITY, DataGapStatus.NOT_INTEGRATED, "Broker activity is outside the current scope")
        add(DataGapCategory.FREE_FLOAT, DataGapStatus.NOT_APPLIED, "Free-float weighting is not used; equal-weight method is active")
        if provider_mode in (ProviderMode.PUBLIC_PROTOTYPE, ProviderMode.DEMO_FIXTURE):
            add(DataGapCategory.TAXONOMY, DataGapStatus.PROTOTYPE, "IDX taxonomy is not attached; prototype grouping remains in use")
        else:
            add(DataGapCategory.TAXONOMY, DataGapStatus.READY, "Sectors fixture taxonomy is in use")

    # Sectors benchmark coverage: only flagged when explicitly stale.
    add(DataGapCategory.BENCHMARK, DataGapStatus.READY, "Benchmark date and series present")

    return gaps
