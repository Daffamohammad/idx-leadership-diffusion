"""Public-data prototype provider (yfinance) — keeps the existing
groundwork implementation, but now also satisfies the
`PriceCrossSectionProvider` and `BenchmarkProvider` capability
interfaces so the engine can use it as a uniform capability-aware
provider in tests and dev mode.
"""
from __future__ import annotations

import math
import time
from datetime import date
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from ..data import RawCache
from ..models import (
    BenchmarkObservation,
    PriceObservation,
    PriceBasis,
    ProviderName,
    ProviderMode,
    SecurityMasterEntry,
)
from ..utils import get_logger, load_yaml, project_root
from ..utils.errors import ProviderError
from .base import MarketDataProvider
from .capabilities import (
    BenchmarkProvider,
    PriceCrossSectionProvider,
    PriceHistoryProvider,
    SecurityMasterProvider,
    TaxonomyProvider,
)
from .ledger import RequestLedger

_log = get_logger(__name__)


class YFinanceProvider(
    MarketDataProvider,
    SecurityMasterProvider,
    PriceHistoryProvider,
    PriceCrossSectionProvider,
    BenchmarkProvider,
    TaxonomyProvider,
):
    """Concrete provider for Yahoo Finance public data (groundwork)."""

    name = "yfinance"
    mode = ProviderMode.PUBLIC_PROTOTYPE

    def __init__(
        self,
        *,
        universe_path: str | Path = "config/universe.yaml",
        request_timeout_seconds: int = 20,
        max_retries: int = 2,
        retry_backoff_seconds: float = 1.5,
        cache_ttl_hours: int = 12,
        ledger: Optional[RequestLedger] = None,
        cache: Optional[RawCache] = None,
    ) -> None:
        super().__init__(ledger=ledger)
        self.universe_path = project_root() / universe_path
        self.timeout = int(request_timeout_seconds)
        self.max_retries = max(0, int(max_retries))
        self.retry_backoff = float(retry_backoff_seconds)
        self.cache_ttl = int(cache_ttl_hours) * 3600
        self.cache = cache or RawCache()
        self._universe_config: dict[str, Any] = load_yaml(self.universe_path)
        self._ticker_meta: dict[str, dict[str, Any]] = {
            row["ticker"]: row for row in self._universe_config.get("universe", [])
        }
        # Mirrors SectorsProvider.history_diagnostics so the pipeline can
        # distinguish failed vs empty symbols without provider coupling.
        self.history_diagnostics: dict[str, Any] = {}

    # ---- contract methods ----

    def get_security_master(self) -> list[SecurityMasterEntry]:
        out: list[SecurityMasterEntry] = []
        for tkr, meta in self._ticker_meta.items():
            out.append(
                SecurityMasterEntry(
                    ticker=tkr,
                    vendor_ticker=tkr,
                    company_name=meta.get("company_name"),
                    exchange=meta.get("exchange", "IDX"),
                    country="ID",
                    sector=meta.get("sectors"),
                    subsector=meta.get("sub_sectors"),
                    industry=None,
                    subindustry=None,
                    group_id=meta.get("sectors"),
                    active=True,
                    benchmark_flag=False,
                    source=ProviderName.YFINANCE,
                    source_as_of=date.today(),
                )
            )
        return out

    def get_full_universe_close(self, as_of: date) -> pd.DataFrame:
        """Best-effort cross-section from the per-ticker cache.
        Returns whatever yfinance returned for the requested date; may
        be incomplete for thinly-traded names.
        """
        tickers = list(self._ticker_meta.keys())
        return self.get_price_history(tickers, start=as_of, end=as_of)

    def get_price_history(
        self, tickers: list[str], *, start: date, end: date
    ) -> pd.DataFrame:
        if not tickers:
            self.history_diagnostics = {
                "requested_symbols": 0,
                "failed_symbols": [],
                "empty_symbols": [],
                "window_capped_to_90_calendar_days": False,
            }
            return _empty_price_frame()
        frames: list[pd.DataFrame] = []
        failed_symbols: list[str] = []
        empty_symbols: list[str] = []
        for tkr in tickers:
            try:
                df = self._fetch_one(tkr, start=start, end=end)
            except Exception as e:  # noqa: BLE001
                _log.warning("yfinance_fetch_failed ticker=%s err=%s", tkr, e)
                failed_symbols.append(str(tkr).upper())
                continue
            if df.empty:
                empty_symbols.append(str(tkr).upper())
                continue
            frames.append(df)
        self.history_diagnostics = {
            "requested_symbols": len(tickers),
            "failed_symbols": failed_symbols,
            "empty_symbols": empty_symbols,
            "window_capped_to_90_calendar_days": False,
        }
        if not frames:
            return _empty_price_frame()
        return pd.concat(frames, ignore_index=True)

    def get_benchmark_history(
        self, benchmark_id: str, *, start: date, end: date
    ) -> pd.DataFrame:
        df = self._fetch_one(benchmark_id, start=start, end=end, is_benchmark=True)
        if df.empty:
            return pd.DataFrame(
                columns=["benchmark_id", "date", "close", "price_basis", "source"]
            )
        return pd.DataFrame(
            {
                "benchmark_id": benchmark_id,
                "date": pd.to_datetime(df["date"]).dt.date,
                "close": df["close"].astype(float).values,
                "price_basis": PriceBasis.CLOSE.value,
                "source": ProviderName.YFINANCE.value,
            }
        )

    def get_group_taxonomy(self) -> pd.DataFrame:
        rows = [
            {
                "ticker": tkr,
                "group_id": meta.get("sectors"),
                "sector": meta.get("sectors"),
                "subsector": meta.get("sub_sectors"),
            }
            for tkr, meta in self._ticker_meta.items()
        ]
        return pd.DataFrame(rows, columns=["ticker", "group_id", "sector", "subsector"])

    # ---- internals (unchanged from groundwork) ----

    def _fetch_one(self, ticker: str, *, start: date, end: date, is_benchmark: bool = False) -> pd.DataFrame:
        cache_key = f"yfinance:{ticker}:{start.isoformat()}:{end.isoformat()}:bench={is_benchmark}"
        cached = self.cache.get(cache_key, ttl_seconds=self.cache_ttl)
        if cached is not None:
            self.ledger.record(
                provider=self.name,
                endpoint="price_history" if not is_benchmark else "benchmark_history",
                request_type="single",
                parameters={"ticker": ticker, "start": start, "end": end, "is_benchmark": is_benchmark},
                cache_hit=True,
                status="ok",
                rows_returned=len(cached.get("rows", [])),
                elapsed_ms=0.0,
            )
            return _payload_to_frame(cached, ticker=ticker)

        t0 = time.time()
        rows = self._call_yfinance_with_retry(ticker, start=start, end=end)
        elapsed = (time.time() - t0) * 1000.0
        if rows is None:
            self.ledger.record(
                provider=self.name,
                endpoint="price_history" if not is_benchmark else "benchmark_history",
                request_type="single",
                parameters={
                    "ticker": ticker,
                    "start": start,
                    "end": end,
                    "is_benchmark": is_benchmark,
                },
                cache_hit=False,
                status="failed",
                rows_returned=0,
                elapsed_ms=elapsed,
                error="yfinance returned no data",
            )
            raise ProviderError(f"yfinance returned no data for {ticker}")

        self.cache.set(cache_key, {"rows": rows})
        self.ledger.record(
            provider=self.name,
            endpoint="price_history" if not is_benchmark else "benchmark_history",
            request_type="single",
            parameters={"ticker": ticker, "start": start, "end": end, "is_benchmark": is_benchmark},
            cache_hit=False,
            status="ok",
            rows_returned=len(rows),
            elapsed_ms=elapsed,
        )
        return _payload_to_frame({"rows": rows}, ticker=ticker)

    def _call_yfinance_with_retry(
        self, ticker: str, *, start: date, end: date
    ) -> Optional[list[dict[str, Any]]]:
        try:
            import yfinance as yf  # type: ignore
        except ImportError as e:
            raise ProviderError("yfinance not installed") from e

        last_err: Optional[Exception] = None
        for attempt in range(self.max_retries + 1):
            try:
                df = yf.download(
                    tickers=ticker,
                    start=start.isoformat(),
                    end=(pd.Timestamp(end) + pd.Timedelta(days=1)).date().isoformat(),
                    progress=False,
                    auto_adjust=False,
                    threads=False,
                    timeout=self.timeout,
                )
                if df is None or df.empty:
                    return None

                close = _select_yfinance_column(df, "Close")
                adjusted_close = _select_yfinance_column(df, "Adj Close")
                volume = _select_yfinance_column(df, "Volume")
                if close is None or adjusted_close is None:
                    raise ProviderError(
                        f"yfinance response for {ticker} is missing Close or Adj Close"
                    )

                rows: list[dict[str, Any]] = []
                for idx in df.index:
                    timestamp = pd.Timestamp(idx)
                    if timestamp.tzinfo is not None:
                        timestamp = timestamp.tz_convert(None)
                    row_date = timestamp.date()
                    if row_date < start or row_date > end:
                        continue

                    close_value = _finite_float(close.loc[idx])
                    adjusted_value = _finite_float(adjusted_close.loc[idx])
                    if close_value is None or adjusted_value is None:
                        continue
                    if close_value <= 0 or adjusted_value <= 0:
                        continue

                    volume_value = (
                        _finite_int(volume.loc[idx])
                        if volume is not None
                        else None
                    )
                    rows.append(
                        {
                            "date": row_date.isoformat(),
                            "close": close_value,
                            "adjusted_close": adjusted_value,
                            "volume": volume_value,
                        }
                    )
                return rows or None
            except Exception as e:  # noqa: BLE001
                last_err = e
                if attempt < self.max_retries:
                    time.sleep(self.retry_backoff * (attempt + 1))
                    continue
                break
        if last_err is not None:
            _log.warning("yfinance_attempts_exhausted ticker=%s err=%s", ticker, last_err)
        return None


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


