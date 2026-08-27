"""Concentration engine.

Two complementary computations:

1. `compute_concentration` — robust default. Decomposes the GROUP'S
   absolute price move into per-constituent contributions (signed),
   then reports the top-N share of *absolute* contribution and HHI
   over the absolute shares. This avoids the sign-confusion trap when
   the group return is positive but most constituents are flat or
   negative (e.g. one constituent is doing all the work).

2. `compute_signed_contribution_table` — returns a fully-signed
   per-constituent contribution table. Useful for drill-down and
   evidence objects.

Method version: concentration-v1.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

from ..utils import get_logger
from ..utils.dates import asof_resolve
from .returns import compute_returns

_log = get_logger(__name__)


@dataclass
class ConcentrationResult:
    top1_contribution_share: Optional[float]
    top3_contribution_share: Optional[float]
    top5_contribution_share: Optional[float]
    hhi_contribution: Optional[float]
    contributor_count: int
    convention: str = "absolute_move"

    def to_dict(self) -> dict:
        return {
            "top1_contribution_share": self.top1_contribution_share,
            "top3_contribution_share": self.top3_contribution_share,
            "top5_contribution_share": self.top5_contribution_share,
            "hhi_contribution": self.hhi_contribution,
            "contributor_count": self.contributor_count,
            "convention": self.convention,
        }


def compute_signed_contribution_table(
    prices: pd.DataFrame,
    *,
    group_tickers: list[str],
    horizon: int = 20,
    as_of: Optional[pd.Timestamp] = None,
) -> pd.DataFrame:
    """Compute per-constituent returns and signed contribution shares.

    Contribution share_i = ret_i / sum_j(ret_j) when sum != 0.
    When sum == 0 (zero group move), shares are undefined and returned
    as NaN. A `caveat` column flags this case.
    """
    if not group_tickers:
        return pd.DataFrame()
    sub = prices[prices["ticker"].isin(group_tickers)].copy()
    if sub.empty:
        return pd.DataFrame()
    sub["date"] = pd.to_datetime(sub["date"])
    as_of_timestamp = pd.Timestamp(as_of) if as_of is not None else None
    rows: list[dict] = []
    for tkr, g in sub.groupby("ticker"):
        g_sorted = g.sort_values("date")
        if as_of_timestamp is not None:
            g_sorted = g_sorted[g_sorted["date"] <= as_of_timestamp]
        g_sorted = g_sorted.drop_duplicates("date", keep="last")
        if len(g_sorted) <= horizon:
            rows.append({"ticker": tkr, "return": None, "abs_return": None, "signed_share": None, "abs_share": None, "caveat": "insufficient_history"})
            continue
        end = float(g_sorted["adjusted_close"].iloc[-1])
        start = float(g_sorted["adjusted_close"].iloc[-(horizon + 1)])
        if start <= 0 or end <= 0:
            rows.append({"ticker": tkr, "return": None, "abs_return": None, "signed_share": None, "abs_share": None, "caveat": "invalid_price"})
            continue
        r = (end / start - 1.0) * 100.0
        rows.append({"ticker": tkr, "return": r, "abs_return": abs(r), "signed_share": None, "abs_share": None, "caveat": None})
    df = pd.DataFrame(rows)
    valid = df.dropna(subset=["return"])
    if valid.empty:
        return df
    s = valid["return"].sum()
    if s == 0:
        df["signed_share"] = float("nan")
    else:
        df["signed_share"] = df["return"] / s
    a = valid["abs_return"].sum()
    if a == 0:
        df["abs_share"] = float("nan")
    else:
        df["abs_share"] = df["abs_return"] / a
    return df


def compute_concentration(
    prices: pd.DataFrame,
    *,
    group_tickers: list[str],
    horizon: int = 20,
    as_of: Optional[pd.Timestamp] = None,
    top_n: tuple[int, ...] = (1, 3, 5),
) -> ConcentrationResult:
    """Compute concentration metrics using the absolute-move convention."""
    contrib = compute_signed_contribution_table(
        prices,
        group_tickers=group_tickers,
        horizon=horizon,
        as_of=as_of,
    )
    if contrib.empty or contrib["abs_share"].dropna().empty:
        return ConcentrationResult(
            top1_contribution_share=None,
            top3_contribution_share=None,
            top5_contribution_share=None,
            hhi_contribution=None,
            contributor_count=int(contrib.shape[0]),
        )
    abs_sorted = contrib.dropna(subset=["abs_share"]).sort_values("abs_share", ascending=False)
    contrib_count = int(len(abs_sorted))
    top1 = float(abs_sorted["abs_share"].iloc[0]) if contrib_count >= 1 else None
    top3 = float(abs_sorted["abs_share"].head(3).sum()) if contrib_count >= 3 else None
    top5 = float(abs_sorted["abs_share"].head(5).sum()) if contrib_count >= 5 else None
    hhi = float((abs_sorted["abs_share"] ** 2).sum())
    return ConcentrationResult(
        top1_contribution_share=round(top1, 4) if top1 is not None else None,
        top3_contribution_share=round(top3, 4) if top3 is not None else None,
        top5_contribution_share=round(top5, 4) if top5 is not None else None,
        hhi_contribution=round(hhi, 4) if hhi is not None else None,
        contributor_count=contrib_count,
    )
