"""Thin, credit-aware Sectors v2 HTTP client.

The client is the only module that opens a Sectors connection. It keeps the
provider boundary explicit by handling authentication, bounded retries,
pagination, response validation, raw-response caching, and request
provenance here while returning plain JSON to the provider normalizers.

API keys are accepted from the provider factory and are never included in
cache keys, ledger parameters, response headers, or error messages.
"""
from __future__ import annotations

import hashlib
import json
import math
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Optional, Sequence

from ..data import RawCache
from ..models import ProviderMode
from ..utils import get_logger
from ..utils.errors import CreditBudgetExceeded, IDXError, ProviderError
from .ledger import RequestLedger

_log = get_logger(__name__)
DEFAULT_MAX_ESTIMATED_CREDITS = 1_000.0


# Per-endpoint cost table. Values are taken from the current Sectors v2
# documentation; an unknown value remains 0 in the numeric estimate and is
# labelled UNKNOWN / VERIFY in the response and generated reports.
DOCUMENTED_COST = {
    "/v2/close/": "per_page",
    "/v2/daily/{symbol}/": "per_call_1",
    "/v2/index-daily/{index}/": "per_call_1",
    "/v2/idx-total/": "per_call_1",
    "/v2/free-float/": "per_100_companies",
    "/v2/foreign-flow/{symbol}/": "per_call_1",
    "/v2/company/corporate-actions/{symbol}/": "per_call_1",
    "/v2/suspensions/": "per_call_1",
    "/v2/subsectors/": "per_call_1",
    "/v2/industries/": "per_call_1",
    "/v2/subindustries/": "per_call_1",
    "/v2/companies/": "unknown_verify",
    "/v2/company/report/{symbol}/": "unknown_verify",
}


def _endpoint_cost_key(endpoint: str) -> str:
    """Map concrete symbol/index paths to their documented template."""

    path = endpoint.split("?", 1)[0]
    if path.startswith("/v2/daily/"):
        return "/v2/daily/{symbol}/"
    if path.startswith("/v2/index-daily/"):
        return "/v2/index-daily/{index}/"
    if path.startswith("/v2/foreign-flow/"):
        return "/v2/foreign-flow/{symbol}/"
    if path.startswith("/v2/company/corporate-actions/"):
        return "/v2/company/corporate-actions/{symbol}/"
    return path