def _payload_to_frame(
    payload: dict[str, Any], *, ticker: str | None = None
) -> pd.DataFrame:
    rows = payload.get("rows", [])
    if not rows:
        return _empty_price_frame()
    df = pd.DataFrame(rows)
    if "ticker" not in df.columns:
        if ticker is None:
            raise ProviderError("yfinance payload is missing ticker identity")
        df["ticker"] = ticker
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date
    df = df[df["date"].notna()].copy()
    for column in ("close", "adjusted_close", "market_cap"):
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")
    df["currency"] = "IDR"
    if "price_basis" not in df.columns:
        df["price_basis"] = PriceBasis.ADJUSTED_CLOSE.value
    if "source" not in df.columns:
        df["source"] = ProviderName.YFINANCE.value
    if "market_cap" not in df.columns:
        df["market_cap"] = None
    return df[
        [
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
    ]


def _select_yfinance_column(
    frame: pd.DataFrame, field_name: str
) -> pd.Series | None:
    """Select a yfinance field across flat and multi-index responses.

    yfinance has returned both Close, Ticker and Ticker, Close multi-index
    layouts across releases. Matching the field at either level keeps the
    provider boundary stable without leaking vendor columns into the
    canonical frame.
    """
    wanted = field_name.casefold()
    matches: list[int] = []
    for position, column in enumerate(frame.columns):
        parts = column if isinstance(column, tuple) else (column,)
        if any(str(part).strip().casefold() == wanted for part in parts):
            matches.append(position)
    if not matches:
        return None
    selected = frame.iloc[:, matches[0]]
    if isinstance(selected, pd.DataFrame):
        selected = selected.iloc[:, 0]
    return selected


def _finite_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _finite_int(value: Any) -> int | None:
    number = _finite_float(value)
    if number is None:
        return None
    return int(number)
