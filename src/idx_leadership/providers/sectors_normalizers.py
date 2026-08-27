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
        out_rows.append(
            {
                "ticker": sym,
                "vendor_ticker": sym,
                "company_name": r.get("company_name"),
                "listing_board": r.get("listing_board"),
                "sector": r.get("sector"),
                "sub_sector": r.get("sub_sector"),
                "industry": r.get("industry"),
                "sub_industry": r.get("sub_industry"),
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
    rows: Iterable[Mapping[str, Any]], *, as_of: date, source: str = "sectors"
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
        out_rows.append(
            {
                "ticker": sym,
                "date": as_of,
                "close": price,
                # Sectors v2 close field is treated as raw close (see
                # `KNOWN_GAPS.md` G011 for the basis audit). The column
                # is duplicated to `adjusted_close` so downstream
                # code that only consumes `adjusted_close` still
                # works; a future pass will split them.
                "adjusted_close": price,
                "volume": None,
                "market_cap": None,
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
