"""Small, server-side Tavily client for provenance-aware web context.

Tavily is intentionally not a market-data provider in this project. This
client only returns web evidence and records it in a separate cache/ledger so
web text cannot accidentally enter quantitative features or group metrics.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import os
import threading
import time
from typing import Any, Mapping, Sequence

from ..data import RawCache
from ..utils import get_logger, load_project_env, project_root
from ..utils.errors import ProviderError
from .ledger import RequestLedger

_log = get_logger(__name__)


class TavilyError(ProviderError):
    """Structured error for a Tavily request."""

    def __init__(
        self,
        message: str,
        *,
        endpoint: str,
        status: int | None = None,
        code: str = "TAVILY_ERROR",
        retryable: bool = False,
    ) -> None:
        self.endpoint = endpoint
        self.status = status
        self.code = code
        self.retryable = retryable
        super().__init__(message)


@dataclass
class TavilyResponse:
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
        results = self.payload.get("results", [])
        return [dict(row) for row in results if isinstance(row, Mapping)]

    @property
    def credits_used(self) -> float | None:
        value = self.usage.get("credits")
        try:
            return float(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    def to_dict(self) -> dict[str, Any]:
        """Return a persisted evidence envelope with no request credential."""

        return {
            "provider": "tavily",
            "endpoint": self.endpoint,
            "query": self.params.get("query"),
            "params": dict(self.params),
            "request_id": self.request_id,
            "retrieved_at": self.retrieved_at,
            "cache_hit": self.cache_hit,
            "usage": dict(self.usage),
            "results": self.results,
            "failed_results": self.payload.get("failed_results", []),
            # If a caller explicitly requests Tavily's answer, retain it as
            # context but mark it as an unsourced synthesis. The snapshot
            # pipeline never reads this field for quantitative metrics.
            "answer": self.payload.get("answer"),
        }


class TavilyClient:
    """Bounded Tavily REST client using the ``TAVILY_API_KEY`` environment."""

    BASE_URL = "https://api.tavily.com"
    DEFAULT_TIMEOUT_SECONDS = 20
    DEFAULT_MAX_RETRIES = 2
    DEFAULT_BACKOFF_SECONDS = 1.0

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str = BASE_URL,
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
            os.environ.get("TAVILY_API_KEY", "") if api_key is None else api_key
        ).strip()
        self.base_url = (base_url or self.BASE_URL).rstrip("/")
        self.ledger = ledger or RequestLedger(
            path=project_root() / "data" / "raw" / "tavily_request_ledger.jsonl"
        )
        self.cache = cache or RawCache(project_root() / "data" / "cache" / "tavily")
        self.timeout = max(1, int(timeout))
        self.max_retries = max(0, int(max_retries))
        self.backoff_seconds = max(0.0, float(backoff_seconds))
        self.cache_ttl_seconds = cache_ttl_seconds
        self.allow_live = bool(allow_live)
        self.project_id = project_id or os.environ.get("TAVILY_PROJECT")
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
        search_depth: str = "basic",
        topic: str = "finance",
        max_results: int = 5,
        include_domains: Sequence[str] | None = None,
        exclude_domains: Sequence[str] | None = None,
        time_range: str | None = None,
        include_answer: bool | str = False,
        include_raw_content: bool | str = False,
        use_cache: bool = True,
    ) -> TavilyResponse:
        query = str(query or "").strip()
        if not query:
            raise TavilyError(
                "Tavily search query is empty",
                endpoint="/search",
                code="INVALID_QUERY",
            )
        if len(query) > 400:
            raise TavilyError(
                "Tavily search query must be at most 400 characters",
                endpoint="/search",
                code="QUERY_TOO_LONG",
            )
        if search_depth not in {"ultra-fast", "fast", "basic", "advanced"}:
            raise TavilyError(
                f"unsupported Tavily search_depth={search_depth}",
                endpoint="/search",
                code="INVALID_PARAMETER",
            )
        if not 0 <= int(max_results) <= 20:
            raise TavilyError(
                "Tavily max_results must be between 0 and 20",
                endpoint="/search",
                code="INVALID_PARAMETER",
            )
        params: dict[str, Any] = {
            "query": query,
            "search_depth": search_depth,
            "topic": topic,
            "max_results": int(max_results),
            "include_answer": include_answer,
            "include_raw_content": include_raw_content,
            "include_usage": True,
        }
        if include_domains:
            params["include_domains"] = list(include_domains)
        if exclude_domains:
            params["exclude_domains"] = list(exclude_domains)
        if time_range:
            params["time_range"] = time_range
        return self._request("/search", params, use_cache=use_cache)

    def extract(
        self,
        urls: Sequence[str],
        *,
        extract_depth: str = "basic",
        format: str = "markdown",
        query: str | None = None,
        chunks_per_source: int | None = None,
        use_cache: bool = True,
    ) -> TavilyResponse:
        clean_urls = [str(url).strip() for url in urls if str(url).strip()]
        if not clean_urls or len(clean_urls) > 20:
            raise TavilyError(
                "Tavily extract accepts between 1 and 20 URLs",
                endpoint="/extract",
                code="INVALID_URL_BATCH",
            )
        params: dict[str, Any] = {
            "urls": clean_urls,
            "extract_depth": extract_depth,
            "format": format,
        }
        if query:
            params["query"] = query[:400]
        if chunks_per_source is not None:
            if not 1 <= int(chunks_per_source) <= 5:
                raise TavilyError(
                    "chunks_per_source must be between 1 and 5",
                    endpoint="/extract",
                    code="INVALID_PARAMETER",
                )
            params["chunks_per_source"] = int(chunks_per_source)
        return self._request("/extract", params, use_cache=use_cache)

    def crawl(
        self,
        url: str,
        *,
        max_depth: int = 1,
        max_breadth: int = 5,
        limit: int = 5,
        select_paths: Sequence[str] | None = None,
        exclude_paths: Sequence[str] | None = None,
        allow_external: bool = False,
        instructions: str | None = None,
        chunks_per_source: int | None = None,
        use_cache: bool = True,
    ) -> TavilyResponse:
        """Crawl a bounded first-party site for qualitative evidence.

        Crawling is deliberately explicit and narrow.  The caller must set a
        small depth/breadth/limit, and external links are disabled by default
        so a research-context refresh cannot unexpectedly fan out across the
        web or become a market-data ingestion path.
        """

        clean_url = str(url or "").strip()
        if not clean_url.startswith(("https://", "http://")):
            raise TavilyError(
                "Tavily crawl URL must use http:// or https://",
                endpoint="/crawl",
                code="INVALID_URL",
            )
        if not 0 <= int(max_depth) <= 5:
            raise TavilyError(
                "Tavily crawl max_depth must be between 0 and 5",
                endpoint="/crawl",
                code="INVALID_PARAMETER",
            )
        if not 1 <= int(max_breadth) <= 20:
            raise TavilyError(
                "Tavily crawl max_breadth must be between 1 and 20",
                endpoint="/crawl",
                code="INVALID_PARAMETER",
            )
        if not 1 <= int(limit) <= 20:
            raise TavilyError(
                "Tavily crawl limit must be between 1 and 20",
                endpoint="/crawl",
                code="INVALID_PARAMETER",
            )
        params: dict[str, Any] = {
            "url": clean_url,
            "max_depth": int(max_depth),
            "max_breadth": int(max_breadth),
            "limit": int(limit),
            "allow_external": bool(allow_external),
            "include_usage": True,
        }
        if select_paths:
            params["select_paths"] = [str(path).strip() for path in select_paths if str(path).strip()]
        if exclude_paths:
            params["exclude_paths"] = [str(path).strip() for path in exclude_paths if str(path).strip()]
        if instructions:
            params["instructions"] = str(instructions).strip()[:400]
        if chunks_per_source is not None:
            if not 1 <= int(chunks_per_source) <= 5:
                raise TavilyError(
                    "chunks_per_source must be between 1 and 5",
                    endpoint="/crawl",
                    code="INVALID_PARAMETER",
                )
            params["chunks_per_source"] = int(chunks_per_source)
        return self._request("/crawl", params, use_cache=use_cache)

    def search_context(
        self,
        query: str,
        *,
        include_domains: Sequence[str] | None = None,
        max_results: int = 3,
        time_range: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return normalized web evidence records, separate from metrics."""

        response = self.search(
            query,
            search_depth="basic",
            topic="finance",
            max_results=max_results,
            include_domains=include_domains,
            time_range=time_range,
            include_answer=False,
            include_raw_content=False,
        )
        records: list[dict[str, Any]] = []
        for result in response.results:
            records.append(
                {
                    "source_type": "WEB_CONTEXT",
                    "provider": "tavily",
                    "url": result.get("url"),
                    "title": result.get("title"),
                    "content": result.get("content"),
                    "relevance_score": result.get("score"),
                    "retrieved_at": response.retrieved_at,
                    "request_id": response.request_id,
                    "quantitative_use": False,
                }
            )
        return records

    def _request(
        self, endpoint: str, params: dict[str, Any], *, use_cache: bool
    ) -> TavilyResponse:
        if not self.allow_live:
            raise TavilyError(
                "Tavily live request disabled (allow_live=False)",
                endpoint=endpoint,
                code="LIVE_DISABLED",
            )
        if not self.api_key:
            raise TavilyError(
                "Tavily credential missing (TAVILY_API_KEY)",
                endpoint=endpoint,
                code="CREDENTIAL_MISSING",
            )
        cache_key = self._cache_key(endpoint, params)
        if use_cache:
            cached = self.cache.get(cache_key, ttl_seconds=self.cache_ttl_seconds)
            if isinstance(cached, Mapping):
                self.ledger.record(
                    provider="tavily",
                    endpoint=endpoint,
                    request_type="POST",
                    parameters=params,
                    cache_hit=True,
                    status="ok",
                    rows_returned=len(cached.get("results", []))
                    if isinstance(cached.get("results"), list)
                    else 0,
                    elapsed_ms=0.0,
                    actual_credit_cost=0.0,
                )
                return TavilyResponse(
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
                result = self._post_json(endpoint, params)
                status, payload, headers = _unpack_result(result)
                elapsed = (time.time() - started) * 1000.0
                if status == 429 or 500 <= status < 600:
                    if attempt < self.max_retries:
                        delay = _retry_after(headers) or self.backoff_seconds * (attempt + 1)
                        time.sleep(min(30.0, max(0.0, delay)))
                        attempt += 1
                        continue
                    raise _response_error(
                        "Tavily transient response", endpoint, status, payload, self.api_key, True
                    )
                if status >= 400:
                    raise _response_error(
                        "Tavily response", endpoint, status, payload, self.api_key, False
                    )
                normalized = _validate_payload(endpoint, payload)
                normalized["_retrieved_at"] = datetime.now(timezone.utc).isoformat()
                if use_cache:
                    self.cache.set(cache_key, normalized)
                usage = normalized.get("usage")
                usage = dict(usage) if isinstance(usage, Mapping) else {}
                request_id = str(normalized.get("request_id") or "") or None
                credits = _credits(usage)
                self.ledger.record(
                    provider="tavily",
                    endpoint=endpoint,
                    request_type="POST",
                    parameters=params,
                    cache_hit=False,
                    status="ok",
                    rows_returned=len(normalized.get("results", [])),
                    elapsed_ms=elapsed,
                    actual_credit_cost=credits,
                )
                return TavilyResponse(
                    endpoint=endpoint,
                    params=dict(params),
                    payload=normalized,
                    elapsed_ms=elapsed,
                    request_id=request_id,
                    usage=usage,
                    retrieved_at=str(normalized.get("_retrieved_at")),
                )
            except TavilyError:
                raise
            except Exception as exc:  # noqa: BLE001
                if attempt < self.max_retries:
                    time.sleep(min(30.0, self.backoff_seconds * (attempt + 1)))
                    attempt += 1
                    continue
                message = _redact(str(exc), self.api_key)
                self.ledger.record(
                    provider="tavily",
                    endpoint=endpoint,
                    request_type="POST",
                    parameters=params,
                    cache_hit=False,
                    status="transport_error",
                    rows_returned=0,
                    elapsed_ms=(time.time() - started) * 1000.0,
                    error=message,
                )
                raise TavilyError(
                    f"Tavily transport error endpoint={endpoint}: {message}",
                    endpoint=endpoint,
                    code="TRANSPORT_ERROR",
                    retryable=True,
                ) from exc
        raise TavilyError(
            f"Tavily retries exhausted endpoint={endpoint}",
            endpoint=endpoint,
            code="RETRIES_EXHAUSTED",
            retryable=True,
        )

    def _reserve_http_request(self, endpoint: str) -> None:
        """Reserve one HTTP attempt, including retries, before transport."""

        with self._request_count_lock:
            if self._request_count >= self.max_http_requests:
                raise TavilyError(
                    "Tavily client request cap reached before HTTP request; "
                    f"endpoint={endpoint} cap={self.max_http_requests}",
                    endpoint=endpoint,
                    code="REQUEST_CAP_EXCEEDED",
                    retryable=False,
                )
            self._request_count += 1

    def _post_json(self, endpoint: str, params: Mapping[str, Any]) -> Any:
        if self._transport is not None:
            return self._transport(
                "POST",
                f"{self.base_url}{endpoint}",
                dict(params),
                self._headers(),
            )
        import urllib.error
        import urllib.request

        request = urllib.request.Request(
            f"{self.base_url}{endpoint}",
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
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "idx-leadership-diffusion/0.2 (+tavily-client)",
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
    if not isinstance(payload, Mapping):
        raise TavilyError(
            f"Tavily response is not an object endpoint={endpoint}",
            endpoint=endpoint,
            code="INVALID_RESPONSE",
        )
    normalized = dict(payload)
    results = normalized.get("results")
    if results is not None and not isinstance(results, list):
        raise TavilyError(
            f"Tavily results is not an array endpoint={endpoint}",
            endpoint=endpoint,
            code="INVALID_RESPONSE",
        )
    if results is None:
        normalized["results"] = []
    for index, row in enumerate(normalized["results"]):
        if not isinstance(row, Mapping):
            raise TavilyError(
                f"Tavily result {index} is not an object endpoint={endpoint}",
                endpoint=endpoint,
                code="INVALID_RESPONSE",
            )
        if endpoint == "/search" and not str(row.get("url") or "").strip():
            raise TavilyError(
                f"Tavily search result {index} has no URL endpoint={endpoint}",
                endpoint=endpoint,
                code="INVALID_RESPONSE",
            )
    return normalized


def _unpack_result(result: Any) -> tuple[int, Any, Mapping[str, Any]]:
    if not isinstance(result, tuple) or len(result) < 2:
        raise TavilyError(
            "Tavily transport must return (status, payload[, headers])",
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
) -> TavilyError:
    body = json.dumps(payload, default=str, ensure_ascii=False)[:300]
    return TavilyError(
        _redact(f"{prefix} status={status} endpoint={endpoint} body={body}", api_key),
        endpoint=endpoint,
        status=status,
        code="HTTP_ERROR",
        retryable=retryable,
    )


__all__ = ["TavilyClient", "TavilyError", "TavilyResponse"]
