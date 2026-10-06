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
    assert to_v1_state(DiffusionStateV2.NARROWING_FRAGILE) == "NARROWING"
    assert to_v1_state(DiffusionStateV2.STABLE) == "STABLE"
    assert to_v1_state(DiffusionStateV2.UNCONFIRMED) == "UNCONFIRMED"


def _pct(count: int, group_size: int) -> float:
    return 100.0 * count / group_size


def test_count_aware_path_matches_integer_oracle_on_audit_cases():
    # IDXIC Banks 2026-09-18: n=45, 16 -> 21. The true count change is
    # five and the firm floor is five; percentage subtraction previously
    # yielded an implied 4.999999999999998 and a FRAGILE misclassification.
    state = classify_diffusion_v2(
        breadth_current=_pct(21, 45),
        breadth_previous=_pct(16, 45),
        group_size=45,
        breadth_change_count=5,
    )
    assert state == DiffusionStateV2.BROADENING_FIRM
    reverse = classify_diffusion_v2(
        breadth_current=_pct(16, 45),
        breadth_previous=_pct(21, 45),
        group_size=45,
        breadth_change_count=-5,
    )
    assert reverse == DiffusionStateV2.NARROWING_FIRM
    # n=19, 9 -> 11: d=2 clears the pp gate (20 >= 19) and the floor (2).
    assert classify_diffusion_v2(
        breadth_current=_pct(11, 19),
        breadth_previous=_pct(9, 19),
        group_size=19,
        breadth_change_count=2,
    ) == DiffusionStateV2.BROADENING_FIRM
    # n=62, 37 -> 30: d=-7 clears the narrowing gate (-70 <= -62) and
    # the floor of seven.
    assert classify_diffusion_v2(
        breadth_current=_pct(30, 62),
        breadth_previous=_pct(37, 62),
        group_size=62,
        breadth_change_count=-7,
    ) == DiffusionStateV2.NARROWING_FIRM


def test_exact_ten_pp_boundary_is_inclusive():
    # n=20, d=2 is exactly +10pp and meets the floor of two.
    assert classify_diffusion_v2(
        breadth_current=60.0, breadth_previous=50.0, group_size=20,
        breadth_change_count=2,
    ) == DiffusionStateV2.BROADENING_FIRM
    # n=20, d=-2 is exactly -10pp and meets the floor of two.
    assert classify_diffusion_v2(
        breadth_current=40.0, breadth_previous=60.0, group_size=20,
        breadth_change_count=-2,
    ) == DiffusionStateV2.NARROWING_FIRM
    # n=100, d=10 is exactly +10pp and meets the floor of ten.
    assert classify_diffusion_v2(
        breadth_current=60.0, breadth_previous=50.0, group_size=100,
        breadth_change_count=10,
    ) == DiffusionStateV2.BROADENING_FIRM
    # n=10, d=1 is exactly +10pp but below the floor of two.
    assert classify_diffusion_v2(
        breadth_current=60.0, breadth_previous=50.0, group_size=10,
        breadth_change_count=1,
    ) == DiffusionStateV2.BROADENING_FRAGILE


def test_one_name_move_clears_pp_gate_but_stays_fragile():
    # n=5, d=1 is +20pp (gate cleared) but below the floor of two.
    assert classify_diffusion_v2(
        breadth_current=80.0, breadth_previous=60.0, group_size=5,
        breadth_change_count=1,
    ) == DiffusionStateV2.BROADENING_FRAGILE


def test_move_genuinely_below_pp_gate_is_stable():
    # n=45, d=4 is +8.9pp: below the gate, so STABLE even though the
    # floor of five is also unmet.
    assert classify_diffusion_v2(
        breadth_current=_pct(20, 45),
        breadth_previous=_pct(16, 45),
        group_size=45,
        breadth_change_count=4,
    ) == DiffusionStateV2.STABLE


def test_float_path_bounded_tolerance_recovers_exact_count():
    # The Banks percentages without the count delta: the tolerance must
    # recover the exact implied count of five.
    state = classify_diffusion_v2(
        breadth_current=46.666666666666664,
        breadth_previous=35.55555555555555,
        group_size=45,
    )
    assert state == DiffusionStateV2.BROADENING_FIRM
    # A genuinely sub-threshold move must not be promoted by the
    # tolerance: n=45, d=4 stays STABLE via the float path.
    assert classify_diffusion_v2(
        breadth_current=_pct(20, 45),
        breadth_previous=_pct(16, 45),
        group_size=45,
    ) == DiffusionStateV2.STABLE
    # n=10, d=1 via the float path stays FRAGILE.
    assert classify_diffusion_v2(
        breadth_current=60.0, breadth_previous=50.0, group_size=10,
    ) == DiffusionStateV2.BROADENING_FRAGILE


def test_count_aware_path_still_requires_prior_and_eligibility():
    assert classify_diffusion_v2(
        breadth_current=80.0, breadth_previous=None, group_size=45,
        breadth_change_count=None,
    ) == DiffusionStateV2.UNCONFIRMED
    assert classify_diffusion_v2(
        breadth_current=80.0, breadth_previous=50.0, group_size=4,
        eligible=False, breadth_change_count=2,
    ) == DiffusionStateV2.UNCONFIRMED


def test_constituent_floor_is_exact_for_decimal_fractions():
    assert constituent_floor(30) == 3
    assert constituent_floor(45) == 5
    assert constituent_floor(250) == 25
    assert constituent_floor(4, fraction=0.20, minimum=1) == 1
