"""Return engine.

Returns are computed in percent (e.g. 5.0 for +5%) and never use future
observations. As-of date resolution picks the latest available date
within a tolerance window.
"""
from __future__ import annotations

from datetime import date
from typing import Iterable, Optional

import numpy as np
import pandas as pd

from ..utils import get_logger
from ..utils.dates import asof_resolve

_log = get_logger(__name__)


def compute_returns(
    prices: pd.DataFrame,
    *,
    horizons: dict[str, int],
    price_col: str = "adjusted_close",
    as_of: Optional[date] = None,
    tolerance_days: int = 7,
) -> pd.DataFrame:
    """Compute horizon returns for one or more tickers.

    Parameters
    ----------
    prices:
        long-format DataFrame with columns: ticker, date, adjusted_close
    horizons:
        mapping like {"5d": 5, "20d": 20}
    price_col:
        which price column to use
    as_of:
        optional as-of date; uses the latest date <= as_of within tolerance
    tolerance_days:
        max staleness in days
    """
    if prices.empty:
        return pd.DataFrame()
    df = prices.copy()
    df["date"] = pd.to_datetime(df["date"]).dt.date
    out_rows: list[dict] = []
    for tkr, sub in df.groupby("ticker"):
        sub_sorted = sub.sort_values("date")
        sub_sorted = _dedupe(sub_sorted)
        sub_sorted = _validate_prices(sub_sorted, price_col)
        if as_of is not None:
            chosen = asof_resolve(sub_sorted["date"].tolist(), as_of, tolerance_days)
            if chosen is None:
                continue
            sub_sorted = sub_sorted[sub_sorted["date"] <= chosen]
        if sub_sorted.empty:
            continue
        # We compute the return relative to the most recent observation date.
        # The end is the most recent date for the ticker, the start is the
        # observation `h` trading days earlier.
        end_row = sub_sorted.iloc[-1]
        end_date = end_row["date"]
        end_price = float(end_row[price_col])
        row: dict = {
            "ticker": tkr,
            "as_of": end_date,
            "latest_close": end_price,
        }
        for label, h in horizons.items():
            start_price, start_date = _lookup_past(sub_sorted, end_date, h, price_col)
            if start_price is None:
                row[f"return_{label}"] = None
                row[f"return_{label}_start_date"] = None
            else:
                row[f"return_{label}"] = _pct_change(start_price, end_price)
                row[f"return_{label}_start_date"] = start_date
        out_rows.append(row)
    return pd.DataFrame(out_rows)


def compute_returns_for_universe(
    prices: pd.DataFrame,
    *,
    horizons: dict[str, int],
    price_col: str = "adjusted_close",
) -> pd.DataFrame:
    """Like compute_returns but uses the latest available date per ticker
    without an explicit as_of. Used in batch pipelines.
    """
    return compute_returns(
        prices,
        horizons=horizons,
        price_col=price_col,
        as_of=None,
    )


def forward_fill(
    df: pd.DataFrame,
    *,
    date_col: str = "date",
    group_col: str = "ticker",
    value_cols: Iterable[str] = ("close", "adjusted_close"),
) -> pd.DataFrame:
    """Forward-fill missing values for each ticker.

    Only valid for value columns. Does NOT forward-fill across tickers.
    Uses forward-fill then backward-fill within each ticker group; no
    interpolation is performed. Callers control the leading edge.
    """
    if df.empty:
        return df
    out = df.copy()
    out[date_col] = pd.to_datetime(out[date_col])
    out = out.sort_values([group_col, date_col])
    out = out.set_index(date_col)
    out[list(value_cols)] = (
        out.groupby(group_col)[list(value_cols)].apply(lambda g: g.ffill().bfill()).reset_index(level=0, drop=True)
    )
    out = out.reset_index()
    return out


def asof_close(
    prices: pd.DataFrame,
    *,
    as_of: date,
    price_col: str = "adjusted_close",
) -> pd.DataFrame:
    """For each ticker, return the latest observation at or before as_of."""
    df = prices.copy()
    df["date"] = pd.to_datetime(df["date"]).dt.date
    df = df[df["date"] <= as_of]
    df = df.sort_values("date").groupby("ticker").tail(1).reset_index(drop=True)
    df = df.rename(columns={price_col: "asof_price"})
    return df[["ticker", "date", "asof_price"]]


# ---- internals ----


def _pct_change(start: float, end: float) -> float:
    # Zero prices are not valid return denominators: a zero start produces
    # division by zero, and a zero end is an economically impossible price
    # that must not be reported as -100%. Both are NaN.
    if start == 0 or end == 0 or pd.isna(start) or pd.isna(end):
        return float("nan")
    return (end / start - 1.0) * 100.0


def _dedupe(df: pd.DataFrame) -> pd.DataFrame:
    """Drop duplicate dates for a single ticker; keep the last value seen."""
    return df.drop_duplicates(subset="date", keep="last").reset_index(drop=True)


def _validate_prices(df: pd.DataFrame, price_col: str) -> pd.DataFrame:
    df = df.copy()
    df[price_col] = pd.to_numeric(df[price_col], errors="coerce")
    df = df[df[price_col].notna() & (df[price_col] > 0.0)]
    return df


def _lookup_past(
    sub: pd.DataFrame,
    end_date: date,
    horizon: int,
    price_col: str,
) -> tuple[Optional[float], Optional[date]]:
    """Find the price `horizon` trading days before end_date.

    We treat the row index as the trading-day order. Returns the price
    and its date, or (None, None) if insufficient history.
    """
    if len(sub) <= horizon:
        return None, None
    # The last row is the end. Walk back `horizon` rows.
    start_row = sub.iloc[-(horizon + 1)]
    return float(start_row[price_col]), start_row["date"]
