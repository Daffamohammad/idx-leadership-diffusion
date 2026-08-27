"""Market-wide universe construction and eligibility filtering.

A market-wide candidate universe is filtered by:

  * listing status (must be active / Main / Development board)
  * sufficient history (>= 60 days of prices)
  * recent trading (close within the last 30 days)
  * taxonomy availability (sector / sub_sector / industry present)
  * not in suspensions (per Sectors /v2/suspensions/ window)

The output is a list of `(ticker, eligibility_flag, exclusion_reason)`
rows that the engine uses to scope the snapshot.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable, Optional

import pandas as pd

from ..utils import get_logger
from .capabilities import (
    EventProvider,
    PriceCrossSectionProvider,
    SecurityMasterProvider,
)

_log = get_logger(__name__)


@dataclass
class EligibilityConfig:
    lookback_history_days: int = 60
    stale_trading_days: int = 30
    min_history_days: int = 60
    exclude_suspended: bool = True
    exclude_delisted: bool = True
    listing_boards: tuple[str, ...] = ("Main", "Development", "Acceleration")


def build_market_universe(
    *,
    security_master_provider: SecurityMasterProvider,
    cross_section_provider: PriceCrossSectionProvider,
    event_provider: Optional[EventProvider] = None,
    as_of: date,
    config: Optional[EligibilityConfig] = None,
) -> pd.DataFrame:
    """Construct the eligible market universe for one as-of date.

    Returns a DataFrame with columns:
        ticker, sector, sub_sector, industry, sub_industry, listing_board,
        has_history, latest_close, eligible, exclusion_reason
    """
    cfg = config or EligibilityConfig()
    master = security_master_provider.get_security_master()
    if not master:
        return pd.DataFrame(
            columns=[
                "ticker",
                "sector",
                "sub_sector",
                "industry",
                "sub_industry",
                "listing_board",
                "has_history",
                "latest_close",
                "eligible",
                "exclusion_reason",
            ]
        )
    base = pd.DataFrame([m.model_dump() for m in master])

    # Look back across the universe for `min_history_days` working days.
    # We pull successive cross-sections until either we have enough rows or
    # we run out of `min_history_days` calendar days.
    start = as_of - timedelta(days=int(cfg.min_history_days * 1.8))
    rows: list[pd.DataFrame] = []
    cursor = as_of
    while cursor >= start:
        cs = cross_section_provider.get_full_universe_close(cursor)
        if not cs.empty:
            rows.append(cs[["ticker", "date", "close"]])
        cursor = cursor - timedelta(days=1)
        if len(rows) > cfg.min_history_days + 5:
            break
    if not rows:
        history = pd.DataFrame(columns=["ticker", "date", "close"])
    else:
        history = pd.concat(rows, ignore_index=True).drop_duplicates(["ticker", "date"])

    if not history.empty:
        counts = history.groupby("ticker")["date"].nunique().rename("observed_days")
        latest = (
            history.sort_values("date")
            .groupby("ticker")
            .tail(1)
            .set_index("ticker")[["date", "close"]]
            .rename(columns={"date": "latest_trade_date", "close": "latest_close"})
        )
    else:
        counts = pd.Series(dtype=int, name="observed_days")
        latest = pd.DataFrame(
            columns=["latest_trade_date", "latest_close"]
        ).set_index(pd.Index([], name="ticker"))

    base = base.merge(counts, left_on="ticker", right_index=True, how="left")
    base = base.merge(latest, left_on="ticker", right_index=True, how="left")
    base["observed_days"] = base["observed_days"].fillna(0).astype(int)

    # Suspensions window
    suspended: set[str] = set()
    if cfg.exclude_suspended and event_provider is not None:
        susp = event_provider.get_suspensions(
            start=as_of - timedelta(days=cfg.stale_trading_days * 2),
            end=as_of,
        )
        if not susp.empty:
            suspended = set(susp["ticker"].astype(str).tolist())

    eligible_flags: list[bool] = []
    reasons: list[str] = []
    for _, row in base.iterrows():
        reasons.append(_row_reason(row, cfg, suspended, as_of))
        eligible_flags.append(reasons[-1] == "")
    base["has_history"] = base["observed_days"] >= cfg.min_history_days
    base["latest_close"] = base["latest_close"]
    base["eligible"] = eligible_flags
    base["exclusion_reason"] = reasons
    return base


def _row_reason(row: pd.Series, cfg: EligibilityConfig, suspended: set[str], as_of: date) -> str:
    if cfg.exclude_suspended and str(row.get("ticker")) in suspended:
        return "recently_suspended"
    if row.get("listing_board") not in cfg.listing_boards:
        return "listing_board"
    if not row.get("sector") or not row.get("subsector"):
        return "no_taxonomy"
    if int(row.get("observed_days") or 0) < cfg.min_history_days:
        return "insufficient_history"
    last = row.get("latest_trade_date")
    if last is None or pd.isna(last):
        return "stale_price"
    try:
        last_d = last.date() if hasattr(last, "date") else last
        if (pd.Timestamp(as_of) - pd.Timestamp(last_d)).days > cfg.stale_trading_days:
            return "stale_price"
    except Exception:  # noqa: BLE001
        return "stale_price"
    return ""


def eligibility_summary(df: pd.DataFrame) -> dict:
    if df.empty:
        return {"total": 0, "eligible": 0, "excluded": 0, "by_reason": {}}
    excluded = df[~df["eligible"]]
    by_reason = excluded["exclusion_reason"].value_counts().to_dict()
    return {
        "total": int(len(df)),
        "eligible": int(df["eligible"].sum()),
        "excluded": int(len(excluded)),
        "by_reason": {str(k): int(v) for k, v in by_reason.items()},
    }
