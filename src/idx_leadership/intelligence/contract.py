"""Brief contract (Integration Freeze v1).

This module is the single source of truth for the Markdown brief
contract. The Streamlit UI, the `export_market_brief` script, and any
future narration layer must consume the same section order, the same
section names, and the same field semantics.

Adding a section requires:

1. Appending to :data:`BRIEF_SECTIONS` (and keeping the order
   consistent with the brief view).
2. Implementing a renderer in :mod:`app.view_models` and a UI mirror.
3. Bumping :data:`BRIEF_CONTRACT_VERSION`.

Renaming an existing section or reordering the list breaks every
downstream consumer.
"""
from __future__ import annotations

from typing import Final


#: Section order is frozen. Do not reorder. Do not rename. Do not
#: insert new sections in the middle.
BRIEF_SECTIONS: Final[tuple[str, ...]] = (
    "Market Read",
    "Leadership",
    "Broadening",
    "Narrowing",
    "Material Shifts",
    "Contradictions",
    "Selected Evidence",
    "Screen Invalidation",
    "Data Gaps",
)


#: Bumped only when a section is added, removed, or renamed. The
#: Streamlit sidebar markdown export and the brief unit tests assert
#: against this version.
BRIEF_CONTRACT_VERSION: Final[str] = "brief-v1"


#: Intelligence contract version carried by :class:`GroupEvidence`.
#: Bumped when ``data_gaps``, ``contradictions``, or ``invalidation``
#: change shape.
INTELLIGENCE_CONTRACT_VERSION: Final[str] = "intelligence-v1"


#: Provider-mode contract version.
PROVIDER_MODE_CONTRACT_VERSION: Final[str] = "provider-mode-v1"


#: Snapshot-comparability contract version.
SNAPSHOT_COMPARABILITY_VERSION: Final[str] = "snapshot-comparability-v1"


#: Methodology version pinned by the integration freeze.
METHODOLOGY_VERSION: Final[str] = "methodology-v3"


#: Frozen data-gap categories. Adding a new category requires a
#: versioned addition in :class:`DataGapCategory`.
FROZEN_DATA_GAP_CATEGORIES: Final[tuple[str, ...]] = (
    "FUNDAMENTALS",
    "FOREIGN_FLOW",
    "BROKER_ACTIVITY",
    "FREE_FLOAT",
    "TAXONOMY",
    "CORPORATE_ACTIONS",
    "BENCHMARK",
)


#: Frozen data-gap statuses.
FROZEN_DATA_GAP_STATUSES: Final[tuple[str, ...]] = (
    "DATA_GAP",
    "NOT_INTEGRATED",
    "NOT_APPLIED",
    "PROTOTYPE",
    "STALE",
    "READY",
)


def contract_summary() -> dict[str, str]:
    """Return a dict of contract version strings for the audit log."""
    return {
        "brief_version": BRIEF_CONTRACT_VERSION,
        "intelligence_version": INTELLIGENCE_CONTRACT_VERSION,
        "provider_mode_version": PROVIDER_MODE_CONTRACT_VERSION,
        "snapshot_comparability_version": SNAPSHOT_COMPARABILITY_VERSION,
        "methodology_version": METHODOLOGY_VERSION,
        "section_count": str(len(BRIEF_SECTIONS)),
    }
