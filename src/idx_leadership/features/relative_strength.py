"""Relative performance engine.

Combines per-security returns with benchmark returns to produce
excess returns. All operations are date-aligned and use the same
horizon definitions.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

import pandas as pd

from ..utils import get_logger
from ..utils.dates import asof_resolve
from .returns import compute_returns

_log = get_logger(__name__)


def compute_benchmark_returns(
    benchmark: pd.DataFrame,
    *,
    horizons: dict[str, int],
    price_col: str = "close",
    as_of: Optional[date] = None,
    tolerance_days: int = 7,
) -> pd.Series:
    """Return a Series indexed by horizon label with percent returns.

    For a single benchmark, returns one value per horizon.
    """
    if benchmark.empty:
        return pd.Series({f"return_{h}": None for h in horizons})
    df = benchmark.copy()
    df["date"] = pd.to_datetime(df["date"]).dt.date
    df = df.sort_values("date").drop_duplicates(subset="date", keep="last")
    if as_of is not None:
        chosen = asof_resolve(df["date"].tolist(), as_of, tolerance_days)
        if chosen is None:
            return pd.Series({f"return_{h}": None for h in horizons})
        df = df[df["date"] <= chosen]
    if df.empty:
        return pd.Series({f"return_{h}": None for h in horizons})
    df[price_col] = pd.to_numeric(df[price_col], errors="coerce")
    df = df.dropna(subset=[price_col])
    df = df[df[price_col] > 0]
    if df.empty:
        return pd.Series({f"return_{h}": None for h in horizons})
    out: dict[str, Optional[float]] = {}
    end_date = df["date"].iloc[-1]
    end_price = float(df[price_col].iloc[-1])
    for label, h in horizons.items():
        if len(df) <= h:
            out[f"return_{label}"] = None
            continue
        start_price = float(df[price_col].iloc[-(h + 1)])
        if start_price <= 0:
            out[f"return_{label}"] = None
            continue
        out[f"return_{label}"] = (end_price / start_price - 1.0) * 100.0
    out["as_of"] = end_date
    return pd.Series(out)


def align_security_to_benchmark(
    sec_returns: pd.DataFrame,
    bench_returns: pd.Series,
    *,
    horizons: list[str],
    as_of: Optional[date] = None,
) -> pd.DataFrame:
    """Add benchmark_return_h and excess_return_h columns to sec_returns."""
    if sec_returns.empty or bench_returns is None or bench_returns.empty:
        return sec_returns.assign(
            **{
                f"benchmark_return_{h}": None
                for h in horizons
            },
            **{
                f"excess_return_{h}": None
                for h in horizons
            },
        )
    rows: list[dict] = []
    for _, r in sec_returns.iterrows():
        new = dict(r)
        for h in horizons:
            br = bench_returns.get(f"return_{h}")
            sr = r.get(f"return_{h}")
            new[f"benchmark_return_{h}"] = br
            if sr is None or pd.isna(sr) or br is None or pd.isna(br):
                new[f"excess_return_{h}"] = None
            else:
                new[f"excess_return_{h}"] = float(sr) - float(br)
        rows.append(new)
    return pd.DataFrame(rows)


def compute_excess_returns(
    prices: pd.DataFrame,
    benchmark: pd.DataFrame,
    *,
    horizons: dict[str, int],
    as_of: Optional[date] = None,
    security_price_col: str = "adjusted_close",
    benchmark_price_col: str = "close",
    tolerance_days: int = 7,
) -> pd.DataFrame:
    """Combined: returns + excess returns per security at as_of."""
    horizon_labels = list(horizons.keys())
    sec_returns = compute_returns(
        prices,
        horizons=horizons,
        price_col=security_price_col,
        as_of=as_of,
        tolerance_days=tolerance_days,
    )
    bench = compute_benchmark_returns(
        benchmark,
        horizons=horizons,
        price_col=benchmark_price_col,
        as_of=as_of,
        tolerance_days=tolerance_days,
    )
    if sec_returns.empty:
        return sec_returns
    aligned = align_security_to_benchmark(sec_returns, bench, horizons=horizon_labels, as_of=as_of)
    # Relative strength level and change
    aligned["relative_strength_level"] = aligned.get("excess_return_20d")
    aligned["relative_strength_change"] = _safe_diff(
        aligned.get("excess_return_5d"), aligned.get("excess_return_60d")
    )
    return aligned


def compute_ytd_excess_returns(
    prices: pd.DataFrame,
    benchmark: pd.DataFrame,
    *,
    as_of: Optional[date] = None,
    security_price_col: str = "adjusted_close",
    benchmark_price_col: str = "close",
    tolerance_days: int = 7,
) -> pd.DataFrame:
    """Compute year-to-date returns against a date-matched benchmark.

    YTD starts at the last mutually observed trading session of the previous
    calendar year and ends at the latest mutually observed session on or
    before ``as_of``.  Requiring both dates to exist in the security and
    benchmark series prevents a manually filled close, a holiday mismatch, or
    a stale benchmark from being presented as an analytical return.

    The output contains one row per ticker that has a valid pair of start and
    end observations.  Missing baselines are intentionally omitted; callers
    should left-join this frame so the resulting metric remains a visible
    data gap rather than an imputed zero.
    """
    columns = [
        "ticker",
        "return_ytd",
        "benchmark_return_ytd",
        "excess_return_ytd",
        "return_ytd_start_date",
        "return_ytd_end_date",
    ]
    if prices is None or prices.empty or benchmark is None or benchmark.empty:
        return pd.DataFrame(columns=columns)
    if "ticker" not in prices.columns or "date" not in prices.columns:
        return pd.DataFrame(columns=columns)
    if "date" not in benchmark.columns:
        return pd.DataFrame(columns=columns)
    if security_price_col not in prices.columns or benchmark_price_col not in benchmark.columns:
        return pd.DataFrame(columns=columns)

    sec = prices[["ticker", "date", security_price_col]].copy()
    sec["ticker"] = sec["ticker"].astype(str).str.upper()
    sec["date"] = pd.to_datetime(sec["date"], errors="coerce").dt.date
    sec[security_price_col] = pd.to_numeric(sec[security_price_col], errors="coerce")
    sec = sec.dropna(subset=["ticker", "date", security_price_col])
    sec = sec[sec[security_price_col] > 0]
    sec = sec.sort_values(["ticker", "date"]).drop_duplicates(
        subset=["ticker", "date"], keep="last"
    )

    bench = benchmark[["date", benchmark_price_col]].copy()
    bench["date"] = pd.to_datetime(bench["date"], errors="coerce").dt.date
    bench[benchmark_price_col] = pd.to_numeric(
        bench[benchmark_price_col], errors="coerce"
    )
    bench = bench.dropna(subset=["date", benchmark_price_col])
    bench = bench[bench[benchmark_price_col] > 0]
    bench = bench.sort_values("date").drop_duplicates(subset=["date"], keep="last")
    if sec.empty or bench.empty:
        return pd.DataFrame(columns=columns)

    cutoff = as_of or max(sec["date"].max(), bench["date"].max())
    if isinstance(cutoff, pd.Timestamp):
        cutoff = cutoff.date()
    elif not isinstance(cutoff, date):
        cutoff = pd.Timestamp(cutoff).date()

    previous_year_end = date(cutoff.year - 1, 12, 31)
    benchmark_dates = set(bench["date"])
    rows: list[dict] = []
    for ticker, ticker_frame in sec.groupby("ticker", sort=True):
        security_dates = set(ticker_frame["date"])
        common_dates = sorted(security_dates & benchmark_dates)
        if not common_dates:
            continue

        baseline_dates = [d for d in common_dates if d <= previous_year_end]
        end_dates = [d for d in common_dates if d <= cutoff]
        if not baseline_dates or not end_dates:
            continue
        start_date = baseline_dates[-1]
        end_date = end_dates[-1]
        if end_date <= start_date or (cutoff - end_date).days > tolerance_days:
            continue

        ticker_lookup = ticker_frame.set_index("date")[security_price_col]
        benchmark_lookup = bench.set_index("date")[benchmark_price_col]
        start_security = ticker_lookup.get(start_date)
        end_security = ticker_lookup.get(end_date)
        start_benchmark = benchmark_lookup.get(start_date)
        end_benchmark = benchmark_lookup.get(end_date)
        if any(value is None or pd.isna(value) or float(value) <= 0 for value in (
            start_security,
            end_security,
            start_benchmark,
            end_benchmark,
        )):
            continue

        security_return = (float(end_security) / float(start_security) - 1.0) * 100.0
        benchmark_return = (float(end_benchmark) / float(start_benchmark) - 1.0) * 100.0
        rows.append(
            {
                "ticker": ticker,
                "return_ytd": security_return,
                "benchmark_return_ytd": benchmark_return,
                "excess_return_ytd": security_return - benchmark_return,
                "return_ytd_start_date": start_date,
                "return_ytd_end_date": end_date,
            }
        )
    return pd.DataFrame(rows, columns=columns)


def _safe_diff(a, b):
    """Element-wise (excess_5d - excess_60d), scalar- or Series-safe.

    Previously this took scalar logic (``pd.isna(a)`` in an ``if``) but was
    called with whole Series, so the ``if`` raised and the ``except``
    collapsed every row to ``None``. Handle both shapes explicitly.
    """
    import numpy as np

    if a is None or b is None:
        return None
    try:
        a_is_series = isinstance(a, pd.Series)
        b_is_series = isinstance(b, pd.Series)
        if a_is_series or b_is_series:
            a_num = pd.to_numeric(a, errors="coerce")
            b_num = pd.to_numeric(b, errors="coerce")
            diff = a_num - b_num
            # Preserve missing as None-equivalent (NaN) for DataFrame storage.
            return diff.where(diff.notna(), np.nan)
        if pd.isna(a) or pd.isna(b):
            return None
        return float(a) - float(b)
    except Exception:
        return None
