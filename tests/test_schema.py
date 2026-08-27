"""Tests for canonical schemas (Pydantic models)."""
from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from idx_leadership.models import (
    BenchmarkObservation,
    GroupSnapshot,
    PriceObservation,
    SecurityFeatureSnapshot,
    SecurityMasterEntry,
    TransitionEvent,
    ConcentrationMetrics,
    LeadershipState,
    DiffusionState,
    MaterialityLabel,
    ProviderName,
)


def test_security_master_minimal():
    s = SecurityMasterEntry(ticker="A", vendor_ticker="A", source=ProviderName.YFINANCE)
    assert s.ticker == "A"
    assert s.country == "ID"
    assert s.active is True


def test_security_master_missing_ticker_fails():
    with pytest.raises(ValidationError):
        SecurityMasterEntry(vendor_ticker="A", source=ProviderName.YFINANCE)  # type: ignore[call-arg]


def test_price_observation_validates_positive_prices():
    with pytest.raises(ValidationError):
        PriceObservation(
            ticker="A",
            date=date(2026, 1, 1),
            close=0.0,
            adjusted_close=100.0,
            source=ProviderName.YFINANCE,
        )
    with pytest.raises(ValidationError):
        PriceObservation(
            ticker="A",
            date=date(2026, 1, 1),
            close=100.0,
            adjusted_close=-1.0,
            source=ProviderName.YFINANCE,
        )


def test_benchmark_observation_requires_positive_close():
    with pytest.raises(ValidationError):
        BenchmarkObservation(benchmark_id="IHSG", date=date(2026, 1, 1), close=0.0, source=ProviderName.YFINANCE)


def test_security_feature_snapshot_defaults():
    s = SecurityFeatureSnapshot(snapshot_date=date(2026, 1, 1), ticker="A")
    assert s.feature_version == "features-v1"
    assert s.excess_return_20d is None


def test_group_snapshot_concentration_defaults():
    g = GroupSnapshot(
        snapshot_date=date(2026, 1, 1),
        group_id="X",
    )
    assert g.concentration.convention == "absolute_move"
    assert g.leadership_state == LeadershipState.UNCONFIRMED
    assert g.diffusion_state == DiffusionState.UNCONFIRMED


def test_transition_event_defaults():
    t = TransitionEvent(current_date=date(2026, 1, 1), group_id="X")
    assert t.materiality_label == MaterialityLabel.STABLE
    assert t.transition_version == "transitions-v2"


def test_group_snapshot_extra_ignored_for_helper_fields():
    # GroupSnapshot allows extra fields so internal helpers like
    # relative_strength_level can be attached without breaking serialization.
    s = GroupSnapshot(
        snapshot_date=date(2026, 1, 1),
        group_id="X",
        relative_strength_level=1.5,
    )
    assert s.relative_strength_level == 1.5
