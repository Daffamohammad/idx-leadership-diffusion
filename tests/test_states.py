"""Tests for leadership and diffusion state classification."""
from __future__ import annotations

import pytest

from idx_leadership.models import DiffusionState, LeadershipState
from idx_leadership.signals.diffusion import classify_diffusion
from idx_leadership.signals.leadership import classify_leadership


# --- diffusion ---

def test_diffusion_broadening_above_threshold():
    assert classify_diffusion(breadth_delta_pp=12.0, broadening_threshold_pp=10.0) == DiffusionState.BROADENING


def test_diffusion_narrowing_below_threshold():
    assert classify_diffusion(breadth_delta_pp=-15.0, narrowing_threshold_pp=-10.0) == DiffusionState.NARROWING


def test_diffusion_stable_within_band():
    assert classify_diffusion(breadth_delta_pp=5.0, broadening_threshold_pp=10.0, narrowing_threshold_pp=-10.0) == DiffusionState.STABLE


def test_diffusion_unconfirmed_when_ineligible():
    assert classify_diffusion(breadth_delta_pp=50.0, eligible=False) == DiffusionState.UNCONFIRMED


def test_diffusion_unconfirmed_when_missing():
    assert classify_diffusion(breadth_delta_pp=None) == DiffusionState.UNCONFIRMED


def test_diffusion_boundary_broadening_inclusive():
    assert classify_diffusion(breadth_delta_pp=10.0, broadening_threshold_pp=10.0) == DiffusionState.BROADENING


def test_diffusion_boundary_narrowing_inclusive():
    assert classify_diffusion(breadth_delta_pp=-10.0, narrowing_threshold_pp=-10.0) == DiffusionState.NARROWING


# --- leadership ---

def test_leadership_leading():
    s = classify_leadership(
        excess_return_20d=2.0,
        excess_return_5d=3.0,
        excess_return_60d=1.0,
        acceleration_threshold_pp=1.0,
    )
    assert s == LeadershipState.LEADING


def test_leadership_improving():
    s = classify_leadership(
        excess_return_20d=-1.0,
        excess_return_5d=1.0,
        excess_return_60d=-2.0,
        acceleration_threshold_pp=1.0,
    )
    assert s == LeadershipState.IMPROVING


def test_leadership_lagging():
    s = classify_leadership(
        excess_return_20d=-2.0,
        excess_return_5d=-3.0,
        excess_return_60d=-1.0,
        acceleration_threshold_pp=1.0,
    )
    assert s == LeadershipState.LAGGING


def test_leadership_weakening():
    s = classify_leadership(
        excess_return_20d=2.0,
        excess_return_5d=-1.0,
        excess_return_60d=2.0,
        acceleration_threshold_pp=1.0,
    )
    assert s == LeadershipState.WEAKENING


def test_leadership_unconfirmed_missing():
    s = classify_leadership(
        excess_return_20d=None,
        excess_return_5d=1.0,
        excess_return_60d=0.0,
    )
    assert s == LeadershipState.UNCONFIRMED


def test_leadership_unconfirmed_ineligible():
    s = classify_leadership(
        excess_return_20d=5.0,
        excess_return_5d=5.0,
        excess_return_60d=0.0,
        eligible=False,
    )
    assert s == LeadershipState.UNCONFIRMED


def test_leadership_threshold_boundary():
    # acceleration exactly 1.0 -> improving threshold inclusive
    s = classify_leadership(
        excess_return_20d=-1.0,
        excess_return_5d=0.0,
        excess_return_60d=-1.0,
        acceleration_threshold_pp=1.0,
    )
    assert s == LeadershipState.IMPROVING
