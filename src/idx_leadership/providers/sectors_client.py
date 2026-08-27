"""Thin Sectors v2 HTTP client.

Responsibilities
----------------
* Auth (single header, no Bearer prefix — confirmed from official docs).
* Timeouts.
* Bounded retries for transient errors (5xx, 429) with linear backoff.
* Pagination following the documented `offset`/`limit` cursor shape.
* Request-ledger integration (per-call record with endpoint, parameters hash,
  status, rows, elapsed, estimated_credit_cost, observed credit delta where
  available).
* Raw response cache (TTL-controlled, JSON) — see `RawCache`.
* Pagination collector: `paginate(path, params, ...)`.

Out of scope
------------
* No intelligent credit-economics logic — that lives in the request ledger and
  is enforced upstream by callers.
* No opaque SDK behavior — every method is thin and returns the documented shape.
* No v1 endpoints — v1 was retired 2026-05-11 (HTTP 410 Gone).
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional, Sequence

from ..models import ProviderMode
from ..utils import get_logger, project_root
from ..utils.errors import ProviderError
from .ledger import RequestLedger
from ..data import RawCache

_log = get_logger(__name__)


# Per-endpoint cost table — sourced directly from the Sectors v2 docs.
# Update by re-reading docs.sectors.app; do NOT extrapolate.
DOCUMENTED_COST = {
    "/v2/close/": "per_page",
    "/v2/free-float/": "per_100_companies",
    "/v2/foreign-flow/{symbol}/": "per_call_1",
    "/v2/company/corporate-actions/{symbol}/": "per_call_1",
    "/v2/suspensions/": "per_call_1",
    "/v2/companies/": "unknown_verify",
    "/v2/company/report/{symbol}/": "unknown_verify",
}


def _estimated_credit_cost(endpoint: str, response_payload: Mapping[str, Any] | list | None) -> float:
    """Best-effort credit cost from documented per-endpoint rules.

    Returns 0.0 for `unknown_verify` so the ledger does not invent numbers.
    """
    rule = DOCUMENTED_COST.get(endpoint, "unknown_verify")
    if rule == "unknown_verify":
        return 0.0
    if rule == "per_call_1":
        return 1.0
    if rule == "per_page":
        return 1.0
    if rule == "per_100_companies":
        if isinstance(response_payload, list):
            return max(1.0, (len(response_payload) + 99) // 100)
        if isinstance(response_payload, Mapping) and "results" in response_payload:
            return max(1.0, (len(response_payload["results"]) + 99) // 100)
        return 1.0
    return 0.0


@dataclass
class SectorsResponse:
    payload: Any
    status: int
    endpoint: str
    params: dict
    elapsed_ms: float
    rows: int = 0
    cache_hit: bool = False
    estimated_credit_cost: float = 0.0
    credit_after: Optional[float] = None
    credit_before: Optional[float] = None
    observed_credit_delta: Optional[float] = None
    request_id: Optional[str] = None


class SectorsClient:
    """HTTP client for Sectors v2.

    No requests outside of this module.
    """

    # Keep the API root separate from endpoint paths.  Provider methods use
    # the documented `/v2/...` paths, so including `/v2` in this root would
    # produce the invalid `/v2/v2/...` URL.
    BASE_URL = "https://api.sectors.app"
    DEFAULT_TIMEOUT_SECONDS = 30
    DEFAULT_MAX_RETRIES = 2
    DEFAULT_BACKOFF_SECONDS = 1.5

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = BASE_URL,
        ledger: Optional[RequestLedger] = None,
        cache: Optional[RawCache] = None,
        timeout: int = DEFAULT_TIMEOUT_SECONDS,
        max_retries: int = DEFAULT_MAX_RETRIES,
        backoff_seconds: float = DEFAULT_BACKOFF_SECONDS,
        transport: Any = None,
        allow_live: bool = False,
        mode: ProviderMode | str = ProviderMode.SECTORS_LIVE,
        force_refresh: bool = False,
        validate_contracts: bool = False,
    ) -> None:
        self.api_key = api_key or ""
        # Accept both the API root and the historical ``.../v2`` spelling
        # while ensuring endpoint paths are prefixed exactly once.
        normalized_base_url = (base_url or self.BASE_URL).rstrip("/")
        if normalized_base_url.endswith("/v2"):
            normalized_base_url = normalized_base_url[:-3].rstrip("/")
        self.base_url = normalized_base_url
        self.ledger = ledger or RequestLedger()
        self.cache = cache or RawCache()
        self.timeout = int(timeout)
        self.max_retries = int(max_retries)
        self.backoff = float(backoff_seconds)
        # Pluggable transport for tests; default is urllib.
        self._transport = transport
        self._allow_live = bool(allow_live)
        try:
            self.mode = mode if isinstance(mode, ProviderMode) else ProviderMode(str(mode))
        except ValueError as exc:
            raise ProviderError(f"Unsupported Sectors client mode: {mode}") from exc
        if self.mode not in {ProviderMode.SECTORS_FIXTURE, ProviderMode.SECTORS_LIVE}:
            raise ProviderError(f"SectorsClient cannot run in mode {self.mode.value}")
        if self.mode is ProviderMode.SECTORS_LIVE and not self.api_key.strip():
            # Construction is permitted for dry-run planning; any request fails
            # in _authorize_request before cache or transport access.
            _log.warning("sectors_client_init without_api_key allow_live=%s", allow_live)
        if self.mode is ProviderMode.SECTORS_FIXTURE and self._transport is None:
            raise ProviderError("SECTORS_FIXTURE requires an injected offline transport")
        self.force_refresh = bool(force_refresh)
        self.validate_contracts = bool(validate_contracts)

    # ---- public surface ----

    def get(self, path: str, params: Optional[Mapping[str, Any]] = None, *, use_cache: bool = True) -> SectorsResponse:
        params = dict(params or {})
        return self._request(
            "GET", path, params=params, use_cache=bool(use_cache and not self.force_refresh)
        )

    def paginate(
        self,
        path: str,
        params: Optional[Mapping[str, Any]] = None,
        *,
        page_limit: Optional[int] = None,
        max_rows: Optional[int] = None,
        use_cache: bool = True,
    ) -> list[Any]:
        """Walk all pages using the documented offset/limit cursor.

        `page_limit` caps the number of pages (safety; default = no cap).
        `max_rows` caps the total number of result rows collected.
        """
        collected: list[Any] = []
        offset = 0
        limit = 30
        page = 0
        while True:
            page_params = dict(params or {})
            page_params.update({"offset": offset, "limit": limit})
            resp = self.get(path, page_params, use_cache=use_cache)
            payload = resp.payload
            if isinstance(payload, Mapping) and "results" in payload:
                results = list(payload.get("results") or [])
            elif isinstance(payload, list):
                results = list(payload)
            else:
                # Non-paginated single-object endpoint (e.g. /v2/foreign-flow/{symbol}/)
                results = [payload]
            collected.extend(results)
            if max_rows is not None and len(collected) >= max_rows:
                collected = collected[:max_rows]
                break
            page += 1
            if page_limit is not None and page >= page_limit:
                break
            # Stop if the page was short or pagination metadata says no more.
            if isinstance(payload, Mapping) and "pagination" in payload:
                pg = payload["pagination"]
                if not pg.get("has_next"):
                    break
                offset = pg.get("next_offset") or (offset + limit)
            else:
                # No pagination metadata — single-page response.
                break
        return collected

    # ---- internals ----

    def _request(self, method: str, path: str, *, params: dict, use_cache: bool) -> SectorsResponse:
        # Mode/credential authorization happens before cache lookup. A paid
        # response on disk is not permission to present a run as SECTORS_LIVE.
        provider_label = self._authorize_request(path)
        if path.startswith("http"):
            url = path
        else:
            url = f"{self.base_url}{path}"
        cache_key = self._cache_key(method, url, params)
        if use_cache:
            cached = self.cache.get(cache_key, ttl_seconds=60 * 60)
            if cached is not None:
                self._validate_payload(path, cached, params)
                self.ledger.record(
                    provider=provider_label,
                    endpoint=path,
                    request_type=method,
                    parameters=params,
                    cache_hit=True,
                    status="ok",
                    rows_returned=_row_count(cached),
                    elapsed_ms=0.0,
                    estimated_credit_cost=0.0,
                )
                return SectorsResponse(
                    payload=cached,
                    status=200,
                    endpoint=path,
                    params=params,
                    elapsed_ms=0.0,
                    rows=_row_count(cached),
                    cache_hit=True,
                )

        t0 = time.time()
        attempt = 0
        last_exc: Optional[Exception] = None
        while attempt <= self.max_retries:
            try:
                status, payload = self._do_http(method, url, params)
                elapsed = (time.time() - t0) * 1000.0
                if status == 429 or 500 <= status < 600:
                    # Transient — backoff and retry.
                    if attempt < self.max_retries:
                        time.sleep(self.backoff * (attempt + 1))
                        attempt += 1
                        continue
                    raise ProviderError(f"sectors transient status={status} endpoint={path}")
                if status >= 400:
                    raise ProviderError(
                        f"sectors client error status={status} endpoint={path} body={json.dumps(payload)[:300]}"
                    )
                self._validate_payload(path, payload, params)
                # Success.
                if use_cache and isinstance(payload, (dict, list)):
                    self.cache.set(cache_key, payload)
                est = (
                    _estimated_credit_cost(path, payload)
                    if self.mode is ProviderMode.SECTORS_LIVE
                    else 0.0
                )
                self.ledger.record(
                    provider=provider_label,
                    endpoint=path,
                    request_type=method,
                    parameters=params,
                    cache_hit=False,
                    status="ok",
                    rows_returned=_row_count(payload),
                    elapsed_ms=elapsed,
                    estimated_credit_cost=est,
                )
                return SectorsResponse(
                    payload=payload,
                    status=status,
                    endpoint=path,
                    params=params,
                    elapsed_ms=elapsed,
                    rows=_row_count(payload),
                    cache_hit=False,
                    estimated_credit_cost=est,
                )
            except ProviderError:
                raise
            except Exception as e:  # noqa: BLE001
                last_exc = e
                if attempt < self.max_retries:
                    time.sleep(self.backoff * (attempt + 1))
                    attempt += 1
                    continue
                raise ProviderError(f"sectors transport error: {e}") from e
        if last_exc is not None:
            raise ProviderError(f"sectors exhausted retries: {last_exc}")
        raise ProviderError("sectors exhausted retries (unknown)")

    def _authorize_request(self, path: str) -> str:
        if self.mode is ProviderMode.SECTORS_FIXTURE:
            if self._transport is None:
                raise ProviderError(
                    f"SECTORS_FIXTURE has no offline transport; endpoint={path}"
                )
            return "sectors_fixture"
        if not self._allow_live:
            raise ProviderError(
                f"SECTORS_LIVE request disabled (allow_live=False); endpoint={path}"
            )
        if not self.api_key.strip():
            raise ProviderError(
                f"SECTORS_LIVE credential missing (SECTORS_API_KEY); endpoint={path}"
            )
        return "sectors"

    def _validate_payload(self, path: str, payload: Any, params: Mapping[str, Any]) -> None:
        if not self.validate_contracts:
            return
        from .sectors_contracts import validate_sectors_payload

        validate_sectors_payload(
            path,
            payload,
            expected_date=params.get("date") if path == "/v2/close/" else None,
            raise_on_error=True,
        )

    def _do_http(self, method: str, url: str, params: dict) -> tuple[int, Any]:
        if self._transport is not None:
            return self._transport(method, url, params, self._auth_header())
        # Default urllib transport — kept inline to avoid an extra import path.
        import json
        import urllib.parse
        import urllib.request

        headers = self._auth_header()
        if params:
            encoded = urllib.parse.urlencode(
                {k: v for k, v in params.items() if v is not None}
            )
            sep = "&" if "?" in url else "?"
            url = f"{url}{sep}{encoded}"
        req = urllib.request.Request(url, method=method, headers=headers)
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            raw = resp.read().decode("utf-8")
            try:
                return resp.status, json.loads(raw)
            except json.JSONDecodeError:
                return resp.status, raw

    def _auth_header(self) -> dict:
        # Docs: `Authorization: <api-key>` — no "Bearer" prefix.
        return {
            "Authorization": self.api_key,
            "Accept": "application/json",
            "User-Agent": "idx-leadership-diffusion/0.2 (+sectors-client)",
        }

    @staticmethod
    def _cache_key(method: str, url: str, params: Mapping[str, Any]) -> str:
        s = json.dumps({"m": method, "u": url, "p": dict(params)}, sort_keys=True, default=str)
        return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _row_count(payload: Any) -> int:
    if isinstance(payload, list):
        return len(payload)
    if isinstance(payload, Mapping):
        for key in ("results", "data", "items"):
            if key in payload and isinstance(payload[key], list):
                return len(payload[key])
        return 1
    return 0
