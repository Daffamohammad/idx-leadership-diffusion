"""Tests for the group-size-aware diffusion rule (v2)."""
from __future__ import annotations

import pytest

from idx_leadership.signals.diffusion_v2 import (
    DiffusionStateV2,
    classify_diffusion_v2,
    constituent_floor,
    to_v1_state,
)


def test_constituent_floor_minimum_default():
    assert constituent_floor(5) == 2
    assert constituent_floor(15) == 2  # 10% of 15 = 1.5 -> ceil 2
    assert constituent_floor(20) == 2  # 10% = 2
    assert constituent_floor(25) == 3  # 10% = 2.5 -> ceil 3
    assert constituent_floor(100) == 10


def test_constituent_floor_explicit_params():
    assert constituent_floor(10, fraction=0.20, minimum=1) == 2
    assert constituent_floor(4, fraction=0.20, minimum=1) == 1


def test_small_group_firm_requires_count_change():
    # 5-stock group, +10pp = 0.5 implied constituents; floor = 2.
    state = classify_diffusion_v2(
        breadth_current=70.0, breadth_previous=60.0, group_size=5
    )
    assert state == DiffusionStateV2.BROADENING_FRAGILE


def test_small_group_does_not_flip_to_firm_too_easily():
    # 5-stock group, +20pp = 1.0 implied < floor 2.
    state = classify_diffusion_v2(
        breadth_current=80.0, breadth_previous=60.0, group_size=5
    )
    assert state == DiffusionStateV2.BROADENING_FRAGILE


def test_large_group_firm_quickly():
    # 50-stock group, +10pp = 5.0 implied > floor 5.
    state = classify_diffusion_v2(
        breadth_current=60.0, breadth_previous=50.0, group_size=50
    )
    assert state == DiffusionStateV2.BROADENING_FIRM


def test_stable_classification():
    state = classify_diffusion_v2(
        breadth_current=55.0, breadth_previous=50.0, group_size=20
    )
    assert state == DiffusionStateV2.STABLE


def test_narrowing_firm():
    state = classify_diffusion_v2(
        breadth_current=30.0, breadth_previous=50.0, group_size=20
    )
    assert state == DiffusionStateV2.NARROWING_FIRM


def test_narrowing_fragile_small_group():
    state = classify_diffusion_v2(
        breadth_current=40.0, breadth_previous=50.0, group_size=4
    )
    assert state == DiffusionStateV2.NARROWING_FRAGILE


def test_unconfirmed_when_ineligible():
    state = classify_diffusion_v2(
        breadth_current=80.0, breadth_previous=50.0, group_size=20, eligible=False
    )
    assert state == DiffusionStateV2.UNCONFIRMED


def test_unconfirmed_when_input_missing():
    state = classify_diffusion_v2(
        breadth_current=None, breadth_previous=50.0, group_size=20
    )
    assert state == DiffusionStateV2.UNCONFIRMED


def test_to_v1_state_collapse():
    assert to_v1_state(DiffusionStateV2.BROADENING_FIRM) == "BROADENING"
    assert to_v1_state(DiffusionStateV2.BROADENING_FRAGILE) == "BROADENING"
    assert to_v1_state(DiffusionStateV2.NARROWING_FIRM) == "NARROWING"
    assert to_v1_state(DiffusionStateV2.STABLE) == "STABLE"
    assert to_v1_state(DiffusionStateV2.UNCONFIRMED) == "UNCONFIRMED"
