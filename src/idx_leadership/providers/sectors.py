"""Sectors v2 provider — implements the capability set end-to-end.

This is the production code path for the engine. It is **gated** by
`allow_live=False` by default to prevent accidental credit spend during
tests; the constructor is permissive but every live HTTP call is
refused unless the client is constructed with `allow_live=True` (which
the CLI does explicitly when invoked by a human).

The provider implements:
  * `SecurityMasterProvider`        — /v2/companies/
  * `PriceCrossSectionProvider`     — /v2/close/
  * `BenchmarkProvider`             — IHSG proxy via the /v2/close/ cross-section
                                     (the `IHSG.JK` symbol is part of the
                                     cross-section when present)
  * `TaxonomyProvider`              — derived from /v2/companies/
  * `FreeFloatProvider`             — /v2/free-float/
  * `FlowProvider`                  — /v2/foreign-flow/{symbol}/
  * `EventProvider`                 — /v2/company/corporate-actions/{symbol}/
                                     and /v2/suspensions/

The `PriceHistoryProvider` interface is satisfied via the
`get_full_universe_close` cross-section, and the per-symbol history is
expressed by joining across days (the engine reconstructs any history
window from consecutive cross-sections). This matches the Sectors
"full-universe close" architecture exactly.

For a per-symbol daily history of arbitrary length, the engine can also
call `get_symbol_history(symbol, start, end)` which uses
`/v2/close/?date=YYYY-MM-DD` per day — billed as Tier 3 and only used
when the engine needs a long history for one symbol.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, Mapping, Optional

import pandas as pd

from ..models import (
    BenchmarkObservation,
    PriceObservation,
    ProviderMode,
    ProviderName,
    SecurityMasterEntry,
)
from ..utils import get_logger, project_root
from ..utils.errors import ProviderError
from .capabilities import (
    BenchmarkProvider,
    EventProvider,
    FlowProvider,
    FreeFloatProvider,
    PriceCrossSectionProvider,
    PriceHistoryProvider,
    SecurityMasterProvider,
    TaxonomyProvider,
)
from .ledger import RequestLedger
from .sectors_client import SectorsClient
from .sectors_normalizers import (
    normalize_companies,
    normalize_close_cross_section,
    normalize_free_float,
    normalize_foreign_flow,
    normalize_suspensions,
)

_log = get_logger(__name__)


def _optional_value(value: Any) -> Any:
    """Convert pandas' missing scalar back to the canonical optional value."""
    return None if pd.isna(value) else value


