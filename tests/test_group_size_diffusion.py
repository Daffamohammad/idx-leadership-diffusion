"""Tests for the group-size diffusion sensitivity harness."""
from __future__ import annotations

from idx_leadership.signals.diffusion_v2 import (
    DiffusionStateV2,
    classify_diffusion_v2,
    constituent_floor,
)

from scripts.audit_group_size_diffusion import GROUP_SIZES, diffusion_grid


def test_group_size_floor_scales_with_size_and_minimum():
    assert constituent_floor(3) == 2
    assert constituent_floor(5) == 2
    assert constituent_floor(7) == 2
    assert constituent_floor(10) == 2
    assert constituent_floor(20) == 2
    assert constituent_floor(40) == 4


def test_classify_diffusion_v2_threshold_changes_only_at_floor():
    # 10-name group, floor 2: a +12pp move implies 1.2 names → FRAGILE.
    state = classify_diffusion_v2(
        breadth_current=62.0, breadth_previous=50.0, group_size=10
    )
    assert state == DiffusionStateV2.BROADENING_FRAGILE
    # +20pp implies 2 names → FIRM.
    state = classify_diffusion_v2(
        breadth_current=70.0, breadth_previous=50.0, group_size=10
    )
    assert state == DiffusionStateV2.BROADENING_FIRM
    # 40-name group, floor 4: a +20pp move implies 8 names → FIRM.
    state = classify_diffusion_v2(
        breadth_current=70.0, breadth_previous=50.0, group_size=40
    )
    assert state == DiffusionStateV2.BROADENING_FIRM
    # +5pp implies 2 names, below floor → STABLE.
    state = classify_diffusion_v2(
        breadth_current=55.0, breadth_previous=50.0, group_size=40
    )
    assert state == DiffusionStateV2.STABLE


def test_diffusion_grid_covers_all_group_sizes_and_deltas():
    grid = diffusion_grid()
    assert set(grid["group_sizes"]) == set(GROUP_SIZES)
    assert set(grid["deltas"]) == {-30.0, -20.0, -10.0, -5.0, 0.0, 5.0, 10.0, 20.0, 30.0}
    for group_size in grid["group_sizes"]:
        relevant = [r for r in grid["rows"] if r["group_size"] == group_size]
        assert len(relevant) == len(grid["deltas"])
        for row in relevant:
            assert {"group_size", "floor", "breadth_delta_pp", "state"} <= row.keys()


def test_ineligible_group_size_unconfirmed():
    state = classify_diffusion_v2(
        breadth_current=70.0, breadth_previous=50.0, group_size=0, eligible=False
    )
    assert state == DiffusionStateV2.UNCONFIRMED
    state = classify_diffusion_v2(
        breadth_current=None, breadth_previous=50.0, group_size=10
    )
    assert state == DiffusionStateV2.UNCONFIRMED
