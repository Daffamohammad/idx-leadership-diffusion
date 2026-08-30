"""Sectors v2 provider.

Sectors is the primary source for the live IDX universe, security taxonomy,
security prices, and the native IHSG series. The provider keeps vendor details
behind the capability interfaces and records explicit diagnostics for missing
taxonomy, duplicate identifiers, unsupported instrument classification, stale
prices, and failed history calls.

The live price path uses the documented per-symbol ``/v2/daily/{symbol}/``
route. Reconstructing market history from one full-universe close request per
day would be materially more expensive and is retained only for the offline
Sectors-shaped fixture and compatibility tests.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
import re
from typing import Any, Mapping, Optional

import pandas as pd

from ..models import ProviderMode, ProviderName, SecurityMasterEntry
from ..utils import get_logger
from ..utils.errors import CreditBudgetExceeded, ProviderError
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
    normalize_close_cross_section,
    normalize_companies,
    normalize_daily_history,
    normalize_foreign_flow,
    normalize_free_float,
    normalize_index_daily,
    normalize_suspensions,
)

_log = get_logger(__name__)

_TAXONOMY_FIELDS = ("sector", "sub_sector", "industry", "sub_industry")
_TAXONOMY_WHERE = (
    "sector IS NOT NULL and sub_sector IS NOT NULL and "
    "industry IS NOT NULL and sub_industry IS NOT NULL and "
    "listing_board IS NOT NULL"
)

_NON_COMMON_MARKERS = re.compile(
    r"(?:[-_.](?:W|R|RT|RIGHTS?|WARRANTS?)|(?:RIGHTS?|WARRANTS?|ETF|PREFERRED))$",
    re.IGNORECASE,
)


def _optional_value(value: Any) -> Any:
    """Convert pandas/numpy missing scalars to the canonical optional value."""

    if value is None:
        return None
    try:
        return None if pd.isna(value) else value
    except (TypeError, ValueError):
        return value


def _as_date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    try:
        return pd.Timestamp(value).date()
    except (TypeError, ValueError):
        return None


def _as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if pd.notna(number) else None


def _rows_from_payload(payload: Any) -> list[Mapping[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, Mapping)]
    if isinstance(payload, Mapping):
        for key in ("results", "data", "items", "rows"):
            value = payload.get(key)
            if isinstance(value, list):
                return [row for row in value if isinstance(row, Mapping)]
    return []


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
    """Sectors v2 implementation of the market-data capability set."""

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
        timeout: int = SectorsClient.DEFAULT_TIMEOUT_SECONDS,
        max_retries: int = SectorsClient.DEFAULT_MAX_RETRIES,
        backoff_seconds: float = SectorsClient.DEFAULT_BACKOFF_SECONDS,
        cache_ttl_seconds: int | None = 60 * 60,
        history_workers: int = 4,
        min_request_interval_seconds: float = 0.0,
        max_estimated_credits: float | None = SectorsClient.DEFAULT_MAX_ESTIMATED_CREDITS,
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
        self.history_workers = max(1, int(history_workers))
        self.source_as_of: date | None = None
        self.security_master_diagnostics: dict[str, Any] = {}
        self.close_pagination_diagnostics: dict[str, Any] = {}
        self.history_diagnostics: dict[str, Any] = {}
        self.client = client or SectorsClient(
            api_key=api_key,
            base_url=self.base_url,
            ledger=self.ledger,
            allow_live=allow_live,
            mode=mode,
            force_refresh=force_refresh,
            validate_contracts=True,
            timeout=timeout,
            max_retries=max_retries,
            backoff_seconds=backoff_seconds,
            cache_ttl_seconds=cache_ttl_seconds,
            min_request_interval_seconds=min_request_interval_seconds,
            max_estimated_credits=max_estimated_credits,
        )

    # ---- SecurityMasterProvider -----------------------------------------

    def set_source_as_of(self, as_of: date | None) -> None:
        """Set the market date attached to subsequent master rows."""

        self.source_as_of = as_of

    def get_security_master(self) -> list[SecurityMasterEntry]:
        # Use a tautological structured query for the identity population. The
        # Sectors docs price structured screener pages at one credit and cap
        # them at 200 rows. A separate complete-taxonomy query is merged below
        # so missing taxonomy remains visible without relying on the
        # undocumented price of the unfiltered listing form.
        rows = self.client.paginate(
            "/v2/companies/",
            {
                "where": "symbol IS NOT NULL",
                "order_by": "symbol",
                "limit": 200,
                "offset": 0,
            },
            page_limit=self.max_pages,
        )
        identity_pagination = dict(self.client.last_pagination_diagnostics)
        base = normalize_companies(rows)
        raw_count = len(base)
        duplicate_tickers = int(base.duplicated("ticker").sum()) if not base.empty else 0
        base = base.drop_duplicates("ticker", keep="first") if not base.empty else base

        taxonomy_rows: list[Any] = []
        if not base.empty and not _has_complete_taxonomy(base):
            taxonomy_rows = self.client.paginate(
                "/v2/companies/",
                {
                    "where": _TAXONOMY_WHERE,
                    "include_query_values": "true",
                    "limit": 200,
                    "offset": 0,
                },
                page_limit=self.max_pages,
            )
            taxonomy_pagination = dict(self.client.last_pagination_diagnostics)
            taxonomy = normalize_companies(taxonomy_rows)
            taxonomy = (
                taxonomy.drop_duplicates("ticker", keep="first")
                if not taxonomy.empty
                else taxonomy
            )
            if not taxonomy.empty:
                taxonomy_by_ticker = taxonomy.set_index("ticker")
                for column in (*_TAXONOMY_FIELDS, "listing_board", "listing_status"):
                    if column not in base.columns:
                        base[column] = None
                    mapped = base["ticker"].map(taxonomy_by_ticker[column])
                    base[column] = base[column].where(base[column].notna(), mapped)
        else:
            taxonomy_pagination = None

        missing_taxonomy = int(
            base[list(_TAXONOMY_FIELDS)].isna().any(axis=1).sum()
        ) if not base.empty else 0
        missing_board = int(base["listing_board"].isna().sum()) if not base.empty else 0
        non_common = 0
        unverified_instrument = 0
        out: list[SecurityMasterEntry] = []
        for _, row in base.iterrows():
            common_status = _classify_common_equity(row)
            if common_status == "NON_COMMON_EQUITY":
                non_common += 1
            if common_status == "UNVERIFIED_COMPANY_LISTING":
                unverified_instrument += 1
            listing_board = _optional_value(row.get("listing_board"))
            # The fixture set predates board metadata and historically relied
            # on the model default. Live rows keep a missing board explicit.
            if listing_board is None and self.mode is ProviderMode.SECTORS_FIXTURE:
                listing_board = "Main"
            out.append(
                SecurityMasterEntry(
                    ticker=str(row["ticker"]),
                    vendor_ticker=str(row.get("vendor_ticker") or row["ticker"]),
                    security_id=_optional_value(row.get("security_id")),
                    company_name=_optional_value(row.get("company_name")),
                    exchange="IDX",
                    country="ID",
                    sector=_optional_value(row.get("sector")),
                    subsector=_optional_value(row.get("sub_sector")),
                    industry=_optional_value(row.get("industry")),
                    subindustry=_optional_value(row.get("sub_industry")),
                    group_id=_optional_value(row.get("sector")),
                    listing_status=_optional_value(row.get("listing_status")),
                    instrument_type=_optional_value(row.get("instrument_type")),
                    common_equity_status=common_status,
                    listing_board=listing_board,
                    active=_active_listing(row.get("listing_status")),
                    benchmark_flag=False,
                    listing_date=_as_date(row.get("listing_date")),
                    market_cap=_as_float(row.get("market_cap")),
                    source=(
                        ProviderName.SECTORS
                        if self.mode is ProviderMode.SECTORS_LIVE
                        else ProviderName.FIXTURE
                    ),
                    source_as_of=self.source_as_of or date.today(),
                )
            )

        self.security_master_diagnostics = {
            "raw_rows": raw_count,
            "unique_rows": len(out),
            "duplicate_ticker_rows": duplicate_tickers,
            "taxonomy_query_rows": len(taxonomy_rows),
            "missing_taxonomy_rows": missing_taxonomy,
            "missing_listing_board_rows": missing_board,
            "non_common_equity_rows_flagged": non_common,
            "instrument_classification_unverified_rows": unverified_instrument,
            "taxonomy_source": (
                "Sectors /v2/companies structured where + include_query_values"
                if taxonomy_rows
                else "direct company response fields"
            ),
            "instrument_classification_note": (
                "Sectors company response did not expose an instrument-type field; "
                "obvious suffix/name markers are flagged and remaining company rows "
                "are explicitly UNVERIFIED_COMPANY_LISTING."
            ),
            "pagination": [
                item
                for item in (identity_pagination, taxonomy_pagination)
                if item is not None
            ],
            "pagination_capped": any(
                bool(item.get("capped_by_max_pages"))
                for item in (identity_pagination, taxonomy_pagination)
                if item is not None
            ),
            "pagination_completeness": (
                "PARTIAL"
                if any(
                    bool(item.get("capped_by_max_pages"))
                    for item in (identity_pagination, taxonomy_pagination)
                    if item is not None
                )
                else (
                    "COMPLETE"
                    if all(
                        item.get("completeness") == "COMPLETE"
                        for item in (identity_pagination, taxonomy_pagination)
                        if item is not None
                    )
                    else "UNKNOWN"
                )
            ),
        }
        return out

    # ---- PriceCrossSectionProvider --------------------------------------

    def get_full_universe_close(self, as_of: date | None) -> pd.DataFrame:
        params: dict[str, Any] = {"limit": 30, "offset": 0}
        if as_of is not None:
            params["date"] = as_of.isoformat()
        rows = self.client.paginate(
            "/v2/close/", params, page_limit=self.max_pages
        )
        self.close_pagination_diagnostics = dict(self.client.last_pagination_diagnostics)
        frame = normalize_close_cross_section(rows, as_of=as_of, source=self.name)
        if not frame.empty and self.source_as_of is None:
            self.source_as_of = pd.to_datetime(frame["date"]).max().date()
        return frame

    def get_latest_market_close(self) -> pd.DataFrame:
        """Fetch one page of the latest close to resolve the market date.

        The Sectors close endpoint returns the same market date on every
        page. Date discovery therefore must not walk the entire cross-section;
        callers that explicitly need every close row should use
        ``get_full_universe_close(as_of)``.
        """

        params: dict[str, Any] = {"limit": 30, "offset": 0}
        rows = self.client.paginate(
            "/v2/close/", params, page_limit=1
        )
        self.close_pagination_diagnostics = dict(self.client.last_pagination_diagnostics)
        frame = normalize_close_cross_section(rows, as_of=None, source=self.name)
        if not frame.empty and self.source_as_of is None:
            self.source_as_of = pd.to_datetime(frame["date"]).max().date()
        return frame

    def get_latest_trading_date(self) -> date | None:
        frame = self.get_latest_market_close()
        if frame.empty or "date" not in frame.columns:
            return None
        return pd.to_datetime(frame["date"], errors="coerce").dropna().max().date()

    # ---- PriceHistoryProvider -------------------------------------------

    def get_price_history(
        self,
        tickers: list[str],
        *,
        start: date,
        end: date,
        max_symbols: int | None = None,
    ) -> pd.DataFrame:
        """Return canonical daily history for the requested securities.

        Live mode uses one bounded 90-calendar-day call per ticker and keeps
        failed/empty symbols in ``history_diagnostics``. The compatibility
        cross-section route remains available to the fixture provider and to
        tests that monkeypatch ``get_full_universe_close``.
        """

        canonical = list(dict.fromkeys(str(ticker) for ticker in tickers if ticker))
        if max_symbols is not None:
            if max_symbols < 1:
                raise ValueError("max_symbols must be at least 1")
            canonical = canonical[:max_symbols]
        if self.mode is ProviderMode.SECTORS_FIXTURE or "get_full_universe_close" in self.__dict__:
            return self._get_cross_section_history(canonical, start=start, end=end)
        if end < start:
            raise ValueError("history end must be on or after start")

        # Sectors documents a 90-day maximum for the daily endpoint. Use the
        # latest 90 calendar days rather than silently issuing unsupported
        # requests for longer windows.
        # A 90-calendar-day inclusive window is the largest documented daily
        # request and gives the return engine the extra observation required
        # for a 60-trading-day return when no market holiday intervenes.
        effective_start = max(start, end - timedelta(days=90))
        self.history_diagnostics = {
            "requested_symbols": len(canonical),
            "effective_start": effective_start.isoformat(),
            "requested_start": start.isoformat(),
            "end": end.isoformat(),
            "window_capped_to_90_calendar_days": effective_start != start,
            "failed_symbols": [],
            "empty_symbols": [],
            "duplicate_symbol_date_rows": 0,
        }
        if not canonical:
            return _empty_price_frame()

        def fetch(symbol: str) -> tuple[str, pd.DataFrame, str | None]:
            try:
                response = self.client.get(
                    f"/v2/daily/{symbol}/",
                    {
                        "start": effective_start.isoformat(),
                        "end": end.isoformat(),
                    },
                )
                frame = normalize_daily_history(response.payload, source=self.name)
                frame = frame[frame["ticker"] == symbol]
                if frame.empty:
                    return symbol, frame, "empty"
                return symbol, frame, None
            except CreditBudgetExceeded:
                # A paid-request ceiling is a run-level stop condition. Do not
                # turn it into a missing-symbol diagnostic and continue with a
                # partial snapshot after the budget is exhausted.
                raise
            except ProviderError as exc:
                return symbol, _empty_price_frame(), str(exc)[:300]

        frames: list[pd.DataFrame] = []
        max_workers = min(self.history_workers, len(canonical))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(fetch, symbol) for symbol in canonical]
            for index, future in enumerate(as_completed(futures), start=1):
                symbol, frame, error = future.result()
                if error == "empty":
                    self.history_diagnostics["empty_symbols"].append(symbol)
                elif error is not None:
                    self.history_diagnostics["failed_symbols"].append(
                        {"ticker": symbol, "error": error}
                    )
                elif not frame.empty:
                    frames.append(frame)
                if index % 100 == 0 or index == len(canonical):
                    _log.info("sectors_daily_history progress=%s/%s", index, len(canonical))

        # Conservative 429 calibration: calculate 429 failures AFTER worker
        # results populate history_diagnostics. If more than 50% of symbols
        # failed with 429, probe one to check if the rate limit persists.
        rate_limit_failures = [
            f for f in (self.history_diagnostics.get("failed_symbols") or [])
            if "status=429" in str(f.get("error", ""))
        ]
        if rate_limit_failures and len(rate_limit_failures) > len(canonical) // 2:
            probe_symbol = canonical[0]
            try:
                probe_response = self.client.get(
                    f"/v2/daily/{probe_symbol}/",
                    {
                        "start": effective_start.isoformat(),
                        "end": end.isoformat(),
                    },
                )
                # If the probe still returns 429, stop and report BLOCKED
                if probe_response.status == 429:
                    self.history_diagnostics["blocked"] = True
                    self.history_diagnostics["blocked_reason"] = (
                        "safe single-symbol probe still returns 429; "
                        "stop and report BLOCKED"
                    )
                    _log.warning(
                        "sectors_429_calibration BLOCKED probe=%s", probe_symbol
                    )
                    raise ProviderError(
                        "SECTORS_LIVE 429 calibration: safe probe still rate-limited"
                    )
            except CreditBudgetExceeded:
                raise
            except ProviderError as exc:
                if "429" in str(exc):
                    self.history_diagnostics["blocked"] = True
                    raise ProviderError(
                        "SECTORS_LIVE 429 calibration: safe probe still rate-limited"
                    )

        if not frames:
            self.history_diagnostics["returned_symbols"] = 0
            return _empty_price_frame()
        history = pd.concat(frames, ignore_index=True)
        duplicates = int(history.duplicated(["ticker", "date"]).sum())
        self.history_diagnostics["duplicate_symbol_date_rows"] = duplicates
        self.history_diagnostics["returned_symbols"] = int(history["ticker"].nunique())
        self.history_diagnostics["returned_rows"] = int(len(history))
        return history.drop_duplicates(["ticker", "date"], keep="last").sort_values(
            ["ticker", "date"]
        ).reset_index(drop=True)

    def _get_cross_section_history(
        self, tickers: list[str], *, start: date, end: date
    ) -> pd.DataFrame:
        dates = pd.bdate_range(start=start, end=end)
        frames: list[pd.DataFrame] = []
        wanted = set(tickers)
        for timestamp in dates:
            frame = self.get_full_universe_close(timestamp.date())
            if not frame.empty:
                frames.append(frame[frame["ticker"].isin(wanted)])
        if not frames:
            return _empty_price_frame()
        return pd.concat(frames, ignore_index=True)

    # ---- BenchmarkProvider ----------------------------------------------

    def get_benchmark_history(
        self, benchmark_id: str, *, start: date, end: date
    ) -> pd.DataFrame:
        benchmark_key = (benchmark_id or "").strip().upper()
        if benchmark_key in {"IHSG", "IHSG.JK", "^JKSE", "^JKSE.JK"}:
            native_code = "ihsg"
        else:
            native_code = benchmark_key.lower().removesuffix(".jk")

        if self.mode is ProviderMode.SECTORS_FIXTURE or "get_full_universe_close" in self.__dict__:
            # Fixture compatibility: the synthetic route models IHSG as a
            # cross-section row, while live Sectors has a native index route.
            dates = pd.bdate_range(start=start, end=end)
            rows: list[dict[str, Any]] = []
            for timestamp in dates:
                frame = self.get_full_universe_close(timestamp.date())
                row = frame[frame["ticker"] == "IHSG.JK"]
                if not row.empty:
                    rows.append(
                        {
                            "benchmark_id": benchmark_id,
                            "index_code": "IHSG",
                            "date": timestamp.date(),
                            "close": float(row.iloc[0]["close"]),
                            "price_basis": "close",
                            "source": self.name,
                        }
                    )
            return pd.DataFrame(
                rows,
                columns=[
                    "benchmark_id",
                    "index_code",
                    "date",
                    "close",
                    "price_basis",
                    "source",
                ],
            )

        effective_start = max(start, end - timedelta(days=90))
        response = self.client.get(
            f"/v2/index-daily/{native_code}/",
            {"start": effective_start.isoformat(), "end": end.isoformat()},
        )
        frame = normalize_index_daily(
            response.payload, benchmark_id=benchmark_id, source=self.name
        )
        if frame.empty:
            return frame
        frame = frame.drop_duplicates("date", keep="last").sort_values("date")
        self.source_as_of = pd.to_datetime(frame["date"]).max().date()
        return frame.reset_index(drop=True)

    # ---- TaxonomyProvider ------------------------------------------------

    def get_group_taxonomy(self) -> pd.DataFrame:
        master = self.get_security_master()
        rows = [
            {
                "ticker": item.ticker,
                "group_id": item.group_id,
                "sector": item.sector,
                "subsector": item.subsector,
                "industry": item.industry,
                "sub_industry": item.subindustry,
            }
            for item in master
        ]
        return pd.DataFrame(
            rows,
            columns=["ticker", "group_id", "sector", "subsector", "industry", "sub_industry"],
        )

    # ---- FreeFloatProvider ----------------------------------------------

    def get_free_float(self, as_of: Optional[date] = None) -> pd.DataFrame:
        rows = self.client.paginate(
            "/v2/free-float/",
            {"limit": 100, "offset": 0},
            page_limit=self.max_pages,
        )
        return normalize_free_float(rows)

    # ---- FlowProvider ----------------------------------------------------

    def get_foreign_flow(
        self, ticker: str, *, start: date, end: date
    ) -> pd.DataFrame:
        symbol = ticker if ticker.upper().endswith(".JK") else f"{ticker}.JK"
        response = self.client.get(
            f"/v2/foreign-flow/{symbol}/",
            {"start": start.isoformat(), "end": end.isoformat()},
        )
        payload = response.payload if isinstance(response.payload, Mapping) else {}
        return normalize_foreign_flow(payload)

    # ---- EventProvider ---------------------------------------------------

    def get_corporate_actions(self, ticker: str) -> dict[str, Any]:
        symbol = ticker if ticker.upper().endswith(".JK") else f"{ticker}.JK"
        response = self.client.get(f"/v2/company/corporate-actions/{symbol}/", {})
        return response.payload if isinstance(response.payload, Mapping) else {}

    def get_suspensions(self, *, start: date, end: date) -> pd.DataFrame:
        rows = self.client.paginate(
            "/v2/suspensions/",
            {
                "start": start.isoformat(),
                "end": end.isoformat(),
                "limit": 200,
                "offset": 0,
            },
            page_limit=self.max_pages,
        )
        return normalize_suspensions(rows)


def _has_complete_taxonomy(frame: pd.DataFrame) -> bool:
    return not frame.empty and frame[list(_TAXONOMY_FIELDS)].notna().all(axis=1).all()


def _active_listing(value: Any) -> bool:
    status = str(value or "").strip().lower()
    return status not in {"delisted", "inactive", "suspended"}


def _classify_common_equity(row: pd.Series) -> str:
    explicit = str(row.get("instrument_type") or "").strip().lower()
    if explicit:
        if any(marker in explicit for marker in ("warrant", "right", "etf", "fund", "preferred")):
            return "NON_COMMON_EQUITY"
        if any(marker in explicit for marker in ("common", "equity", "stock", "share")):
            return "COMMON_EQUITY"
    ticker = str(row.get("ticker") or "")
    name = str(row.get("company_name") or "")
    if _NON_COMMON_MARKERS.search(ticker.removesuffix(".JK")) or re.search(
        r"\b(?:warrant|rights?|etf|preferred)\b", name, re.IGNORECASE
    ):
        return "NON_COMMON_EQUITY"
    return "UNVERIFIED_COMPANY_LISTING"


def _empty_price_frame() -> pd.DataFrame:
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


__all__ = ["SectorsProvider"]
