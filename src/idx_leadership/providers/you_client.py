"""Server-side You.com client for provenance-aware web context.

You.com is intentionally not a market-data provider in this project. This
client only returns web evidence and records it in a separate cache/ledger so
web text cannot accidentally enter quantitative features or group metrics.

You.com exposes three endpoints relevant to qualitative context:

* ``POST https://ydc-index.io/v1/search``   — web + news search
* ``POST https://ydc-index.io/v1/contents`` — page content extraction
* ``POST https://api.you.com/v1/research``  — multi-step research synthesis
                                              with inline citations

Authentication uses an ``X-API-Key`` header (not a Bearer token).  Set
``YOU_API_KEY`` in the project environment before invoking live requests.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import ipaddress
import json
import os
import re as _re
import threading
import time
from typing import Any, Mapping, Sequence
from urllib.parse import urlparse

from ..data import RawCache
from ..utils import get_logger, load_project_env, project_root
from ..utils.errors import ProviderError
from .ledger import RequestLedger

_log = get_logger(__name__)

# Canonical backend cap for persisted research synthesis text. Frontend
# display capping is owned separately; this constant is the shared contract
# value recorded in the closure REPORT.
RESEARCH_ANSWER_MAX_CHARS = 1200

# Provenance banner marking persisted synthesis as unsourced context. The
# persisted value (banner + body) never exceeds RESEARCH_ANSWER_MAX_CHARS.
RESEARCH_ANSWER_PREFIX = "UNSOLICITED WEB SYNTHESIS — CONTEXT ONLY, NOT A METRIC. "

#: Refuse vendor payloads larger than this (serialized chars) before
#: validation/caching so a runaway response cannot fill disk or memory.
MAX_PAYLOAD_CHARS = 1_000_000


def _assert_payload_size(payload: Any, endpoint: str) -> None:
    try:
        size = len(json.dumps(payload, default=str))
    except (TypeError, ValueError):
        size = MAX_PAYLOAD_CHARS + 1
    if size > MAX_PAYLOAD_CHARS:
        raise YouError(
            f"response exceeds size cap endpoint={endpoint} chars={size}",
            endpoint=endpoint,
            code="RESPONSE_TOO_LARGE",
        )


def truncate_research_answer(
    answer: str | None, *, request_id: str | None = None
) -> str | None:
    """Cap research synthesis with a provenance banner.

    The returned value is prefixed with ``RESEARCH_ANSWER_PREFIX`` and the
    body is truncated so the total never exceeds
    ``RESEARCH_ANSWER_MAX_CHARS``. ``None`` passes through (no answer).
    ``request_id`` is accepted for call-site compatibility and recorded in
    the envelope's own ``request_id`` field, not in the persisted text.
    """

    if answer is None:
        return None
    body = str(answer)
    room = max(0, RESEARCH_ANSWER_MAX_CHARS - len(RESEARCH_ANSWER_PREFIX))
    return RESEARCH_ANSWER_PREFIX + body[:room]


class YouError(ProviderError):
    """Structured error for a You.com request."""

    def __init__(
        self,
        message: str,
        *,
        endpoint: str,
        status: int | None = None,
        code: str = "YOU_ERROR",
        retryable: bool = False,
    ) -> None:
        self.endpoint = endpoint
        self.status = status
        self.code = code
        self.retryable = retryable
        super().__init__(message)


def _assert_safe_url(url: str, *, endpoint: str) -> str:
    clean = str(url or "").strip()
    try:
        parsed = urlparse(clean)
    except Exception:
        raise YouError(
            f"You.com {endpoint} URL is not parseable",
            endpoint=endpoint,
            code="INVALID_URL",
        )
    if parsed.scheme not in ("http", "https"):
        raise YouError(
            "You.com URL must use http:// or https://",
            endpoint=endpoint,
            code="INVALID_URL",
        )
    host = (parsed.hostname or "").lower()
    if not host or host in ("localhost", "metadata.google.internal"):
        raise YouError(
            "You.com URL host is not allowed",
            endpoint=endpoint,
            code="INVALID_URL",
        )
    if _re.fullmatch(r"[0-9xXa-fA-F.]+", host or "") and any(
        ch.isdigit() for ch in (host or "")
    ):
        # Decimal / octal / hex IP forms resolve to loopback/link-local via
        # inet_aton on many libc stacks but are not parsed by ipaddress.
        raise YouError(
            "You.com URL numeric-IP hosts are not allowed",
            endpoint=endpoint,
            code="INVALID_URL",
        )
    try:
        ipaddress.ip_address(host)
        raise YouError(
            "You.com URL IP-literal hosts are not allowed",
            endpoint=endpoint,
            code="INVALID_URL",
        )
    except ValueError:
        pass
    if host == "169.254.169.254":
        raise YouError(
            "You.com URL host is not allowed",
            endpoint=endpoint,
            code="INVALID_URL",
        )
    return clean


@dataclass
class YouResponse:
    endpoint: str
    params: dict[str, Any]
    payload: dict[str, Any]
    elapsed_ms: float
    cache_hit: bool = False
    request_id: str | None = None
    usage: dict[str, Any] = field(default_factory=dict)
    retrieved_at: str = ""

    @property
    def results(self) -> list[dict[str, Any]]:
        """Return a normalized, uniform list of evidence records.

        You.com's three endpoint shapes are flattened here so callers can
        iterate a single ``results`` list regardless of which endpoint
        produced it.  Each record is expected to carry ``url`` and ``title``.
        """
        results_obj = self.payload.get("results")
        if isinstance(results_obj, list):
            return [dict(row) for row in results_obj if isinstance(row, Mapping)]
        rows: list[dict[str, Any]] = []
        if isinstance(results_obj, Mapping):
            for section in ("web", "news"):
                section_rows = results_obj.get(section)
                if isinstance(section_rows, list):
                    rows.extend(dict(row) for row in section_rows if isinstance(row, Mapping))
        # ``/v1/contents`` returns a bare array; ``/v1/research`` carries
        # ``output.sources``.  These are only reachable if a caller
        # constructs ``YouResponse`` directly with an un-normalized payload.
        if isinstance(self.payload, list):
            rows.extend(dict(row) for row in self.payload if isinstance(row, Mapping))
        output = self.payload.get("output")
        if isinstance(output, Mapping):
            sources = output.get("sources")
            if isinstance(sources, list):
                rows.extend(dict(row) for row in sources if isinstance(row, Mapping))
        return rows

    @property
    def credits_used(self) -> float | None:
        value = self.usage.get("credits")
        try:
            return float(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    @property
    def answer(self) -> str | None:
        """Research synthesis text, if any (qualitative, unsourced).

        Capped to ``RESEARCH_ANSWER_MAX_CHARS`` with a provenance banner so
        persisted answers never grow unbounded.
        """
        output = self.payload.get("output")
        if isinstance(output, Mapping):
            content = output.get("content")
            if isinstance(content, str):
                return truncate_research_answer(
                    content, request_id=self.request_id
                )
        return None

    def to_dict(self) -> dict[str, Any]:
        """Return a persisted evidence envelope with no request credential."""
        return {
            "provider": "you",
            "endpoint": self.endpoint,
            "params": dict(self.params),
            "request_id": self.request_id,
            "retrieved_at": self.retrieved_at,
            "cache_hit": self.cache_hit,
            "usage": dict(self.usage),
            "results": self.results,
            # Research synthesis, retained as unsourced context only and
            # capped to RESEARCH_ANSWER_MAX_CHARS with provenance banner.
            "answer": self.answer,
        }


class YouClient:
    """Bounded You.com REST client using the ``YOU_API_KEY`` environment."""

    SEARCH_BASE_URL = "https://ydc-index.io"
    RESEARCH_BASE_URL = "https://api.you.com"
    DEFAULT_TIMEOUT_SECONDS = 30
    DEFAULT_MAX_RETRIES = 2
    DEFAULT_BACKOFF_SECONDS = 1.0

    def __init__(
        self,
        api_key: str | None = None,
        *,
        search_base_url: str = SEARCH_BASE_URL,
        research_base_url: str = RESEARCH_BASE_URL,
        ledger: RequestLedger | None = None,
        cache: RawCache | None = None,
        timeout: int = DEFAULT_TIMEOUT_SECONDS,
        max_retries: int = DEFAULT_MAX_RETRIES,
        backoff_seconds: float = DEFAULT_BACKOFF_SECONDS,
        cache_ttl_seconds: int | None = 24 * 60 * 60,
        allow_live: bool = False,
        project_id: str | None = None,
        transport: Any = None,
        max_http_requests: int = 3,
    ) -> None:
        load_project_env()
        self.api_key = (
            os.environ.get("YOU_API_KEY", "") if api_key is None else api_key
        ).strip()
        self.search_base_url = (search_base_url or self.SEARCH_BASE_URL).rstrip("/")
        self.research_base_url = (research_base_url or self.RESEARCH_BASE_URL).rstrip("/")
        self.ledger = ledger or RequestLedger(
            path=project_root() / "data" / "raw" / "you_request_ledger.jsonl"
        )
        self.cache = cache or RawCache(project_root() / "data" / "cache" / "you")
        self.timeout = max(1, int(timeout))
        self.max_retries = max(0, int(max_retries))
        self.backoff_seconds = max(0.0, float(backoff_seconds))
        self.cache_ttl_seconds = cache_ttl_seconds
        self.allow_live = bool(allow_live)
        self.project_id = project_id or os.environ.get("YOU_PROJECT")
        self._transport = transport
        if int(max_http_requests) < 1:
            raise ValueError("max_http_requests must be at least 1")
        self.max_http_requests = int(max_http_requests)
        self._request_count = 0
        self._request_count_lock = threading.Lock()

    @property
    def http_requests_made(self) -> int:
        """Return the number of non-cached HTTP attempts made by this client."""
        with self._request_count_lock:
            return self._request_count

    def search(
        self,
        query: str,
        *,
        count: int = 10,
        freshness: str | None = None,
        country: str | None = None,
        language: str | None = None,
        include_domains: Sequence[str] | None = None,
        exclude_domains: Sequence[str] | None = None,
        boost_domains: Sequence[str] | None = None,
        extraction_mode: str | None = None,
        use_cache: bool = True,
    ) -> YouResponse:
        """Search the web via ``POST /v1/search``.

        Domain scoping via include/exclude/boost_domains is caller-enforced;
        URL safety is enforced at the extract boundary by _assert_safe_url.
        """
        query = str(query or "").strip()
        if not query:
            raise YouError(
                "You.com search query is empty",
                endpoint="/v1/search",
                code="INVALID_QUERY",
            )
        if len(query) > 4000:
            raise YouError(
                "You.com search query exceeds 4000 characters",
                endpoint="/v1/search",
                code="QUERY_TOO_LONG",
            )
        if include_domains and exclude_domains:
            raise YouError(
                "include_domains and exclude_domains cannot be combined",
                endpoint="/v1/search",
                code="INVALID_PARAMETER",
            )
        if boost_domains and include_domains:
            raise YouError(
                "boost_domains and include_domains cannot be combined",
                endpoint="/v1/search",
                code="INVALID_PARAMETER",
            )
        if extraction_mode is not None and extraction_mode not in {"highlights", "full_page"}:
            raise YouError(
                "extraction_mode must be 'highlights' or 'full_page'",
                endpoint="/v1/search",
                code="INVALID_PARAMETER",
            )
        params: dict[str, Any] = {
            "query": query,
            "count": int(count),
        }
        if freshness:
            params["freshness"] = str(freshness)
        if country:
            params["country"] = str(country)
        if language:
            params["language"] = str(language)
        if include_domains:
            params["include_domains"] = list(include_domains)
        if exclude_domains:
            params["exclude_domains"] = list(exclude_domains)
        if boost_domains:
            params["boost_domains"] = list(boost_domains)
        if extraction_mode is not None:
            params["extraction"] = {"extraction_mode": extraction_mode}
        return self._request("/v1/search", params, use_cache=use_cache, base_url=self.search_base_url)

    def extract(
        self,
        urls: Sequence[str],
        *,
        formats: Sequence[str] | None = None,
        crawl_timeout: int = 10,
        max_age: int | None = None,
        use_cache: bool = True,
    ) -> YouResponse:
        """Extract page content via ``POST /v1/contents``."""
        clean_urls = [str(url).strip() for url in urls if str(url).strip()]
        if not clean_urls or len(clean_urls) > 20:
            raise YouError(
                "You.com extract accepts between 1 and 20 URLs",
                endpoint="/v1/contents",
                code="INVALID_URL_BATCH",
            )
        clean_urls = [_assert_safe_url(u, endpoint="/v1/contents") for u in clean_urls]
        params: dict[str, Any] = {
            "urls": clean_urls,
            "crawl_timeout": int(crawl_timeout),
        }
        if formats:
            params["formats"] = [str(fmt) for fmt in formats]
        if max_age is not None:
            params["max_age"] = int(max_age)
        return self._request("/v1/contents", params, use_cache=use_cache, base_url=self.search_base_url)

    def research(
        self,
        input_text: str,
        *,
        research_effort: str = "standard",
        source_include_domains: Sequence[str] | None = None,
        source_exclude_domains: Sequence[str] | None = None,
        source_boost_domains: Sequence[str] | None = None,
        source_freshness: str | None = None,
        source_country: str | None = None,
        output_schema: Mapping[str, Any] | None = None,
        background: bool = False,
        use_cache: bool = True,
    ) -> YouResponse:
        """Run multi-step research via ``POST /v1/research``."""
        text = str(input_text or "").strip()
        if not text:
            raise YouError(
                "You.com research input is empty",
                endpoint="/v1/research",
                code="INVALID_QUERY",
            )
        if len(text) > 40000:
            raise YouError(
                "You.com research input exceeds 40000 characters",
                endpoint="/v1/research",
                code="QUERY_TOO_LONG",
            )
        valid_efforts = {"lite", "standard", "deep", "exhaustive", "frontier"}
        if research_effort not in valid_efforts:
            raise YouError(
                f"unsupported You.com research_effort={research_effort}",
                endpoint="/v1/research",
                code="INVALID_PARAMETER",
            )
        if research_effort == "frontier" and not background:
            raise YouError(
                "research_effort='frontier' requires background=true",
                endpoint="/v1/research",
                code="INVALID_PARAMETER",
            )
        if research_effort == "lite" and output_schema:
            raise YouError(
                "output_schema is not supported with research_effort='lite'",
                endpoint="/v1/research",
                code="INVALID_PARAMETER",
            )
        params: dict[str, Any] = {
            "input": text,
            "research_effort": research_effort,
            "background": bool(background),
        }
        source_control: dict[str, Any] = {}
        if source_include_domains:
            source_control["include_domains"] = list(source_include_domains)
        if source_exclude_domains:
            source_control["exclude_domains"] = list(source_exclude_domains)
        if source_boost_domains:
            source_control["boost_domains"] = list(source_boost_domains)
        if source_freshness:
            source_control["freshness"] = str(source_freshness)
        if source_country:
            source_control["country"] = str(source_country)
        if source_control:
            params["source_control"] = source_control
        if output_schema:
            params["output_schema"] = dict(output_schema)
        return self._request("/v1/research", params, use_cache=use_cache, base_url=self.research_base_url)

    def search_context(
        self,
        query: str,
        *,
        include_domains: Sequence[str] | None = None,
        max_results: int = 5,
        time_range: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return normalized web evidence records, separate from metrics."""
        response = self.search(
            query,
            count=max_results,
            include_domains=include_domains,
            freshness=time_range,
        )
        records: list[dict[str, Any]] = []
        for result in response.results:
            url = str(result.get("url") or "").strip()
            if not url:
                continue
            content = (
                result.get("content")
                or result.get("markdown")
                or result.get("description")
                or ""
            )
            records.append(
                {
                    "source_type": "WEB_CONTEXT",
                    "provider": "you",
                    "url": url,
                    "title": str(result.get("title") or url)[:300],
                    "content": str(content)[:1200],
                    "retrieved_at": response.retrieved_at,
                    "request_id": response.request_id,
                    "quantitative_use": False,
                }
            )
        return records

    def _request(
        self,
        endpoint: str,
        params: dict[str, Any],
        *,
        use_cache: bool,
        base_url: str,
    ) -> YouResponse:
        if not self.allow_live:
            raise YouError(
                "You.com live request disabled (allow_live=False)",
                endpoint=endpoint,
                code="LIVE_DISABLED",
            )
        if not self.api_key:
            raise YouError(
                "You.com credential missing (YOU_API_KEY)",
                endpoint=endpoint,
                code="CREDENTIAL_MISSING",
            )
        cache_key = self._cache_key(endpoint, params)
        if use_cache:
            cached = self.cache.get(cache_key, ttl_seconds=self.cache_ttl_seconds)
            if isinstance(cached, Mapping):
                rows = cached.get("results")
                rows_returned = len(rows) if isinstance(rows, list) else 0
                self.ledger.record(
                    provider="you",
                    endpoint=endpoint,
                    request_type="POST",
                    parameters=params,
                    cache_hit=True,
                    status="ok",
                    rows_returned=rows_returned,
                    elapsed_ms=0.0,
                    actual_credit_cost=0.0,
                )
                return YouResponse(
                    endpoint=endpoint,
                    params=dict(params),
                    payload=dict(cached),
                    elapsed_ms=0.0,
                    cache_hit=True,
                    request_id=str(cached.get("request_id") or "") or None,
                    usage=dict(cached.get("usage") or {}),
                    retrieved_at=str(
                        cached.get("_retrieved_at")
                        or datetime.now(timezone.utc).isoformat()
                    ),
                )

        started = time.time()
        attempt = 0
        while attempt <= self.max_retries:
            try:
                self._reserve_http_request(endpoint)
                result = self._post_json(endpoint, params, base_url)
                status, payload, headers = _unpack_result(result)
                elapsed = (time.time() - started) * 1000.0
                _assert_payload_size(payload, endpoint)
                if status == 429 or 500 <= status < 600:
                    if attempt < self.max_retries:
                        delay = _retry_after(headers) or self.backoff_seconds * (attempt + 1)
                        time.sleep(min(30.0, max(0.0, delay)))
                        attempt += 1
                        continue
                    raise _response_error(
                        "You.com transient response",
                        endpoint,
                        status,
                        payload,
                        self.api_key,
                        True,
                    )
                if status >= 400:
                    self.ledger.record(
                        provider="you",
                        endpoint=endpoint,
                        request_type="POST",
                        parameters=params,
                        cache_hit=False,
                        status=f"http_{status}",
                        rows_returned=0,
                        elapsed_ms=elapsed,
                        error=f"You.com response endpoint={endpoint} status={status}",
                    )
                    raise _response_error(
                        "You.com response",
                        endpoint,
                        status,
                        payload,
                        self.api_key,
                        False,
                    )
                normalized = _validate_payload(endpoint, payload)
                normalized["_retrieved_at"] = datetime.now(timezone.utc).isoformat()
                if use_cache:
                    self.cache.set(cache_key, normalized)
                usage = normalized.get("usage")
                usage = dict(usage) if isinstance(usage, Mapping) else {}
                request_id = str(normalized.get("request_id") or "") or None
                credits = _credits(usage)
                rows = normalized.get("results")
                rows_returned = len(rows) if isinstance(rows, list) else 0
                self.ledger.record(
                    provider="you",
                    endpoint=endpoint,
                    request_type="POST",
                    parameters=params,
                    cache_hit=False,
                    status="ok",
                    rows_returned=rows_returned,
                    elapsed_ms=elapsed,
                    actual_credit_cost=credits,
                )
                return YouResponse(
                    endpoint=endpoint,
                    params=dict(params),
                    payload=normalized,
                    elapsed_ms=elapsed,
                    request_id=request_id,
                    usage=usage,
                    retrieved_at=str(normalized.get("_retrieved_at")),
                )
            except YouError:
                raise
            except Exception as exc:  # noqa: BLE001
                if attempt < self.max_retries:
                    time.sleep(min(30.0, self.backoff_seconds * (attempt + 1)))
                    attempt += 1
                    continue
                message = _redact(str(exc), self.api_key)
                self.ledger.record(
                    provider="you",
                    endpoint=endpoint,
                    request_type="POST",
                    parameters=params,
                    cache_hit=False,
                    status="transport_error",
                    rows_returned=0,
                    elapsed_ms=(time.time() - started) * 1000.0,
                    error=message,
                )
                raise YouError(
                    f"You.com transport error endpoint={endpoint}: {message}",
                    endpoint=endpoint,
                    code="TRANSPORT_ERROR",
                    retryable=True,
                ) from exc
        raise YouError(
            f"You.com retries exhausted endpoint={endpoint}",
            endpoint=endpoint,
            code="RETRIES_EXHAUSTED",
            retryable=True,
        )

    def _reserve_http_request(self, endpoint: str) -> None:
        with self._request_count_lock:
            if self._request_count >= self.max_http_requests:
                raise YouError(
                    "You.com client request cap reached before HTTP request; "
                    f"endpoint={endpoint} cap={self.max_http_requests}",
                    endpoint=endpoint,
                    code="REQUEST_CAP_EXCEEDED",
                    retryable=False,
                )
            self._request_count += 1

    def _post_json(self, endpoint: str, params: Mapping[str, Any], base_url: str) -> Any:
        if self._transport is not None:
            return self._transport(
                "POST",
                f"{base_url}{endpoint}",
                dict(params),
                self._headers(),
            )
        import urllib.error
        import urllib.request

        request = urllib.request.Request(
            f"{base_url}{endpoint}",
            data=json.dumps(dict(params), ensure_ascii=False).encode("utf-8"),
            method="POST",
            headers=self._headers(),
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = response.read().decode("utf-8", errors="replace")
                return response.status, _decode(body), dict(response.headers.items())
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            return exc.code, _decode(body), dict(exc.headers.items())

    def _headers(self) -> dict[str, str]:
        headers = {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "idx-leadership-diffusion/0.2 (+you-client)",
        }
        if self.project_id:
            headers["X-Project-ID"] = self.project_id
        return headers

    @staticmethod
    def _cache_key(endpoint: str, params: Mapping[str, Any]) -> str:
        serialized = json.dumps(
            {"endpoint": endpoint, "params": dict(params)},
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _validate_payload(endpoint: str, payload: Any) -> dict[str, Any]:
    """Normalize You.com's varied response shapes into a uniform envelope.

    * ``/v1/search``   — ``{"results": {"web": [...], "news": [...]}}``
    * ``/v1/contents`` — bare array of page objects
    * ``/v1/research`` — ``{"output": {"sources": [...]}}``
    """
    if isinstance(payload, list):
        # ``/v1/contents`` returns a bare array.
        return {"results": [dict(row) for row in payload if isinstance(row, Mapping)]}
    if not isinstance(payload, Mapping):
        raise YouError(
            "You.com response is not an object or array",
            endpoint=endpoint,
            code="INVALID_RESPONSE",
        )
    normalized = dict(payload)
    results_obj = normalized.get("results")
    if isinstance(results_obj, Mapping):
        flattened: list[dict[str, Any]] = []
        for section in ("web", "news"):
            section_rows = results_obj.get(section)
            if isinstance(section_rows, list):
                flattened.extend(dict(row) for row in section_rows if isinstance(row, Mapping))
        normalized["results"] = flattened
    elif results_obj is None:
        output = normalized.get("output")
        if isinstance(output, Mapping):
            sources = output.get("sources")
            if isinstance(sources, list):
                normalized["results"] = [dict(row) for row in sources if isinstance(row, Mapping)]
            else:
                normalized["results"] = []
        else:
            normalized["results"] = []
    return normalized


def _unpack_result(result: Any) -> tuple[int, Any, Mapping[str, Any]]:
    if not isinstance(result, tuple) or len(result) < 2:
        raise YouError(
            "You.com transport must return (status, payload[, headers])",
            endpoint="UNKNOWN",
            code="TRANSPORT_CONTRACT",
        )
    headers = result[2] if len(result) >= 3 and isinstance(result[2], Mapping) else {}
    return int(result[0]), result[1], headers


def _decode(raw: str) -> Any:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def _retry_after(headers: Mapping[str, Any]) -> float | None:
    for key, value in headers.items():
        if str(key).lower() == "retry-after":
            try:
                return float(value)
            except (TypeError, ValueError):
                return None
    return None


def _credits(usage: Mapping[str, Any]) -> float | None:
    value = usage.get("credits")
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _redact(value: str, api_key: str) -> str:
    message = str(value)
    return message.replace(api_key, "[REDACTED]")[:500] if api_key else message[:500]


def _response_error(
    prefix: str,
    endpoint: str,
    status: int,
    payload: Any,
    api_key: str,
    retryable: bool,
) -> YouError:
    body = json.dumps(payload, default=str, ensure_ascii=False)[:300]
    return YouError(
        _redact(f"{prefix} status={status} endpoint={endpoint} body={body}", api_key),
        endpoint=endpoint,
        status=status,
        code="HTTP_ERROR",
        retryable=retryable,
    )


__all__ = ["YouClient", "YouError", "YouResponse", "RESEARCH_ANSWER_MAX_CHARS", "RESEARCH_ANSWER_PREFIX", "truncate_research_answer"]