def _estimated_credit_cost(
    endpoint: str,
    response_payload: Mapping[str, Any] | list | None,
    params: Mapping[str, Any] | None = None,
) -> float:
    """Return a documented/best-effort numeric cost without inventing one."""

    params = params or {}
    endpoint_key = _endpoint_cost_key(endpoint)
    if endpoint_key == "/v2/companies/":
        # Structured ``where`` calls are documented at one credit and natural
        # language ``q`` calls at three. The unfiltered listing price is not
        # stated in the public contract, so leave it unknown.
        if str(params.get("q") or "").strip():
            return 3.0
        if str(params.get("where") or "").strip():
            return 1.0
        return 0.0

    rule = DOCUMENTED_COST.get(endpoint_key, "unknown_verify")
    if rule == "unknown_verify":
        return 0.0
    if rule == "per_call_1" or rule == "per_page":
        return 1.0
    if rule == "per_100_companies":
        if isinstance(response_payload, list):
            return float(max(1, (len(response_payload) + 99) // 100))
        if isinstance(response_payload, Mapping) and isinstance(
            response_payload.get("results"), list
        ):
            return float(max(1, (len(response_payload["results"]) + 99) // 100))
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
    response_headers: dict[str, str] = field(default_factory=dict)
    rate_limit_remaining: Optional[int] = None
    retry_after_seconds: Optional[float] = None
    cost_basis: str = "UNKNOWN / VERIFY"


class SectorsClient:
    """HTTP client for Sectors v2."""

    BASE_URL = "https://api.sectors.app"
    DEFAULT_MAX_ESTIMATED_CREDITS = DEFAULT_MAX_ESTIMATED_CREDITS
    DEFAULT_TIMEOUT_SECONDS = 30
    DEFAULT_MAX_RETRIES = 2
    DEFAULT_BACKOFF_SECONDS = 1.5
    DEFAULT_MAX_PAGES = 50
    # A request-count ceiling is intentionally separate from the credit
    # estimate.  It is a last-resort circuit breaker for demo runs when the
    # provider's balance/debit is not visible to this client.
    DEFAULT_MAX_HTTP_REQUESTS = 400

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
        cache_ttl_seconds: int | None = 60 * 60,
        min_request_interval_seconds: float = 0.0,
        max_estimated_credits: float | None = DEFAULT_MAX_ESTIMATED_CREDITS,
        max_http_requests: int | None = DEFAULT_MAX_HTTP_REQUESTS,
        budget_reserver: Callable[[str, float], None] | None = None,
    ) -> None:
        self.api_key = api_key or ""
        normalized_base_url = (base_url or self.BASE_URL).rstrip("/")
        if normalized_base_url.endswith("/v2"):
            normalized_base_url = normalized_base_url[:-3].rstrip("/")
        self.base_url = normalized_base_url
        self.ledger = ledger or RequestLedger()
        self.cache = cache or RawCache()
        self.timeout = max(1, int(timeout))
        self.max_retries = max(0, int(max_retries))
        self.backoff = max(0.0, float(backoff_seconds))
        self._transport = transport
        self._allow_live = bool(allow_live)
        try:
            self.mode = mode if isinstance(mode, ProviderMode) else ProviderMode(str(mode))
        except ValueError as exc:
            raise ProviderError(f"Unsupported Sectors client mode: {mode}") from exc
        if self.mode not in {ProviderMode.SECTORS_FIXTURE, ProviderMode.SECTORS_LIVE}:
            raise ProviderError(f"SectorsClient cannot run in mode {self.mode.value}")
        if self.mode is ProviderMode.SECTORS_LIVE and not self.api_key.strip():
            # Construction remains available for dry-run planning. Requests
            # fail before cache/transport access in _authorize_request.
            _log.warning("sectors_client_init without_api_key allow_live=%s", allow_live)
        if self.mode is ProviderMode.SECTORS_FIXTURE and self._transport is None:
            raise ProviderError("SECTORS_FIXTURE requires an injected offline transport")
        self.force_refresh = bool(force_refresh)
        self.validate_contracts = bool(validate_contracts)
        self.cache_ttl_seconds = cache_ttl_seconds
        self.min_request_interval_seconds = max(0.0, float(min_request_interval_seconds))
        if max_estimated_credits is not None:
            max_estimated_credits = float(max_estimated_credits)
            if not math.isfinite(max_estimated_credits) or max_estimated_credits < 0:
                raise ValueError("max_estimated_credits must be finite and non-negative or None")
            if max_estimated_credits > self.DEFAULT_MAX_ESTIMATED_CREDITS:
                raise ValueError(
                    "max_estimated_credits cannot exceed "
                    f"{self.DEFAULT_MAX_ESTIMATED_CREDITS:.0f}"
                )
        self.max_estimated_credits = (
            None if max_estimated_credits is None else max_estimated_credits
        )
        if max_http_requests is not None:
            max_http_requests = int(max_http_requests)
            if max_http_requests < 0:
                raise ValueError("max_http_requests must be non-negative or None")
        self.max_http_requests = max_http_requests
        self._budget_reserver = budget_reserver
        self._budget_lock = threading.Lock()
        self._budget_reserved_credits = 0.0
        self._http_requests_made = 0
        self._request_slot_lock = threading.Lock()
        self._next_request_at = 0.0
        self.last_pagination_diagnostics: dict[str, Any] = {}

    @property
    def budget_reserved_credits(self) -> float:
        """Return the in-process paid-request reserve without exposing secrets."""

        with self._budget_lock:
            return round(self._budget_reserved_credits, 6)

    @property
    def http_requests_made(self) -> int:
        """Return outgoing live HTTP attempts, including retry attempts."""

        with self._budget_lock:
            return self._http_requests_made

    # ---- public surface -------------------------------------------------

    def get(
        self,
        path: str,
        params: Optional[Mapping[str, Any]] = None,
        *,
        use_cache: bool = True,
    ) -> SectorsResponse:
        request_params = dict(params or {})
        return self._request(
            "GET",
            path,
            params=request_params,
            use_cache=bool(use_cache and not self.force_refresh),
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
        """Walk documented offset/limit pages with explicit safety caps."""

        if page_limit is not None and page_limit < 1:
            raise ProviderError("Sectors page_limit must be at least 1")
        if page_limit is None and max_rows is None:
            # Unbounded walks never terminate if the vendor asserts
            # has_next=True forever; default cap keeps them auditable via
            # capped_by_max_pages/PARTIAL diagnostics.
            page_limit = self.DEFAULT_MAX_PAGES
        collected: list[Any] = []
        base_params = dict(params or {})
        offset = int(base_params.get("offset", 0) or 0)
        limit = int(base_params.get("limit", 30) or 30)
        if offset < 0 or limit < 1:
            raise ProviderError("Sectors pagination requires offset >= 0 and limit >= 1")
        page = 0
        diagnostics: dict[str, Any] = {
            "endpoint": path,
            "page_limit": page_limit,
            "pages_fetched": 0,
            "rows_collected": 0,
            "has_next": None,
            "capped_by_max_pages": False,
            "capped_by_max_rows": False,
            "incomplete": True,
            "completeness": "UNKNOWN",
        }
        self.last_pagination_diagnostics = diagnostics

        while True:
            page_params = dict(base_params)
            page_params.update({"offset": offset, "limit": limit})
            response = self.get(path, page_params, use_cache=use_cache)
            payload = response.payload
            if isinstance(payload, Mapping) and "results" in payload:
                results = list(payload.get("results") or [])
            elif isinstance(payload, list):
                results = list(payload)
            else:
                results = [payload]
            collected.extend(results)
            page += 1
            diagnostics["pages_fetched"] = page
            diagnostics["rows_collected"] = len(collected)

            pagination = payload.get("pagination") if isinstance(payload, Mapping) else None
            has_next = (
                bool(pagination.get("has_next"))
                if isinstance(pagination, Mapping) and "has_next" in pagination
                else None
            )
            diagnostics["has_next"] = has_next

            if not isinstance(pagination, Mapping):
                if max_rows is not None and len(collected) >= max_rows:
                    diagnostics.update(
                        {
                            "capped_by_max_rows": True,
                            "stop_reason": "max_rows_without_pagination_metadata",
                            "completeness": "UNKNOWN",
                        }
                    )
                    return collected[:max_rows]
                if page_limit is not None and page >= page_limit:
                    diagnostics.update(
                        {
                            "capped_by_max_pages": True,
                            "stop_reason": "max_pages_without_pagination_metadata",
                            "completeness": "UNKNOWN",
                        }
                    )
                    return collected
                diagnostics.update(
                    {"stop_reason": "missing_pagination_metadata", "completeness": "UNKNOWN"}
                )
                return collected

            if "has_next" not in pagination:
                if max_rows is not None and len(collected) >= max_rows:
                    diagnostics.update(
                        {
                            "capped_by_max_rows": True,
                            "stop_reason": "max_rows_without_has_next",
                            "completeness": "UNKNOWN",
                        }
                    )
                    return collected[:max_rows]
                if page_limit is not None and page >= page_limit:
                    diagnostics.update(
                        {
                            "capped_by_max_pages": True,
                            "stop_reason": "max_pages_without_has_next",
                            "completeness": "UNKNOWN",
                        }
                    )
                    return collected
                diagnostics.update(
                    {"stop_reason": "missing_has_next_metadata", "completeness": "UNKNOWN"}
                )
                return collected

            if max_rows is not None and len(collected) >= max_rows:
                diagnostics.update(
                    {
                        "capped_by_max_rows": True,
                        "stop_reason": "max_rows",
                        "completeness": "COMPLETE" if has_next is False else "PARTIAL",
                        "incomplete": has_next is not False,
                    }
                )
                return collected[:max_rows]

            if has_next is False:
                diagnostics.update(
                    {"stop_reason": "provider_end", "incomplete": False, "completeness": "COMPLETE"}
                )
                return collected

            if page_limit is not None and page >= page_limit:
                diagnostics.update(
                    {
                        "capped_by_max_pages": True,
                        "stop_reason": "max_pages",
                        "completeness": "PARTIAL",
                    }
                )
                return collected
            next_offset = pagination.get("next_offset")
            next_offset = int(next_offset) if next_offset is not None else offset + limit
            if next_offset <= offset:
                raise ProviderError(
                    f"Sectors pagination did not advance endpoint={path} offset={offset}"
                )
            offset = next_offset

    # ---- internals ------------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict,
        use_cache: bool,
    ) -> SectorsResponse:
        provider_label = self._authorize_request(path)
        url = path if path.startswith("http") else f"{self.base_url}{path}"
        cache_key = self._cache_key(method, url, params)

        if use_cache:
            cached = self.cache.get(cache_key, ttl_seconds=self.cache_ttl_seconds)
            if cached is not None:
                try:
                    self._validate_payload(path, cached, params)
                except IDXError as exc:
                    message = _redact_error(str(exc), self.api_key)
                    self.ledger.record(
                        provider=provider_label,
                        endpoint=path,
                        request_type=method,
                        parameters=params,
                        cache_hit=True,
                        status="invalid_response",
                        rows_returned=_row_count(cached),
                        elapsed_ms=0.0,
                        error=message,
                    )
                    raise
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
                    cost_basis="CACHE_HIT",
                )

        started = time.time()
        attempt = 0
        budget_reserved = 0.0
        last_exc: Optional[Exception] = None
        while attempt <= self.max_retries:
            try:
                self._wait_for_request_slot()
                budget_reserved += self._reserve_budget(path, params)
                transport_result = self._do_http(method, url, params)
                status, payload, headers = _unpack_transport_result(transport_result)
                elapsed = (time.time() - started) * 1000.0
                safe_headers = _safe_response_headers(headers)
                retry_after = _parse_retry_after(safe_headers.get("retry-after"))

                if status == 429 or 500 <= status < 600:
                    if attempt < self.max_retries:
                        delay = (
                            retry_after
                            if retry_after is not None
                            else self.backoff * (2**attempt)
                        )
                        time.sleep(min(30.0, max(0.0, float(delay))))
                        attempt += 1
                        continue
                    message = _format_response_error(
                        "sectors transient response", status, payload, path, self.api_key
                    )
                    self.ledger.record(
                        provider=provider_label,
                        endpoint=path,
                        request_type=method,
                        parameters=params,
                        cache_hit=False,
                        status=f"http_{status}",
                        rows_returned=_row_count(payload),
                        elapsed_ms=elapsed,
                        budget_reserved_credit_cost=budget_reserved,
                        error=message,
                    )
                    raise ProviderError(message)

                if status >= 400:
                    message = _format_response_error(
                        "sectors client response", status, payload, path, self.api_key
                    )
                    self.ledger.record(
                        provider=provider_label,
                        endpoint=path,
                        request_type=method,
                        parameters=params,
                        cache_hit=False,
                        status=f"http_{status}",
                        rows_returned=_row_count(payload),
                        elapsed_ms=elapsed,
                        budget_reserved_credit_cost=budget_reserved,
                        error=message,
                    )
                    raise ProviderError(message)

                try:
                    _assert_payload_size(payload, path)
                    self._validate_payload(path, payload, params)
                except IDXError as exc:
                    message = _redact_error(str(exc), self.api_key)
                    self.ledger.record(
                        provider=provider_label,
                        endpoint=path,
                        request_type=method,
                        parameters=params,
                        cache_hit=False,
                        status="invalid_response",
                        rows_returned=_row_count(payload),
                        elapsed_ms=elapsed,
                        budget_reserved_credit_cost=budget_reserved,
                        error=message,
                    )
                    raise

                if use_cache and isinstance(payload, (dict, list)):
                    self.cache.set(cache_key, payload)
                estimated = (
                    _estimated_credit_cost(path, payload, params)
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
                    estimated_credit_cost=estimated,
                    budget_reserved_credit_cost=budget_reserved,
                )
                rate_limit_remaining = _parse_int_header(
                    safe_headers,
                    ("x-ratelimit-remaining", "x-rate-limit-remaining", "ratelimit-remaining"),
                )
                return SectorsResponse(
                    payload=payload,
                    status=status,
                    endpoint=path,
                    params=params,
                    elapsed_ms=elapsed,
                    rows=_row_count(payload),
                    estimated_credit_cost=estimated,
                    request_id=_first_header(
                        safe_headers, ("x-request-id", "x-correlation-id", "request-id")
                    ),
                    response_headers=safe_headers,
                    rate_limit_remaining=rate_limit_remaining,
                    retry_after_seconds=retry_after,
                    cost_basis=_cost_basis(path, params),
                )
            except IDXError:
                raise
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                if attempt < self.max_retries:
                    time.sleep(min(30.0, self.backoff * (2**attempt)))
                    attempt += 1
                    continue
                message = _redact_error(f"sectors transport error: {exc}", self.api_key)
                self.ledger.record(
                    provider=provider_label,
                    endpoint=path,
                    request_type=method,
                    parameters=params,
                    cache_hit=False,
                    status="transport_error",
                    rows_returned=0,
                    elapsed_ms=(time.time() - started) * 1000.0,
                    budget_reserved_credit_cost=budget_reserved,
                    error=message,
                )
                raise ProviderError(message) from exc

        if last_exc is not None:
            raise ProviderError(_redact_error(f"sectors exhausted retries: {last_exc}", self.api_key))
        raise ProviderError("sectors exhausted retries (unknown)")

    def _wait_for_request_slot(self) -> None:
        """Serialize live requests when the account has a low request rate limit."""

        interval = self.min_request_interval_seconds
        if interval <= 0:
            return
        with self._request_slot_lock:
            now = time.monotonic()
            delay = self._next_request_at - now
            if delay > 0:
                time.sleep(delay)
            self._next_request_at = time.monotonic() + interval

    def _reserve_budget(self, path: str, params: Mapping[str, Any]) -> float:
        """Reserve one complete potential HTTP attempt before it leaves the process.

        Retries reserve again, so a transient response cannot silently push the
        run beyond its ceiling. Unknown endpoint pricing is blocked when a
        budget is active rather than guessed.
        """

        if self.mode is not ProviderMode.SECTORS_LIVE:
            return 0.0
        cost = _budget_request_cost(path, params)
        if cost is None and self.max_estimated_credits is not None:
            raise CreditBudgetExceeded(
                "credit budget cannot certify endpoint pricing; "
                f"endpoint={path} requires a documented cost before live use"
            )
        # If the caller deliberately disabled credit accounting, the request
        # circuit breaker still applies. Unknown pricing is then allowed, but
        # remains unpriced in the ledger/audit.
        numeric_cost = float(cost or 0.0)
        with self._budget_lock:
            if (
                self.max_http_requests is not None
                and self._http_requests_made >= self.max_http_requests
            ):
                raise CreditBudgetExceeded(
                    "live request cap exhausted before HTTP request; "
                    f"endpoint={path} requests={self._http_requests_made} "
                    f"cap={self.max_http_requests}"
                )
            proposed = self._budget_reserved_credits + numeric_cost
            if (
                self.max_estimated_credits is not None
                and proposed > self.max_estimated_credits + 1e-9
            ):
                raise CreditBudgetExceeded(
                    "credit budget exhausted before HTTP request; "
                    f"endpoint={path} reserved={self._budget_reserved_credits:.2f} "
                    f"requested={numeric_cost:.2f} cap={self.max_estimated_credits:.2f}"
                )
            if self._budget_reserver is not None:
                # Persist before sending each attempt so a process restart or
                # concurrent runner cannot reset the recording ceiling.
                self._budget_reserver(path, numeric_cost)
            if self.max_estimated_credits is not None:
                self._budget_reserved_credits = proposed
            self._http_requests_made += 1
        return numeric_cost

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

    def _do_http(self, method: str, url: str, params: dict) -> Any:
        if self._transport is not None:
            return self._transport(method, url, params, self._auth_header())

        import urllib.error
        import urllib.parse
        import urllib.request

        request_url = url
        if params:
            encoded = urllib.parse.urlencode(
                {key: value for key, value in params.items() if value is not None}
            )
            separator = "&" if "?" in request_url else "?"
            request_url = f"{request_url}{separator}{encoded}"
        request = urllib.request.Request(
            request_url, method=method, headers=self._auth_header()
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8", errors="replace")
                return response.status, _decode_json_or_text(raw), dict(response.headers.items())
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            return exc.code, _decode_json_or_text(raw), dict(exc.headers.items())

    def _auth_header(self) -> dict[str, str]:
        # Sectors v2 expects the raw key, not a Bearer prefix.
        return {
            "Authorization": self.api_key,
            "Accept": "application/json",
            "User-Agent": "idx-leadership-diffusion/0.2 (+sectors-client)",
        }

    @staticmethod
    def _cache_key(method: str, url: str, params: Mapping[str, Any]) -> str:
        serialized = json.dumps(
            {"m": method, "u": url, "p": dict(params)},
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _unpack_transport_result(result: Any) -> tuple[int, Any, Mapping[str, str]]:
    """Accept the historical two-tuple fixture transport and richer headers."""

    if not isinstance(result, tuple) or len(result) < 2:
        raise ProviderError("Sectors transport must return (status, payload[, headers])")
    status = int(result[0])
    payload = result[1]
    headers = result[2] if len(result) >= 3 and isinstance(result[2], Mapping) else {}
    return status, payload, headers


def _decode_json_or_text(raw: str) -> Any:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def _safe_response_headers(headers: Mapping[str, Any] | None) -> dict[str, str]:
    """Keep operational headers only; authorization material is discarded."""

    allowed = {
        "retry-after",
        "x-request-id",
        "x-correlation-id",
        "request-id",
        "x-ratelimit-remaining",
        "x-rate-limit-remaining",
        "ratelimit-remaining",
        "x-credits-remaining",
    }
    return {
        str(key).lower(): str(value)
        for key, value in (headers or {}).items()
        if str(key).lower() in allowed
    }


def _parse_retry_after(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return max(0.0, min(30.0, float(value.strip())))
    except (TypeError, ValueError):
        return None


def _parse_int_header(headers: Mapping[str, str], names: Sequence[str]) -> int | None:
    value = _first_header(headers, names)
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _first_header(headers: Mapping[str, str], names: Sequence[str]) -> str | None:
    for name in names:
        value = headers.get(name.lower())
        if value is not None:
            return value
    return None


def _redact_error(value: str, api_key: str) -> str:
    message = str(value)
    if api_key:
        message = message.replace(api_key, "[REDACTED]")
    return message[:500]


def _format_response_error(
    prefix: str, status: int, payload: Any, endpoint: str, api_key: str
) -> str:
    try:
        body = json.dumps(payload, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        body = str(payload)
    return _redact_error(
        f"{prefix} status={status} endpoint={endpoint} body={body[:300]}", api_key
    )


def _cost_basis(endpoint: str, params: Mapping[str, Any]) -> str:
    key = _endpoint_cost_key(endpoint)
    if key == "/v2/companies/":
        if str(params.get("q") or "").strip():
            return "DOCUMENTED: natural-language companies query = 3 credits"
        if str(params.get("where") or "").strip():
            return "DOCUMENTED: structured companies query = 1 credit"
        return "UNKNOWN / VERIFY: unfiltered companies listing"
    rule = DOCUMENTED_COST.get(key, "unknown_verify")
    if rule == "per_page":
        return "DOCUMENTED: 1 credit per page"
    if rule == "per_100_companies":
        return "DOCUMENTED: 1 credit per 100 companies"
    if rule == "per_call_1":
        return "DOCUMENTED: 1 credit per call"
    return "UNKNOWN / VERIFY"


def _budget_request_cost(
    endpoint: str, params: Mapping[str, Any]
) -> float | None:
    """Return a conservative pre-request cost, or None when pricing is unknown."""

    key = _endpoint_cost_key(endpoint)
    if key == "/v2/companies/":
        if str(params.get("q") or "").strip():
            return 3.0
        if str(params.get("where") or "").strip():
            return 1.0
        return None
    rule = DOCUMENTED_COST.get(key, "unknown_verify")
    if rule in {"per_call_1", "per_page"}:
        return 1.0
    if rule == "per_100_companies":
        limit = int(params.get("limit", 100) or 100)
        return float(max(1, (limit + 99) // 100))
    return None


def _row_count(payload: Any) -> int:
    if isinstance(payload, list):
        return len(payload)
    if isinstance(payload, Mapping):
        for key in ("results", "data", "items"):
            if key in payload and isinstance(payload[key], list):
                return len(payload[key])
        return 1
    return 0


#: Refuse vendor payloads larger than this (serialized chars) before
#: validation/caching so a runaway response cannot fill disk or memory.
MAX_PAYLOAD_CHARS = 1_000_000


def _assert_payload_size(payload: Any, endpoint: str) -> None:
    try:
        size = len(json.dumps(payload, default=str))
    except (TypeError, ValueError):
        size = MAX_PAYLOAD_CHARS + 1
    if size > MAX_PAYLOAD_CHARS:
        raise ProviderError(
            f"response exceeds size cap endpoint={endpoint} chars={size}"
        )


__all__ = [
    "DEFAULT_MAX_ESTIMATED_CREDITS",
    "DOCUMENTED_COST",
    "SectorsClient",
    "SectorsResponse",
    "_budget_request_cost",
    "_estimated_credit_cost",
]