class SectorsProvider(
    SecurityMasterProvider,
    PriceCrossSectionProvider,
    PriceHistoryProvider,
    BenchmarkProvider,
    TaxonomyProvider,
    FreeFloatProvider,
    FlowProvider,
    EventProvider,
):
    """Real Sectors v2 provider."""

    name = "sectors"
    mode = ProviderMode.SECTORS_LIVE

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://api.sectors.app",
        ledger: Optional[RequestLedger] = None,
        allow_live: bool = False,
        client: Optional[SectorsClient] = None,
        mode: ProviderMode = ProviderMode.SECTORS_LIVE,
        max_pages: Optional[int] = None,
        force_refresh: bool = False,
    ) -> None:
        if mode not in {ProviderMode.SECTORS_LIVE, ProviderMode.SECTORS_FIXTURE}:
            raise ProviderError(f"SectorsProvider cannot run in mode {mode.value}")
        if client is not None and client.mode is not mode:
            raise ProviderError(
                f"Sectors provider/client mode mismatch: {mode.value} vs {client.mode.value}"
            )
        self.base_url = base_url.rstrip("/")
        self.ledger = ledger or RequestLedger()
        self.mode = mode
        self.name = "sectors" if mode is ProviderMode.SECTORS_LIVE else "sectors_fixture"
        self.max_pages = max_pages
        self.client = client or SectorsClient(
            api_key=api_key,
            base_url=self.base_url,
            ledger=self.ledger,
            allow_live=allow_live,
            mode=mode,
            force_refresh=force_refresh,
            validate_contracts=True,
        )

    # ---- SecurityMasterProvider ----

    def get_security_master(self) -> list[SecurityMasterEntry]:
        rows = self.client.paginate(
            "/v2/companies/",
            {"limit": 30, "offset": 0},
            page_limit=self.max_pages,
        )
        if not rows:
            return []
        df = normalize_companies(rows)
        out: list[SecurityMasterEntry] = []
        for _, r in df.iterrows():
            out.append(
                SecurityMasterEntry(
                    ticker=r["ticker"],
                    vendor_ticker=r["vendor_ticker"],
                    company_name=_optional_value(r.get("company_name")),
                    exchange="IDX",
                    country="ID",
                    sector=_optional_value(r.get("sector")),
                    subsector=_optional_value(r.get("sub_sector")),
                    industry=_optional_value(r.get("industry")),
                    subindustry=_optional_value(r.get("sub_industry")),
                    group_id=_optional_value(r.get("sector")),
                    active=True,
                    benchmark_flag=False,
                    source=(
                        ProviderName.SECTORS
                        if self.mode is ProviderMode.SECTORS_LIVE
                        else ProviderName.FIXTURE
                    ),
                    source_as_of=date.today(),
                )
            )
        return out

    # ---- PriceCrossSectionProvider ----

    def get_full_universe_close(self, as_of: date) -> pd.DataFrame:
        rows = self.client.paginate(
            "/v2/close/",
            {"date": as_of.isoformat(), "limit": 30, "offset": 0},
            page_limit=self.max_pages,
        )
        return normalize_close_cross_section(
            rows,
            as_of=as_of,
            source=self.name,
        )

    # ---- PriceHistoryProvider (reconstructed from cross-sections) ----

    def get_price_history(
        self, tickers: list[str], *, start: date, end: date
    ) -> pd.DataFrame:
        """Reconstruct per-symbol history by iterating daily cross-sections.

        This is intentionally heavy — used only when the engine needs a
        long history for a small set of tickers (e.g. drilldown). For
        market-wide analytics the engine should use the
        `get_full_universe_close` cross-section directly.
        """
        from ..utils.dates import trading_days_between
        n = max(1, trading_days_between(start, end))
        frames: list[pd.DataFrame] = []
        tickers_set = set(tickers)
        # Cap at 90 daily cross-sections to avoid accidentally blowing the
        # credit budget on a typo. This is deliberately above the 60D
        # horizon because return computation needs horizon + 1 observations.
        # Callers needing more must use
        # `get_symbol_history`.
        n = min(n, 90)
        for i in range(n):
            d = (pd.Timestamp(end) - pd.offsets.BDay(i)).date()
            cs = self.get_full_universe_close(d)
            if not cs.empty:
                frames.append(cs[cs["ticker"].isin(tickers_set)])
        if not frames:
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
        return pd.concat(frames, ignore_index=True)

    # ---- BenchmarkProvider ----

    def get_benchmark_history(
        self, benchmark_id: str, *, start: date, end: date
    ) -> pd.DataFrame:
        # The benchmark symbol is the cross-section symbol when present.
        benchmark_key = (benchmark_id or "").strip().upper()
        # Config uses Yahoo's ``^JKSE`` identifier while Sectors exposes the
        # index row as ``IHSG.JK`` in the close cross-section.
        if benchmark_key in {"IHSG", "IHSG.JK", "^JKSE", "^JKSE.JK"}:
            symbol = "IHSG.JK"
        else:
            symbol = benchmark_key if benchmark_key.endswith(".JK") else f"{benchmark_key}.JK"
        # We reconstruct from daily cross-sections to obtain a series.
        from ..utils.dates import trading_days_between

        n = max(1, trading_days_between(start, end))
        rows: list[dict] = []
        # Cap; long windows should use the explicit per-symbol API.
        n = min(n, 90)
        for i in range(n):
            d = (pd.Timestamp(end) - pd.offsets.BDay(i)).date()
            cs = self.get_full_universe_close(d)
            row = cs[cs["ticker"] == symbol]
            if not row.empty:
                rows.append(
                    {
                        "benchmark_id": benchmark_id,
                        "date": d,
                        "close": float(row.iloc[0]["close"]),
                        "price_basis": "close",
                        "source": "sectors",
                    }
                )
        if not rows:
            return pd.DataFrame(
                columns=["benchmark_id", "date", "close", "price_basis", "source"]
            )
        return pd.DataFrame(rows).sort_values("date").reset_index(drop=True)

    # ---- TaxonomyProvider ----

    def get_group_taxonomy(self) -> pd.DataFrame:
        rows = self.client.paginate(
            "/v2/companies/",
            {"limit": 30, "offset": 0},
            page_limit=self.max_pages,
        )
        if not rows:
            return pd.DataFrame(
                columns=["ticker", "group_id", "sector", "subsector", "industry", "sub_industry"]
            )
        df = normalize_companies(rows)
        return df[["ticker", "sector", "sub_sector", "industry", "sub_industry"]].rename(
            columns={"sector": "group_id", "sub_sector": "subsector"}
        )

    # ---- FreeFloatProvider ----

    def get_free_float(self, as_of: Optional[date] = None) -> pd.DataFrame:
        rows = self.client.paginate(
            "/v2/free-float/",
            {"limit": 30, "offset": 0},
            page_limit=self.max_pages,
        )
        return normalize_free_float(rows)

    # ---- FlowProvider ----

    def get_foreign_flow(
        self, ticker: str, *, start: date, end: date
    ) -> pd.DataFrame:
        if not ticker.upper().endswith(".JK"):
            ticker = f"{ticker}.JK"
        path = f"/v2/foreign-flow/{ticker}/"
        # Per docs the endpoint takes a date range, not a per-day list.
        params = {"start": start.isoformat(), "end": end.isoformat()}
        resp = self.client.get(path, params)
        payload = resp.payload if isinstance(resp.payload, Mapping) else {}
        return normalize_foreign_flow(payload)

    # ---- EventProvider ----

    def get_corporate_actions(self, ticker: str) -> dict[str, Any]:
        if not ticker.upper().endswith(".JK"):
            ticker = f"{ticker}.JK"
        path = f"/v2/company/corporate-actions/{ticker}/"
        resp = self.client.get(path, {})
        return resp.payload if isinstance(resp.payload, Mapping) else {}

    def get_suspensions(self, *, start: date, end: date) -> pd.DataFrame:
        rows = self.client.paginate(
            "/v2/suspensions/",
            {"start": start.isoformat(), "end": end.isoformat(), "limit": 30, "offset": 0},
            page_limit=self.max_pages,
        )
        return normalize_suspensions(rows)
