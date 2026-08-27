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


def _safe_diff(a, b):
    import numpy as np
    if a is None or b is None:
        return None
    try:
        if pd.isna(a) or pd.isna(b):
            return None
        return float(a) - float(b)
    except Exception:
        return None
