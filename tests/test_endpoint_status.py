"""Tests for the per-endpoint data-quality status model."""
from __future__ import annotations

from datetime import date

import pytest

from idx_leadership.data.endpoint_status import (
    EndpointQuality,
    EndpointStatus,
    assess_endpoint_quality,
    rollup_status,
)


def test_assess_zero_rows_is_failed():
    eq = assess_endpoint_quality("close", rows=0, expected_rows=900)
    assert eq.status == EndpointStatus.FAILED
    assert "no_rows" in eq.reasons


def test_assess_partial_when_below_half():
    eq = assess_endpoint_quality("close", rows=400, expected_rows=900)
    assert eq.status == EndpointStatus.PARTIAL


def test_assess_ready_with_gaps():
    eq = assess_endpoint_quality("close", rows=850, expected_rows=900)
    assert eq.status == EndpointStatus.READY_WITH_GAPS


def test_assess_ready():
    eq = assess_endpoint_quality("close", rows=900, expected_rows=900)
    assert eq.status == EndpointStatus.READY


def test_assess_errors_force_partial_or_failed():
    eq = assess_endpoint_quality("close", rows=0, expected_rows=900, errors=["network"])
    assert eq.status == EndpointStatus.FAILED
    eq2 = assess_endpoint_quality("close", rows=400, expected_rows=900, errors=["network"])
    assert eq2.status == EndpointStatus.PARTIAL


def test_rollup_failed_wins():
    statuses = [EndpointStatus.READY, EndpointStatus.FAILED, EndpointStatus.READY_WITH_GAPS]
    eqs = [EndpointQuality(name="a", status=s) for s in statuses]
    assert rollup_status(eqs) == "FAILED"


def test_rollup_partial_maps_to_ready_with_gaps():
    eqs = [EndpointQuality(name="a", status=EndpointStatus.READY), EndpointQuality(name="b", status=EndpointStatus.PARTIAL)]
    assert rollup_status(eqs) == "READY_WITH_GAPS"


def test_rollup_all_ready():
    eqs = [EndpointQuality(name="a", status=EndpointStatus.READY), EndpointQuality(name="b", status=EndpointStatus.READY)]
    assert rollup_status(eqs) == "READY"


def test_rollup_empty():
    assert rollup_status([]) == "READY"


def test_rollup_only_unknown_is_failed():
    eqs = [EndpointQuality(name="a", status=EndpointStatus.UNKNOWN)]
    assert rollup_status(eqs) == "FAILED"
