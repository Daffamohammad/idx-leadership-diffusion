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
    min_median_daily_value: float | None = None


def build_market_universe(
    *,
    security_master_provider: SecurityMasterProvider,
    cross_section_provider: PriceCrossSectionProvider,
    event_provider: Optional[EventProvider] = None,
    as_of: date,
    config: Optional[EligibilityConfig] = None,
    price_history: pd.DataFrame | None = None,
    security_master: list[object] | None = None,
    acquisition_failures: set[str] | None = None,
    acquisition_empties: set[str] | None = None,
) -> pd.DataFrame:
    """Construct the eligible market universe for one as-of date.

    Returns a DataFrame with columns:
        ticker, sector, sub_sector, industry, sub_industry, listing_board,
        has_history, latest_close, eligible, exclusion_reason,
        acquisition_status

    acquisition_status is one of:
        POLICY_EXCLUDED     — failed a policy check (suspension, delisting,
                              board, taxonomy, non-common-equity, stale, liquidity)
        ACQUISITION_FAILED — policy-eligible but provider returned 429/network
                              error; remains in the analytical denominator
        ACQUISITION_EMPTY  — policy-eligible but returned empty history;
                              treated as insufficient evidence
        ACQUIRED           — policy-eligible and data was returned
    """
    cfg = config or EligibilityConfig()
    master = (
        security_master
        if security_master is not None
        else security_master_provider.get_security_master()
    )
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

    if price_history is not None:
        history = _canonical_history(price_history)
    else:
        # Compatibility path for providers that only expose a daily
        # cross-section. A live Sectors run supplies price_history directly so
        # this loop does not turn a market-wide refresh into dozens of full
        # universe requests.
        start = as_of - timedelta(days=int(cfg.min_history_days * 1.8))
        rows: list[pd.DataFrame] = []
        cursor = as_of
        while cursor >= start:
            cs = cross_section_provider.get_full_universe_close(cursor)
            if not cs.empty and {"ticker", "date", "close"}.issubset(cs.columns):
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
        first = (
            history.sort_values("date")
            .groupby("ticker")
            .head(1)
            .set_index("ticker")[["date"]]
            .rename(columns={"date": "first_trade_date"})
        )
        latest = latest.join(first, how="left")
    else:
        counts = pd.Series(dtype=int, name="observed_days")
        latest = pd.DataFrame(
            columns=["latest_trade_date", "latest_close", "first_trade_date"]
        ).set_index(pd.Index([], name="ticker"))

    base = base.merge(counts, left_on="ticker", right_index=True, how="left")
    base = base.merge(latest, left_on="ticker", right_index=True, how="left")
    base["observed_days"] = base["observed_days"].fillna(0).astype(int)

    median_value = _median_daily_value(history)
    if not median_value.empty:
        base = base.merge(
            median_value.rename("median_daily_value"),
            left_on="ticker",
            right_index=True,
            how="left",
        )
    else:
        base["median_daily_value"] = None

    # Suspensions window
    suspended: set[str] = set()
    if cfg.exclude_suspended and event_provider is not None:
        susp = event_provider.get_suspensions(
            start=as_of - timedelta(days=cfg.stale_trading_days * 2),
            end=as_of,
        )
        if not susp.empty:
            suspended = set(susp["ticker"].astype(str).tolist())

    fail_set = {str(t).upper() for t in (acquisition_failures or set())}
    empty_set = {str(t).upper() for t in (acquisition_empties or set())}

    # Tick-by-tick policy evaluation. Tickers in the acquisition failure
    # or empty set have their policy evaluation done with adjusted row
    # values that bypass the data-availability checks (insufficient_history,
    # stale_price) — the failure is in acquisition, not in policy.
    eligible_flags: list[bool] = []
    reasons: list[str] = []
    acq_statuses: list[str] = []
    for _, row in base.iterrows():
        ticker = str(row.get("ticker", "")).upper()
        is_acq_issue = ticker in fail_set or ticker in empty_set
        if is_acq_issue:
            # Synthesize a row that passes data-availability checks so
            # only the genuine policy rules (suspension, delisting, board,
            # taxonomy, non-common-equity) are evaluated.
            row_eval = row.copy()
            row_eval["observed_days"] = max(
                int(row.get("observed_days") or 0), cfg.min_history_days
            )
            if pd.isna(row_eval.get("latest_trade_date")) or row_eval.get(
                "latest_trade_date"
            ) is None:
                row_eval["latest_trade_date"] = as_of
        else:
            row_eval = row
        reason = _row_reason(row_eval, cfg, suspended, as_of)
        reasons.append(reason)
        policy_ok = reason == ""
        eligible_flags.append(policy_ok)
        if not policy_ok:
            acq_statuses.append("POLICY_EXCLUDED")
        elif ticker in fail_set:
            acq_statuses.append("ACQUISITION_FAILED")
        elif ticker in empty_set:
            acq_statuses.append("ACQUISITION_EMPTY")
        else:
            acq_statuses.append("ACQUIRED")
    base["has_history"] = base["observed_days"] >= cfg.min_history_days
    base["latest_close"] = base["latest_close"]
    base["eligible"] = eligible_flags
    base["exclusion_reason"] = reasons
    base["acquisition_status"] = acq_statuses
    return base


