"""Fixture-based provider used by tests and offline runs."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from ..models import ProviderMode, ProviderName, SecurityMasterEntry
from ..utils import project_root
from .base import MarketDataProvider
from .capabilities import (
    BenchmarkProvider,
    PriceCrossSectionProvider,
    PriceHistoryProvider,
    SecurityMasterProvider,
    TaxonomyProvider,
)
from .ledger import RequestLedger


class FixtureProvider(
    MarketDataProvider,
    SecurityMasterProvider,
    PriceHistoryProvider,
    PriceCrossSectionProvider,
    BenchmarkProvider,
    TaxonomyProvider,
):
    """Read-only provider that returns canned data for tests and offline runs."""

    name = "fixture"
    mode = ProviderMode.DEMO_FIXTURE

    def __init__(
        self,
        fixtures_dir: str | Path,
        *,
        ledger: RequestLedger | None = None,
        mode: ProviderMode = ProviderMode.DEMO_FIXTURE,
    ) -> None:
        super().__init__(ledger=ledger)
        if mode is not ProviderMode.DEMO_FIXTURE:
            raise ValueError("FixtureProvider only supports DEMO_FIXTURE mode")
        self.mode = mode
        self.fixtures_dir = Path(fixtures_dir)
        if not self.fixtures_dir.is_absolute():
            self.fixtures_dir = project_root() / self.fixtures_dir
        self._master: list[SecurityMasterEntry] | None = None
        self._taxonomy: pd.DataFrame | None = None

    def _load_master(self) -> list[SecurityMasterEntry]:
        if self._master is not None:
            return self._master
        path = self.fixtures_dir / "security_master.json"
        rows = json.loads(path.read_text(encoding="utf-8"))
        out = [SecurityMasterEntry(**r) for r in rows]
        self._master = out
        return out

    def _load_taxonomy(self) -> pd.DataFrame:
        if self._taxonomy is not None:
            return self._taxonomy
        path = self.fixtures_dir / "taxonomy.csv"
        self._taxonomy = pd.read_csv(path)
        return self._taxonomy

    def get_security_master(self) -> list[SecurityMasterEntry]:
        return list(self._load_master())

    def get_price_history(self, tickers: list[str], *, start: date, end: date) -> pd.DataFrame:
        path = self.fixtures_dir / "prices.parquet"
        if path.exists():
            df = pd.read_parquet(path)
        else:
            df = pd.read_csv(self.fixtures_dir / "prices.csv")
        df["date"] = pd.to_datetime(df["date"]).dt.date
        df = df[(df["date"] >= start) & (df["date"] <= end)]
        if tickers:
            df = df[df["ticker"].isin(tickers)]
        return df.reset_index(drop=True)

    def get_full_universe_close(self, as_of: date) -> pd.DataFrame:
        df = self.get_price_history(tickers=[], start=as_of, end=as_of)
        return df

    def get_benchmark_history(self, benchmark_id: str, *, start: date, end: date) -> pd.DataFrame:
        path = self.fixtures_dir / "benchmark.csv"
        df = pd.read_csv(path)
        df["date"] = pd.to_datetime(df["date"]).dt.date
        df = df[(df["date"] >= start) & (df["date"] <= end)]
        df["benchmark_id"] = benchmark_id
        df["price_basis"] = "close"
        df["source"] = ProviderName.FIXTURE.value
        return df[["benchmark_id", "date", "close", "price_basis", "source"]].reset_index(drop=True)

    def get_group_taxonomy(self) -> pd.DataFrame:
        return self._load_taxonomy().copy()
