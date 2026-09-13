"""Per-endpoint data-quality status.

The brief §73 requires that the data-quality UI expose separate
statuses for each data domain (core, taxonomy, benchmark, fundamentals,
flow, events) rather than one global flag.

This module provides:

* `EndpointStatus` enum: READY / READY_WITH_GAPS / PARTIAL / STALE
  / FAILED / UNKNOWN.
* `EndpointQuality`: per-endpoint name + status + reasons + last_run
  + provider.
* `assess_endpoint_quality(name, rows, expected, ...)` builder.

A snapshot's `quality.json` now contains a `by_endpoint` mapping
alongside the legacy global `status` and `coverage_pct`. The UI
reads the per-endpoint view; the global status is a roll-up.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from ..models.enums import DataQualityStatus


# Per-endpoint status vocabulary. The global `DataQualityStatus` enum
# is kept for back-compat; the per-endpoint level adds `PARTIAL` and
# `UNKNOWN`.
class EndpointStatus(str):
    READY = "READY"
    READY_WITH_GAPS = "READY_WITH_GAPS"
    PARTIAL = "PARTIAL"
    STALE = "STALE"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


@dataclass
class EndpointQuality:
    name: str
    status: str = EndpointStatus.UNKNOWN
    rows: int = 0
    expected_rows: Optional[int] = None
    reasons: list[str] = field(default_factory=list)
    last_run: Optional[date] = None
    provider: str = "unknown"

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "status": self.status,
            "rows": self.rows,
            "expected_rows": self.expected_rows,
            "reasons": list(self.reasons),
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "provider": self.provider,
        }


def assess_endpoint_quality(
    name: str,
    rows: int,
    *,
    provider: str = "sectors",
    expected_rows: Optional[int] = None,
    errors: Optional[list[str]] = None,
    last_run: Optional[date] = None,
) -> EndpointQuality:
    """Build an EndpointQuality for one domain."""
    eq = EndpointQuality(
        name=name,
        rows=rows,
        expected_rows=expected_rows,
        provider=provider,
        last_run=last_run,
    )
    if errors:
        eq.reasons.extend(errors)
        if rows == 0:
            eq.status = EndpointStatus.FAILED
        elif rows < (expected_rows or rows) * 0.5:
            eq.status = EndpointStatus.PARTIAL
        else:
            eq.status = EndpointStatus.READY_WITH_GAPS
        return eq
    if rows == 0:
        eq.status = EndpointStatus.FAILED
        eq.reasons.append("no_rows")
    elif expected_rows is not None and rows < expected_rows * 0.5:
        eq.status = EndpointStatus.PARTIAL
        eq.reasons.append(f"rows {rows} < 50% of expected {expected_rows}")
    elif expected_rows is not None and rows < expected_rows:
        eq.status = EndpointStatus.READY_WITH_GAPS
        eq.reasons.append(f"rows {rows} < expected {expected_rows}")
    else:
        eq.status = EndpointStatus.READY
    return eq


def rollup_status(endpoints: list[EndpointQuality]) -> str:
    """Roll up per-endpoint statuses to one global status.

    Rules:
      * any FAILED → FAILED
      * any PARTIAL → READY_WITH_GAPS (PARTIAL has no global enum member;
        it always signals a gap, never clean READY)
      * any READY_WITH_GAPS → READY_WITH_GAPS
      * any STALE → STALE
      * otherwise READY
    """
    statuses = {e.status for e in endpoints}
    if EndpointStatus.FAILED in statuses:
        return DataQualityStatus.FAILED.value
    if EndpointStatus.PARTIAL in statuses:
        return DataQualityStatus.READY_WITH_GAPS.value
    if EndpointStatus.STALE in statuses:
        return DataQualityStatus.STALE.value
    if EndpointStatus.READY_WITH_GAPS in statuses:
        return DataQualityStatus.READY_WITH_GAPS.value
    if statuses and statuses <= {EndpointStatus.UNKNOWN}:
        return DataQualityStatus.FAILED.value
    if not statuses:
        return DataQualityStatus.READY.value
    return DataQualityStatus.READY.value
