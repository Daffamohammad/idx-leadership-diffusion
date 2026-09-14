"""Data-quality UI rendering.

Renders a per-endpoint status table for the Streamlit sidebar or a
standalone panel. Reads the per-endpoint `EndpointQuality` records
from a snapshot's `quality.json` (when present) or builds them from
the current run.
"""
from __future__ import annotations

from typing import Iterable, Optional

import pandas as pd

from idx_leadership.data.endpoint_status import (
    EndpointQuality,
    EndpointStatus,
    rollup_status,
)


def render_endpoint_status(endpoints: Iterable[EndpointQuality]) -> pd.DataFrame:
    rows = [e.to_dict() for e in endpoints]
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    return df


def overall_rollup(endpoints: list[EndpointQuality]) -> str:
    return rollup_status(endpoints)


def human_readable_status(s: str) -> str:
    """Render an internal status as clean, user-facing product language."""
    raw = getattr(s, "value", s)
    key = str(raw).upper().replace(" ", "_")
    labels = {
        "READY": "Ready",
        "READY_WITH_GAPS": "Ready · partial coverage",
        "PARTIAL": "Partial coverage",
        "DATA_GAP": "Not available",
        "NOT_INTEGRATED": "Outside current scope",
        "NOT_APPLIED": "Not used by current method",
        "PROTOTYPE": "Prototype source",
        "FIXTURE": "Fixture source",
        "STALE": "Stale",
        "FAILED": "Failed",
        "UNAVAILABLE": "Unavailable",
    }
    return labels.get(key, str(raw).replace("_", " ").title())


def highlight_row_color(status: str) -> str:
    """Return a CSS color token for a status (used by the Streamlit table)."""
    if status == EndpointStatus.READY:
        return "green"
    if status in (EndpointStatus.READY_WITH_GAPS, EndpointStatus.PARTIAL):
        return "orange"
    if status in (EndpointStatus.STALE, EndpointStatus.FAILED):
        return "red"
    return "grey"
