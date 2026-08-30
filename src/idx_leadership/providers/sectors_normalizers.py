"""Sectors v2 response → canonical DataFrame normalizers.

Each function takes the raw `results` array (or a single payload) returned
by the Sectors v2 client and returns a canonical `pd.DataFrame` with the
documented column names used by the rest of the engine.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Iterable, Mapping

import pandas as pd


def _to_symbol(raw: str) -> str:
    s = (raw or "").strip().upper()
    if not s:
        return ""
    if not s.endswith(".JK"):
        s = s + ".JK"
    return s


def normalize_companies(rows: Iterable[Mapping[str, Any]]) -> pd.DataFrame:
    out_rows: list[dict] = []
    for r in rows:
        sym = _to_symbol(str(r.get("symbol") or ""))
        if not sym:
            continue
        query_values = r.get("query_values")
        query_values = query_values if isinstance(query_values, Mapping) else {}

        def value(name: str, *aliases: str) -> Any:
            for key in (name, *aliases):
                raw = r.get(key)
                if raw is not None:
                    return raw
                raw = query_values.get(key)
                if raw is not None:
                    return raw
            return None

        out_rows.append(
            {
                "ticker": sym,
                "vendor_ticker": sym,
                "company_name": r.get("company_name"),
                "security_id": value("security_id", "company_id", "id"),
                "listing_status": value("listing_status", "status"),
                "instrument_type": value("instrument_type", "security_type"),
                "listing_board": value("listing_board"),
                "sector": value("sector"),
                "sub_sector": value("sub_sector", "subsector"),
                "industry": value("industry"),
                "sub_industry": value("sub_industry", "subindustry"),
                "market_cap": r.get("market_cap"),
                "market_cap_rank": r.get("market_cap_rank"),
                "listing_date": r.get("listing_date"),
                "last_close_price": r.get("last_close_price"),
                "esg_score": r.get("esg_score"),
                "yield_ttm": r.get("yield_ttm"),
                "yoy_quarter_revenue_growth": r.get("yoy_quarter_revenue_growth"),
                "yoy_quarter_earnings_growth": r.get("yoy_quarter_earnings_growth"),
                "tags": r.get("tags") or [],
                "indices": r.get("indices") or [],
            }
        )
    if not out_rows:
        return pd.DataFrame()
    return pd.DataFrame(out_rows)


def normalize_close_cross_section(
    rows: Iterable[Mapping[str, Any]], *, as_of: date | None, source: str = "sectors"
) -> pd.DataFrame:
    out_rows: list[dict] = []
    for r in rows:
        sym = _to_symbol(str(r.get("symbol") or ""))
        if not sym:
            continue
        try:
            price = float(r.get("close"))
        except (TypeError, ValueError):
            continue
        row_date = r.get("date")
        try:
            normalized_date = pd.Timestamp(row_date).date() if row_date is not None else as_of
        except (TypeError, ValueError):
            normalized_date = as_of
        if normalized_date is None:
            continue
        out_rows.append(
            {
                "ticker": sym,
                "date": normalized_date,
                "close": price,
                # Sectors v2 close field is treated as raw close (see
                # `KNOWN_GAPS.md` G011 for the basis audit). The column
                # is duplicated to `adjusted_close` so downstream
                # code that only consumes `adjusted_close` still
                # works; a future pass will split them.
                "adjusted_close": price,
                "volume": _numeric_or_none(r.get("volume")),
                "market_cap": _numeric_or_none(r.get("market_cap")),
                "currency": "IDR",
                "price_basis": "close",
                "source": source,
            }
        )
    if not out_rows:
        return pd.DataFrame(
            columns=[
                "ticker",
                "date",
                "close",
                "adjusted_close",
                "volume",
                "market_cap",
                "currency",
                "price_basis",
                "source",
            ]
        )
    return pd.DataFrame(out_rows)


def normalize_daily_history(
    payload: Any, *, source: str = "sectors"
) -> pd.DataFrame:
    """Normalize Sectors ``/v2/daily/{symbol}/`` rows."""

    rows = _payload_rows(payload)
    out_rows: list[dict[str, Any]] = []
    for r in rows:
        sym = _to_symbol(str(r.get("symbol") or ""))
        if not sym:
            continue
        try:
            row_date = pd.Timestamp(r.get("date")).date()
            close = float(r.get("close"))
        except (TypeError, ValueError):
            continue
        if close <= 0:
            continue
        out_rows.append(
            {
                "ticker": sym,
                "date": row_date,
                "close": close,
                "adjusted_close": close,
                "volume": _numeric_or_none(r.get("volume")),
                "market_cap": _numeric_or_none(r.get("market_cap")),
                "currency": "IDR",
                "price_basis": "close",
                "source": source,
            }
        )
    return pd.DataFrame(out_rows, columns=_price_columns())


def normalize_index_daily(
    payload: Any, *, benchmark_id: str, source: str = "sectors"
) -> pd.DataFrame:
    """Normalize Sectors native index-daily rows into benchmark columns."""

    rows = _payload_rows(payload)
    out_rows: list[dict[str, Any]] = []
    for r in rows:
        try:
            row_date = pd.Timestamp(r.get("date")).date()
            price = float(r.get("price"))
        except (TypeError, ValueError):
            continue
        if price <= 0:
            continue
        out_rows.append(
            {
                "benchmark_id": benchmark_id,
                "index_code": r.get("index_code"),
                "date": row_date,
                "close": price,
                "price_basis": "close",
                "source": source,
            }
        )
    return pd.DataFrame(
        out_rows,
        columns=["benchmark_id", "index_code", "date", "close", "price_basis", "source"],
    )


def normalize_free_float(rows: Iterable[Mapping[str, Any]]) -> pd.DataFrame:
    out_rows: list[dict] = []
    for r in rows:
        sym = _to_symbol(str(r.get("symbol") or ""))
        if not sym:
            continue
        ff = r.get("free_float")
        try:
            ff_val = float(ff)
        except (TypeError, ValueError):
            continue
        out_rows.append({"ticker": sym, "free_float": ff_val, "company_name": r.get("company_name")})
    if not out_rows:
        return pd.DataFrame(columns=["ticker", "free_float", "company_name"])
    return pd.DataFrame(out_rows)


def normalize_foreign_flow(payload: Mapping[str, Any]) -> pd.DataFrame:
    out_rows: list[dict] = []
    data = payload.get("data") if isinstance(payload, Mapping) else None
    if not isinstance(data, list):
        return pd.DataFrame(columns=["ticker", "date", "net_foreign_inflow"])
    for d in data:
        if not isinstance(d, Mapping):
            continue
        out_rows.append(
            {
                "ticker": _to_symbol(str(payload.get("symbol") or "")),
                "date": d.get("date"),
                "net_foreign_inflow": d.get("net_foreign_inflow"),
            }
        )
    if not out_rows:
        return pd.DataFrame(columns=["ticker", "date", "net_foreign_inflow"])
    return pd.DataFrame(out_rows)


def normalize_suspensions(rows: Iterable[Mapping[str, Any]]) -> pd.DataFrame:
    out_rows: list[dict] = []
    for r in rows:
        sym = _to_symbol(str(r.get("symbol") or ""))
        if not sym:
            continue
        out_rows.append(
            {
                "ticker": sym,
                "suspension_date": r.get("suspension_date"),
                "reason": r.get("reason"),
                "pdf_url": r.get("pdf_url"),
            }
        )
    if not out_rows:
        return pd.DataFrame(columns=["ticker", "suspension_date", "reason", "pdf_url"])
    return pd.DataFrame(out_rows)


def _payload_rows(payload: Any) -> list[Mapping[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, Mapping)]
    if isinstance(payload, Mapping):
        for key in ("results", "data", "items", "rows"):
            value = payload.get(key)
            if isinstance(value, list):
                return [row for row in value if isinstance(row, Mapping)]
    return []


def _numeric_or_none(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric if pd.notna(numeric) else None


def _price_columns() -> list[str]:
    return [
        "ticker",
        "date",
        "close",
        "adjusted_close",
        "volume",
        "market_cap",
        "currency",
        "price_basis",
        "source",
    ]
