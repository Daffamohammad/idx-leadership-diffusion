"""Data quality diagnostics.

Returns explicit `DataQualityStatus` codes; never silently fixes severe
structural problems.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

import pandas as pd

from ..models import DataQualityStatus
from ..utils import get_logger
from ..utils.dates import asof_resolve

_log = get_logger(__name__)


@dataclass
class QualityReport:
    status: DataQualityStatus
    issues: list[str] = field(default_factory=list)
    coverage_pct: float = 0.0
    requested_securities: int = 0
    loaded_securities: int = 0
    usable_securities: int = 0
    failed_securities: int = 0
    benchmark_latest_date: date | None = None
    latest_common_date: date | None = None
    duplicate_ticker_date_rows: int = 0
    invalid_prices: int = 0
    stale: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "issues": list(self.issues),
            "coverage_pct": self.coverage_pct,
            "requested_securities": self.requested_securities,
            "loaded_securities": self.loaded_securities,
            "usable_securities": self.usable_securities,
            "failed_securities": self.failed_securities,
            "benchmark_latest_date": self.benchmark_latest_date.isoformat() if self.benchmark_latest_date else None,
            "latest_common_date": self.latest_common_date.isoformat() if self.latest_common_date else None,
            "duplicate_ticker_date_rows": self.duplicate_ticker_date_rows,
            "invalid_prices": self.invalid_prices,
            "stale": self.stale,
        }


def assess_quality(
    *,
    requested_tickers: list[str],
    prices: pd.DataFrame,
    benchmark: pd.DataFrame,
    today: date,
    stale_days: int = 14,
    min_history_days: int = 60,
) -> QualityReport:
    issues: list[str] = []
    if not requested_tickers:
        return QualityReport(status=DataQualityStatus.FAILED, issues=["no requested tickers"])
    requested = set(requested_tickers)
    loaded = set(prices["ticker"].unique()) if "ticker" in prices.columns else set()

    failed = sorted(requested - loaded)
    if failed:
        issues.append(f"failed_securities={failed}")

    # Duplicate rows
    dupes = 0
    if {"ticker", "date"}.issubset(prices.columns):
        dupes = int(prices.duplicated(subset=["ticker", "date"]).sum())
        if dupes:
            issues.append(f"duplicate_rows={dupes}")

    # Invalid prices
    invalid = 0
    if {"adjusted_close", "close"}.issubset(prices.columns):
        invalid = int(((prices["adjusted_close"] <= 0) | (prices["close"] <= 0)).sum())
        if invalid:
            issues.append(f"invalid_prices={invalid}")

    # Coverage
    loaded_count = len(loaded)
    coverage_pct = (loaded_count / max(1, len(requested))) * 100.0

    # Benchmark present?
    if benchmark.empty:
        issues.append("missing_benchmark")
    bench_latest = benchmark["date"].max() if not benchmark.empty and "date" in benchmark.columns else None
    if isinstance(bench_latest, pd.Timestamp):
        bench_latest = bench_latest.date()
    if not bench_latest:
        issues.append("benchmark_empty")

    # Stale check
    stale = False
    if bench_latest and (today - bench_latest) > timedelta(days=stale_days):
        stale = True
        issues.append(f"benchmark_stale={bench_latest}")

    # Latest common date (max date where all loaded tickers have data)
    latest_common: date | None = None
    if not prices.empty and "ticker" in prices.columns and "date" in prices.columns:
        counts = prices.groupby("date")["ticker"].nunique()
        if not counts.empty:
            best = counts.idxmax()
            if counts.max() >= max(1, int(0.9 * len(loaded))):
                latest_common = best.date() if isinstance(best, pd.Timestamp) else best
            else:
                issues.append("no_common_date_with_90pct_coverage")

    # Determine status
    if failed and len(failed) == len(requested):
        status = DataQualityStatus.FAILED
    elif stale:
        status = DataQualityStatus.STALE
    elif failed or dupes or invalid or (bench_latest is None):
        status = DataQualityStatus.READY_WITH_GAPS
    else:
        status = DataQualityStatus.READY

    return QualityReport(
        status=status,
        issues=issues,
        coverage_pct=round(coverage_pct, 2),
        requested_securities=len(requested),
        loaded_securities=loaded_count,
        usable_securities=loaded_count,
        failed_securities=len(failed),
        benchmark_latest_date=bench_latest,
        latest_common_date=latest_common,
        duplicate_ticker_date_rows=dupes,
        invalid_prices=invalid,
        stale=stale,
    )
