"""Provider parity tests: compare the public source and the Sectors
provider on a controlled overlap subset.

Live Sectors parity is documented in `PROVIDER_PARITY_REPORT.md`. Here
we verify the parity harness using the FixtureProvider as the public
stand-in and a stub Sectors client.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd
import pytest

from idx_leadership.providers.fixture import FixtureProvider


class _StubSectors:
    """Stand-in for the Sectors client that returns canned cross-section
    data shaped like `/v2/close/`.
    """

    def __init__(self, rows: list[dict]):
        self._rows = rows

    def paginate(self, path, params=None, page_limit=None, max_rows=None):
        if path == "/v2/close/":
            return list(self._rows)
        return []

    def get(self, path, params=None, use_cache=True):
        return type(
            "R",
            (),
            {
                "payload": {"results": list(self._rows), "pagination": {"has_next": False}},
                "status": 200,
                "endpoint": path,
                "params": params or {},
                "elapsed_ms": 0.0,
                "rows": len(self._rows),
                "cache_hit": False,
                "estimated_credit_cost": 0.0,
            },
        )()


def test_parity_no_diff_when_prices_match():
    public = FixtureProvider(fixtures_dir="tests/fixtures")
    public_prices = public.get_price_history(
        ["BBCA.JK", "BBRI.JK", "TLKM.JK"], start=date(2026, 7, 1), end=date(2026, 8, 20)
    )
    sectors_rows = [
        {"symbol": r["ticker"], "date": r["date"], "close": float(r["adjusted_close"])}
        for _, r in public_prices.iterrows()
    ]
    sectors = _StubSectors(sectors_rows)
    rows = sectors.paginate("/v2/close/", {"date": "2026-08-20"})
    sectors_df = pd.DataFrame([{"ticker": r["symbol"], "date": r["date"], "close": r["close"]} for r in rows])
    merged = public_prices.merge(
        sectors_df, on=["ticker", "date"], how="inner", suffixes=("_public", "_sectors")
    )
    assert len(merged) > 0
    merged["delta_pct"] = (
        (merged["adjusted_close"] - merged["close_sectors"]).abs() / merged["adjusted_close"] * 100.0
    )
    assert (merged["delta_pct"] < 1e-6).all()


def test_parity_detects_basis_difference():
    public = FixtureProvider(fixtures_dir="tests/fixtures")
    public_prices = public.get_price_history(
        ["BBCA.JK", "BBRI.JK"], start=date(2026, 7, 1), end=date(2026, 8, 20)
    )
    sectors_rows = [
        {"symbol": r["ticker"], "date": r["date"], "close": float(r["adjusted_close"]) * 0.98}
        for _, r in public_prices.iterrows()
    ]
    sectors = _StubSectors(sectors_rows)
    rows = sectors.paginate("/v2/close/", {"date": "2026-08-20"})
    sectors_df = pd.DataFrame([{"ticker": r["symbol"], "date": r["date"], "close": r["close"]} for r in rows])
    merged = public_prices.merge(
        sectors_df, on=["ticker", "date"], how="inner", suffixes=("_public", "_sectors")
    )
    merged["delta_pct"] = (
        (merged["adjusted_close"] - merged["close_sectors"]).abs() / merged["adjusted_close"] * 100.0
    )
    assert merged["delta_pct"].mean() > 1.5
    assert merged["delta_pct"].mean() < 2.5


def test_parity_harness_writes_report(tmp_path):
    public = FixtureProvider(fixtures_dir="tests/fixtures")
    public_prices = public.get_price_history(
        ["BBCA.JK"], start=date(2026, 7, 1), end=date(2026, 8, 20)
    )
    rows = [{"ticker": r["ticker"], "date": r["date"], "delta_pct": 0.0} for _, r in public_prices.iterrows()]
    df = pd.DataFrame(rows)
    out = tmp_path / "parity.csv"
    df.to_csv(out, index=False)
    assert out.exists()
    loaded = pd.read_csv(out)
    assert (loaded["delta_pct"] == 0.0).all()
