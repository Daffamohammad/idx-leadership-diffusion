"""Tests for the market-wide universe eligibility filter."""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd
import pytest

from idx_leadership.providers.market_universe import (
    EligibilityConfig,
    build_market_universe,
    eligibility_summary,
)
from idx_leadership.models import SecurityMasterEntry


class _StubProvider:
    """Stub that mimics SectorsProvider capabilities for the eligibility
    filter. Returns canned cross-sections and suspensions."""

    def __init__(self, master, cross_sections, suspensions=None):
        self._master = master
        self._cs = cross_sections
        self._susp = suspensions if suspensions is not None else pd.DataFrame(
            columns=["ticker", "suspension_date", "reason", "pdf_url"]
        )

    def get_security_master(self):
        return self._master

    def get_full_universe_close(self, as_of):
        return self._cs.get(as_of, pd.DataFrame())

    def get_suspensions(self, *, start, end):
        return self._susp


def _entry(ticker, sector="Financials", sub_sector="Banks", industry="Banks",
           sub_industry="Banks", listing_board="Main"):
    return SecurityMasterEntry(
        ticker=ticker,
        vendor_ticker=ticker,
        company_name=ticker,
        exchange="IDX",
        country="ID",
        sector=sector,
        subsector=sub_sector,
        industry=industry,
        subindustry=sub_industry,
        group_id=sector,
        active=True,
        benchmark_flag=False,
        source="fixture",
        source_as_of=date(2026, 8, 20),
    )


def _build_full_history(ticker, as_of, n_days, base_price=100.0):
    import datetime as _dt
    rows = []
    for i in range(n_days):
        d = as_of - _dt.timedelta(days=i)
        rows.append({"ticker": ticker, "date": d, "close": base_price + i})
    return rows


def test_eligibility_basic():
    as_of = date(2026, 8, 20)
    master = [
        _entry("A.JK"),
        _entry("B.JK"),
        _entry("C.JK", sector=None, sub_sector=None),  # no taxonomy
    ]
    history_rows = []
    history_rows.extend(_build_full_history("A.JK", as_of, 60, 100))
    history_rows.extend(_build_full_history("B.JK", as_of, 60, 200))
    history_rows.extend(_build_full_history("C.JK", as_of, 1, 300))  # only 1 day
    cs = {as_of: pd.DataFrame(history_rows)}
    p = _StubProvider(master, cs)
    df = build_market_universe(
        security_master_provider=p,
        cross_section_provider=p,
        event_provider=p,
        as_of=as_of,
    )
    assert len(df) == 3
    eligible = df[df["ticker"].isin(["A.JK", "B.JK"])]
    assert bool(eligible["eligible"].all())
    c_row = df[df["ticker"] == "C.JK"].iloc[0]
    assert bool(c_row["eligible"]) is False
    assert c_row["exclusion_reason"] in {"no_taxonomy", "insufficient_history"}


def test_eligibility_summary_counts():
    master = [_entry(f"T{i}.JK") for i in range(5)]
    as_of = date(2026, 8, 20)
    p = _StubProvider(master, {as_of: pd.DataFrame()})
    df = build_market_universe(
        security_master_provider=p, cross_section_provider=p, event_provider=p, as_of=as_of
    )
    summary = eligibility_summary(df)
    assert summary["total"] == 5
    assert summary["eligible"] == 0
    # Either reason may appear; the important point is that the summary
    # accounting is non-empty.
    assert summary["by_reason"]


def test_suspension_excludes():
    as_of = date(2026, 8, 20)
    master = [_entry("A.JK"), _entry("B.JK")]
    history_rows = []
    history_rows.extend(_build_full_history("A.JK", as_of, 60, 100))
    history_rows.extend(_build_full_history("B.JK", as_of, 60, 200))
    cs = {as_of: pd.DataFrame(history_rows)}
    susp = pd.DataFrame({
        "ticker": ["A.JK"],
        "suspension_date": [as_of],
        "reason": ["x"],
        "pdf_url": ["x"],
    })
    p = _StubProvider(master, cs, suspensions=susp)
    df = build_market_universe(
        security_master_provider=p,
        cross_section_provider=p,
        event_provider=p,
        as_of=as_of,
    )
    a = df[df["ticker"] == "A.JK"].iloc[0]
    assert bool(a["eligible"]) is False
    assert a["exclusion_reason"] in {"recently_suspended", "insufficient_history"}


def test_default_config():
    cfg = EligibilityConfig()
    assert cfg.exclude_delisted is True
    assert cfg.exclude_suspended is True
    assert cfg.min_history_days == 60


def test_liquidity_and_staleness_are_explicit_exclusions():
    as_of = date(2026, 8, 20)
    master = [_entry("LIQ.JK"), _entry("STALE.JK"), _entry("ALT.JK")]
    master[-1] = master[-1].model_copy(update={"common_equity_status": "NON_COMMON_EQUITY"})
    rows = []
    rows.extend(
        {
            "ticker": "LIQ.JK",
            "date": as_of - pd.Timedelta(days=i),
            "close": 100.0,
            "volume": 10,
        }
        for i in range(60)
    )
    rows.extend(
        {
            "ticker": "STALE.JK",
            "date": as_of - pd.Timedelta(days=40 + i),
            "close": 100.0,
            "volume": 10_000_000,
        }
        for i in range(60)
    )
    rows.extend(
        {
            "ticker": "ALT.JK",
            "date": as_of - pd.Timedelta(days=i),
            "close": 100.0,
            "volume": 10_000_000,
        }
        for i in range(60)
    )
    p = _StubProvider(master, {})
    df = build_market_universe(
        security_master_provider=p,
        cross_section_provider=p,
        event_provider=None,
        as_of=as_of,
        config=EligibilityConfig(min_median_daily_value=100_000),
        price_history=pd.DataFrame(rows),
        security_master=master,
    )
    reasons = dict(zip(df["ticker"], df["exclusion_reason"]))
    assert reasons["LIQ.JK"] == "insufficient_liquidity"
    assert reasons["STALE.JK"] == "stale_price"
    assert reasons["ALT.JK"] == "non_common_equity"


class _FailingEventProvider(_StubProvider):
    def get_suspensions(self, *, start, end):
        raise RuntimeError("suspension feed down")


def test_failing_suspension_feed_degrades_explicitly():
    as_of = date(2026, 8, 20)
    master = [_entry("A.JK")]
    history = pd.DataFrame(_build_full_history("A.JK", as_of, 60, 100))
    p = _FailingEventProvider(master, {})
    df = build_market_universe(
        security_master_provider=p,
        cross_section_provider=p,
        event_provider=p,
        as_of=as_of,
        price_history=history,
        security_master=master,
    )
    assert bool(df.iloc[0]["eligible"]) is True
    assert df.attrs.get("suspension_check") == "failed"


def test_suspension_check_attr_present_without_event_provider():
    as_of = date(2026, 8, 20)
    master = [_entry("A.JK")]
    history = pd.DataFrame(_build_full_history("A.JK", as_of, 60, 100))
    p = _StubProvider(master, {})
    df = build_market_universe(
        security_master_provider=p,
        cross_section_provider=p,
        event_provider=None,
        as_of=as_of,
        price_history=history,
        security_master=master,
    )
    assert df.attrs.get("suspension_check") == "not_supported"
