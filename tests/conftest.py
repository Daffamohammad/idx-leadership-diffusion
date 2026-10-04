"""Pytest configuration and shared fixtures."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from idx_leadership.providers.fixture import FixtureProvider  # noqa: E402

_BASELINE_KEY = "idx_baseline_git_status"


def git_status(repo: Path) -> str | None:
    """Porcelain status of ``repo``, or None when it cannot be determined.

    Returns None (rather than a value to compare against) when git is
    unavailable or the directory is not a work tree, so the guard stays
    silent outside a checkout instead of failing on an unknown baseline.
    """
    try:
        proc = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(repo),
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout


def tree_drift(before: str | None, after: str | None) -> list[str]:
    """Paths whose git status differs between two ``git status`` snapshots.

    Only *changes in status* are reported, so a working tree that was
    already dirty before the run is tolerated: a pre-existing modified file
    that the suite leaves alone stays identical in both snapshots. A file
    that appears, disappears, or changes state during the run is drift.
    """
    if before is None or after is None:
        return []
    # Index by path so a status change (clean -> modified, or
    # untracked -> tracked) is detected even when the path is in both.
    # Filenames are compared exactly: normalising them (for example by
    # stripping R/C because they appear in some status codes) would hide
    # drift such as renaming ``notesR.txt`` to ``notes.txt``.
    before_map = {
        line[3:]: line[:2]
        for line in before.splitlines()
        if len(line) > 3
    }
    after_map = {
        line[3:]: line[:2]
        for line in after.splitlines()
        if len(line) > 3
    }
    drifted = set(before_map) ^ set(after_map)
    drifted |= {p for p in before_map.keys() & after_map if before_map[p] != after_map[p]}
    return sorted(drifted)


@pytest.hookimpl(trylast=True)
def pytest_sessionstart(session: pytest.Session) -> None:
    session.config.stash.setdefault(_BASELINE_KEY, git_status(ROOT))


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Fail the run if the test suite mutated the working tree.

    A test that writes into the repository (a tracked file, or an untracked
    path git would surface) leaves the tree dirty. That is exactly the class
    of defect this guard exists to catch: a test must not be able to
    overwrite committed evidence or leave state behind for the next run.
    """
    before = session.config.stash.get(_BASELINE_KEY, None)
    drift = tree_drift(before, git_status(ROOT))
    if not drift:
        return
    print("\n" + "=" * 72)
    print("FAIL: the test suite mutated the working tree")
    for path in drift:
        print(f"  {path}")
    print("=" * 72)
    session.exitstatus = 1


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