def _row_reason(row: pd.Series, cfg: EligibilityConfig, suspended: set[str], as_of: date) -> str:
    if cfg.exclude_suspended and str(row.get("ticker")) in suspended:
        return "recently_suspended"
    common_equity_status = str(row.get("common_equity_status") or "").upper()
    if common_equity_status == "NON_COMMON_EQUITY":
        return "non_common_equity"
    listing_status = str(row.get("listing_status") or "").strip().lower()
    if cfg.exclude_delisted and (
        row.get("active") is False
        or listing_status in {"delisted", "inactive", "suspended"}
    ):
        return "inactive_listing"
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
    if cfg.min_median_daily_value is not None:
        median_value = row.get("median_daily_value")
        if median_value is None or pd.isna(median_value):
            return "liquidity_unknown"
        if float(median_value) < float(cfg.min_median_daily_value):
            return "insufficient_liquidity"
    return ""


def eligibility_summary(df: pd.DataFrame) -> dict:
    if df.empty:
        return {"total": 0, "eligible": 0, "excluded": 0, "by_reason": {}}
    excluded = df[~df["eligible"]]
    by_reason = excluded["exclusion_reason"].value_counts().to_dict()
    acq_col = df.get("acquisition_status")
    acq_counts: dict[str, int] = {}
    if acq_col is not None:
        acq_counts = {str(k): int(v) for k, v in acq_col.value_counts().items()}
    return {
        "total": int(len(df)),
        "eligible": int(df["eligible"].sum()),
        "excluded": int(len(excluded)),
        "by_reason": {str(k): int(v) for k, v in by_reason.items()},
        "acquisition_status": acq_counts,
        "policy_eligible": int((df["eligible"] & (acq_col != "POLICY_EXCLUDED")).sum())
        if acq_col is not None
        else int(df["eligible"].sum()),
        "acquired": int(
            (df["eligible"] & (acq_col == "ACQUIRED")).sum()
        )
        if acq_col is not None
        else int(df["eligible"].sum()),
        "acquisition_failed": int(
            (df["eligible"] & (acq_col == "ACQUISITION_FAILED")).sum()
        )
        if acq_col is not None
        else 0,
        "acquisition_empty": int(
            (df["eligible"] & (acq_col == "ACQUISITION_EMPTY")).sum()
        )
        if acq_col is not None
        else 0,
    }


def _canonical_history(prices: pd.DataFrame) -> pd.DataFrame:
    """Keep the minimum history columns used by eligibility diagnostics."""

    if prices is None or prices.empty or not {"ticker", "date"}.issubset(prices.columns):
        return pd.DataFrame(columns=["ticker", "date", "close"])
    history = prices.copy()
    history["date"] = pd.to_datetime(history["date"], errors="coerce").dt.date
    if "close" not in history.columns:
        history["close"] = history.get("adjusted_close")
    history["close"] = pd.to_numeric(history["close"], errors="coerce")
    history = history.dropna(subset=["ticker", "date", "close"])
    history = history[history["close"] > 0]
    return history.drop_duplicates(["ticker", "date"], keep="last")


def _median_daily_value(history: pd.DataFrame) -> pd.Series:
    if history.empty or "volume" not in history.columns:
        return pd.Series(dtype=float, name="median_daily_value")
    close = pd.to_numeric(history["close"], errors="coerce")
    volume = pd.to_numeric(history["volume"], errors="coerce")
    value = (close * volume).where(close.gt(0) & volume.ge(0))
    frame = pd.DataFrame({"ticker": history["ticker"], "value": value}).dropna()
    if frame.empty:
        return pd.Series(dtype=float, name="median_daily_value")
    return frame.groupby("ticker")["value"].median()
