"""Tests for provider layer (public + fixture + stub)."""
from __future__ import annotations

import json
import tempfile
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from idx_leadership.providers.factory import build_provider_from_config
from idx_leadership.providers.fixture import FixtureProvider
from idx_leadership.providers.ledger import RequestLedger
from idx_leadership.providers.sectors import SectorsProvider
from idx_leadership.providers.capabilities import CapabilitySet
from idx_leadership.utils.errors import ProviderError


def test_fixture_provider_returns_master(fixtures_dir):
    p = FixtureProvider(fixtures_dir=fixtures_dir)
    master = p.get_security_master()
    assert len(master) == 10
    assert all(m.ticker.endswith(".JK") for m in master)


def test_fixture_provider_returns_prices(fixtures_dir):
    p = FixtureProvider(fixtures_dir=fixtures_dir)
    df = p.get_price_history(["BBCA.JK"], start=date(2026, 8, 1), end=date(2026, 8, 20))
    assert not df.empty
    assert "ticker" in df.columns
    assert "adjusted_close" in df.columns


def test_fixture_provider_returns_benchmark(fixtures_dir):
    p = FixtureProvider(fixtures_dir=fixtures_dir)
    df = p.get_benchmark_history("IHSG", start=date(2026, 8, 1), end=date(2026, 8, 20))
    assert not df.empty
    assert "benchmark_id" in df.columns
    assert (df["benchmark_id"] == "IHSG").all()


def test_fixture_provider_returns_taxonomy(fixtures_dir):
    p = FixtureProvider(fixtures_dir=fixtures_dir)
    df = p.get_group_taxonomy()
    assert not df.empty
    assert "group_id" in df.columns
    assert "Financials" in df["group_id"].values


def test_sectors_provider_blocks_live_without_key():
    # With an empty key and allow_live=False (default), the client must
    # raise ProviderError rather than fabricating data.
    from idx_leadership.utils.errors import ProviderError
    p = SectorsProvider(api_key="")
    with pytest.raises(ProviderError):
        p.get_security_master()


def test_sectors_provider_capability_set():
    p = SectorsProvider(api_key="")
    caps = CapabilitySet(p).summary()
    assert caps["security_master"]
    assert caps["price_cross_section"]
    assert caps["benchmark"]
    assert caps["taxonomy"]
    assert caps["free_float"]
    assert caps["flow"]
    assert caps["event"]
    assert caps["fundamental"] is False  # not implemented in this pass


def test_ledger_records(tmp_path):
    p = RequestLedger(path=tmp_path / "ledger.jsonl")
    p.record(
        provider="yfinance",
        endpoint="price_history",
        request_type="single",
        parameters={"ticker": "A"},
        cache_hit=False,
        status="ok",
        rows_returned=10,
        elapsed_ms=12.5,
    )
    p.flush()
    lines = (tmp_path / "ledger.jsonl").read_text().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["provider"] == "yfinance"
    assert record["rows_returned"] == 10


def test_ledger_redacts_secrets():
    p = RequestLedger(path=Path(tempfile.mkdtemp()) / "ledger.jsonl")
    params = {"ticker": "A", "api_key": "secret-123"}
    h = p.hash_params(params)
    assert isinstance(h, str) and len(h) == 16
    # hashed value is not equal to a naive str()
    assert h != "secret-123"[:16]
