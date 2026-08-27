"""Tests for the capability-oriented provider interfaces."""
from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from idx_leadership.providers.capabilities import (
    BenchmarkProvider,
    CapabilityNotSupported,
    CapabilitySet,
    EventProvider,
    FlowProvider,
    FreeFloatProvider,
    PriceCrossSectionProvider,
    PriceHistoryProvider,
    SecurityMasterProvider,
    TaxonomyProvider,
)
from idx_leadership.providers.fixture import FixtureProvider
from idx_leadership.providers.public import YFinanceProvider
from idx_leadership.providers.sectors import SectorsProvider


def test_yfinance_satisfies_core_capabilities():
    p = YFinanceProvider()
    caps = CapabilitySet(p).summary()
    assert caps["security_master"]
    assert caps["price_history"]
    assert caps["benchmark"]
    assert caps["taxonomy"]


def test_fixture_satisfies_core_capabilities():
    p = FixtureProvider(fixtures_dir="tests/fixtures")
    caps = CapabilitySet(p).summary()
    assert caps["security_master"]
    assert caps["price_history"]
    assert caps["benchmark"]
    assert caps["taxonomy"]


def test_sectors_satisfies_all_except_fundamental():
    p = SectorsProvider(api_key="")
    caps = CapabilitySet(p).summary()
    assert caps["security_master"]
    assert caps["price_history"]
    assert caps["price_cross_section"]
    assert caps["benchmark"]
    assert caps["taxonomy"]
    assert caps["free_float"]
    assert caps["flow"]
    assert caps["event"]
    assert caps["fundamental"] is False


def test_capability_set_summary_keys():
    p = SectorsProvider(api_key="")
    summary = CapabilitySet(p).summary()
    assert set(summary.keys()) == {
        "security_master",
        "price_history",
        "price_cross_section",
        "benchmark",
        "taxonomy",
        "free_float",
        "flow",
        "fundamental",
        "event",
    }


def test_capability_not_supported_is_not_implemented_error():
    assert issubclass(CapabilityNotSupported, NotImplementedError)


def test_yfinance_does_not_implement_free_float():
    p = YFinanceProvider()
    assert not isinstance(p, FreeFloatProvider)


def test_yfinance_does_not_implement_flow():
    p = YFinanceProvider()
    assert not isinstance(p, FlowProvider)


def test_fixture_does_not_implement_event():
    p = FixtureProvider(fixtures_dir="tests/fixtures")
    assert not isinstance(p, EventProvider)


def test_sectors_implements_price_cross_section():
    p = SectorsProvider(api_key="")
    assert isinstance(p, PriceCrossSectionProvider)
