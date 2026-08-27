"""Pytest configuration and shared fixtures."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from idx_leadership.providers.fixture import FixtureProvider  # noqa: E402


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    return ROOT / "tests" / "fixtures"


@pytest.fixture(scope="session")
def fixture_provider(fixtures_dir: Path) -> FixtureProvider:
    return FixtureProvider(fixtures_dir=fixtures_dir)


@pytest.fixture()
def prices_df(fixtures_dir: Path) -> pd.DataFrame:
    df = pd.read_csv(fixtures_dir / "prices.csv")
    df["date"] = pd.to_datetime(df["date"]).dt.date
    return df


@pytest.fixture()
def benchmark_df(fixtures_dir: Path) -> pd.DataFrame:
    df = pd.read_csv(fixtures_dir / "benchmark.csv")
    df["date"] = pd.to_datetime(df["date"]).dt.date
    df["benchmark_id"] = "IHSG"
    df["price_basis"] = "close"
    df["source"] = "fixture"
    return df


@pytest.fixture()
def taxonomy_df(fixtures_dir: Path) -> pd.DataFrame:
    return pd.read_csv(fixtures_dir / "taxonomy.csv")
