"""Date helpers — explicit, no implicit timezones beyond naive UTC dates."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Iterable

import pandas as pd


def parse_date(value: str | date | datetime | pd.Timestamp) -> date:
    """Coerce a value to a `datetime.date`. Raises TypeError for unsupported types."""
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, pd.Timestamp):
        return value.date()
    if isinstance(value, str):
        return datetime.strptime(value, "%Y-%m-%d").date()
    raise TypeError(f"Cannot parse date from {type(value).__name__}")


def to_iso(d: date) -> str:
    """ISO-8601 (YYYY-MM-DD) serialization."""
    return d.strftime("%Y-%m-%d")


def asof_resolve(
    dates: Iterable[date],
    cutoff: date,
    tolerance_days: int = 7,
) -> date | None:
    """Return the latest date in `dates` that is <= cutoff within tolerance.

    - If multiple dates qualify, return the latest.
    - If the latest qualifying date is more than `tolerance_days` before cutoff,
      return None to signal that data is stale.
    - `cutoff` itself may be a non-trading day; the most recent prior trading
      date is used.
    """
    materialised = sorted({parse_date(d) for d in dates if d is not None})
    if not materialised:
        return None
    qualifying = [d for d in materialised if d <= cutoff]
    if not qualifying:
        return None
    chosen = qualifying[-1]
    if (cutoff - chosen).days > tolerance_days:
        return None
    return chosen


def trading_days_between(start: date, end: date) -> int:
    """Approximate business-day count between two dates. Inclusive of both ends."""
    if end < start:
        return 0
    # pandas BusinessDay is sufficient for proxy in groundwork.
    return int(len(pd.bdate_range(start=start, end=end)))


def add_business_days(start: date, n: int) -> date:
    """Add N business days to a date."""
    if n < 0:
        return (pd.bdate_range(end=start, periods=abs(n) + 1)[0]).date() if False else _shift(start, n)
    return _shift(start, n)


def _shift(start: date, n: int) -> date:
    rng = pd.bdate_range(start=start, periods=abs(n) + 1)
    if n >= 0:
        return rng[-1].date()
    return rng[0].date()


def today_utc() -> date:
    """Return today's date (naive)."""
    return datetime.now(timezone.utc).date()


def date_range(start: date, end: date) -> list[date]:
    """Inclusive list of daily dates between start and end."""
    if end < start:
        return []
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]
