"""Signed attribution and absolute concentration as separate contracts.

Signed contribution answers *who drove the net group move?*. Absolute
concentration answers *how dependent were constituent moves on a few names?*.
The signed denominator can be unstable when positive and negative moves nearly
cancel; in that case signed fields are explicitly undefined while absolute
shares and HHI remain valid.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from typing import Optional

import numpy as np
import pandas as pd


@dataclass
class ConcentrationV2:
    top1_abs_share: Optional[float] = None
    top3_abs_share: Optional[float] = None
    top5_abs_share: Optional[float] = None
    top1_signed_share: Optional[float] = None
    top3_signed_share: Optional[float] = None
    hhi: Optional[float] = None
    contributor_count: int = 0
    requested_constituent_count: int = 0
    missing_constituent_count: int = 0
    top_absolute_contributor: Optional[str] = None
    net_signed_return: Optional[float] = None
    gross_absolute_return: Optional[float] = None
    signed_denominator_ratio: Optional[float] = None
    status: str = "UNDEFINED"
    signed_attribution_status: str = "UNDEFINED_NO_CONTRIBUTORS"
    absolute_concentration_status: str = "UNDEFINED_NO_CONTRIBUTORS"
    convention: str = "absolute_move_v2"

    def to_dict(self) -> dict:
        return asdict(self)


def compute_concentration_v2(
    prices: pd.DataFrame,
    *,
    group_tickers: list[str],
    horizon: int = 20,
    as_of: Optional[date] = None,
    signed_denominator_epsilon: float = 1e-8,
    signed_min_net_to_gross: float = 0.05,
    price_col: str = "adjusted_close",
) -> ConcentrationV2:
    """Compute constituent attribution and concentration over ``horizon``.

    ``signed_min_net_to_gross`` is a transparent stability guard. Signed
    attribution is undefined when ``abs(net move) / gross absolute move`` is
    below this fraction, because cancellation would make shares arbitrarily
    large. The default 5% guard is methodological, not fitted to forward
    returns.
    """

    if horizon < 1:
        raise ValueError("horizon must be at least 1")
    if signed_denominator_epsilon < 0:
        raise ValueError("signed_denominator_epsilon must be non-negative")
    if not 0 <= signed_min_net_to_gross <= 1:
        raise ValueError("signed_min_net_to_gross must be between 0 and 1")

    requested_tickers = list(
        dict.fromkeys(str(ticker) for ticker in group_tickers if ticker is not None)
    )
    requested_count = len(requested_tickers)
    empty = ConcentrationV2(
        requested_constituent_count=requested_count,
        missing_constituent_count=requested_count,
    )
    if requested_count == 0 or prices is None or prices.empty:
        return empty
    required_columns = {"ticker", "date", price_col}
    missing_columns = required_columns.difference(prices.columns)
    if missing_columns:
        raise ValueError(
            "prices missing required columns: " + ", ".join(sorted(missing_columns))
        )

    sub = prices[prices["ticker"].astype(str).isin(requested_tickers)].copy()
    if sub.empty:
        return empty
    sub["date"] = pd.to_datetime(sub["date"], errors="coerce").dt.date
    sub[price_col] = pd.to_numeric(
        sub[price_col], errors="coerce"
    ).replace([np.inf, -np.inf], np.nan)
    sub = sub.dropna(subset=["date", price_col])

    rows: list[dict[str, object]] = []
    for ticker, ticker_prices in sub.groupby("ticker", sort=True):
        ordered = ticker_prices.sort_values("date")
        if as_of is not None:
            ordered = ordered[ordered["date"] <= as_of]
        ordered = ordered.drop_duplicates("date", keep="last")
        if len(ordered) <= horizon:
            continue
        start = float(ordered[price_col].iloc[-(horizon + 1)])
        end = float(ordered[price_col].iloc[-1])
        if not np.isfinite(start) or not np.isfinite(end) or start <= 0 or end <= 0:
            continue
        constituent_return = (end / start - 1.0) * 100.0
        if not np.isfinite(constituent_return):
            continue
        rows.append(
            {
                "ticker": str(ticker),
                "return": float(constituent_return),
                "abs_return": abs(float(constituent_return)),
            }
        )

    contributions = pd.DataFrame(rows)
    contributor_count = int(len(contributions))
    missing_count = max(0, requested_count - contributor_count)
    if contributions.empty:
        return ConcentrationV2(
            contributor_count=0,
            requested_constituent_count=requested_count,
            missing_constituent_count=missing_count,
        )

    net_move = float(contributions["return"].sum())
    gross_move = float(contributions["abs_return"].sum())
    common = {
        "contributor_count": contributor_count,
        "requested_constituent_count": requested_count,
        "missing_constituent_count": missing_count,
        "net_signed_return": round(net_move, 8),
        "gross_absolute_return": round(gross_move, 8),
    }

    if gross_move <= signed_denominator_epsilon:
        return ConcentrationV2(
            **common,
            signed_denominator_ratio=0.0,
            status="UNDEFINED",
            signed_attribution_status="UNDEFINED_UNSTABLE_DENOMINATOR",
            absolute_concentration_status="UNDEFINED_NO_ABSOLUTE_MOVE",
        )

    contributions["abs_share"] = contributions["abs_return"] / gross_move
    absolute_sorted = contributions.sort_values(
        ["abs_share", "ticker"], ascending=[False, True]
    ).reset_index(drop=True)
    top1_abs = float(absolute_sorted["abs_share"].iloc[0])
    top3_abs = (
        float(absolute_sorted["abs_share"].head(3).sum())
        if contributor_count >= 3
        else None
    )
    top5_abs = (
        float(absolute_sorted["abs_share"].head(5).sum())
        if contributor_count >= 5
        else None
    )
    hhi = float((absolute_sorted["abs_share"] ** 2).sum())

    denominator_ratio = abs(net_move) / gross_move
    signed_is_stable = (
        abs(net_move) > signed_denominator_epsilon
        and denominator_ratio >= signed_min_net_to_gross
    )
    top1_signed: Optional[float] = None
    top3_signed: Optional[float] = None
    signed_status = "UNDEFINED_UNSTABLE_DENOMINATOR"
    if signed_is_stable:
        absolute_sorted["signed_share"] = absolute_sorted["return"] / net_move
        top1_signed = float(absolute_sorted["signed_share"].iloc[0])
        if contributor_count >= 3:
            top3_signed = float(absolute_sorted["signed_share"].head(3).sum())
        signed_status = "DEFINED"

    return ConcentrationV2(
        top1_abs_share=round(min(max(top1_abs, 0.0), 1.0), 4),
        top3_abs_share=(
            round(min(max(top3_abs, 0.0), 1.0), 4)
            if top3_abs is not None
            else None
        ),
        top5_abs_share=(
            round(min(max(top5_abs, 0.0), 1.0), 4)
            if top5_abs is not None
            else None
        ),
        top1_signed_share=(
            round(top1_signed, 4) if top1_signed is not None else None
        ),
        top3_signed_share=(
            round(top3_signed, 4) if top3_signed is not None else None
        ),
        hhi=round(min(max(hhi, 0.0), 1.0), 4),
        top_absolute_contributor=str(absolute_sorted["ticker"].iloc[0]),
        signed_denominator_ratio=round(denominator_ratio, 8),
        status="DEFINED",
        signed_attribution_status=signed_status,
        absolute_concentration_status="DEFINED",
        **common,
    )
