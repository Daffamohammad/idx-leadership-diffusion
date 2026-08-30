"""Offline contract tests for the server-side Tavily context client."""
from __future__ import annotations

import pytest

from idx_leadership.data import RawCache
from idx_leadership.providers.ledger import RequestLedger
from idx_leadership.providers.tavily_client import TavilyClient, TavilyError


def _client(tmp_path, transport, **kwargs):
    return TavilyClient(
        api_key="TAVILY_SECRET",
        allow_live=True,
        transport=transport,
        cache=RawCache(root=tmp_path / "cache"),
        ledger=RequestLedger(path=tmp_path / "ledger.jsonl"),
        backoff_seconds=0.0,
        **kwargs,
    )


def test_search_uses_bearer_auth_and_records_usage(tmp_path):
    seen = {}

    def transport(method, url, params, headers):
        seen.update({"method": method, "url": url, "params": params, "headers": headers})
        return 200, {
            "query": params["query"],
            "results": [{"title": "IDX", "url": "https://idx.co.id/example", "content": "context", "score": 0.9}],
            "usage": {"credits": 1},
        }

    client = _client(tmp_path, transport)
    response = client.search("IDX sector taxonomy", include_domains=["idx.co.id"])

    assert seen["method"] == "POST"
    assert seen["headers"]["Authorization"] == "Bearer TAVILY_SECRET"
    assert "TAVILY_SECRET" not in str(seen["params"])
    assert response.credits_used == 1.0
    assert client.ledger.entries()[0].actual_credit_cost == 1.0


def test_search_context_marks_web_evidence_non_quantitative(tmp_path):
    def transport(method, url, params, headers):
        return 200, {
            "results": [{"title": "IDX", "url": "https://idx.co.id/example", "content": "context"}],
            "usage": {"credits": 1},
        }

    records = _client(tmp_path, transport).search_context(
        "IDX sector taxonomy", include_domains=["idx.co.id"]
    )
    assert records[0]["source_type"] == "WEB_CONTEXT"
    assert records[0]["quantitative_use"] is False


def test_crawl_uses_explicit_bounds_and_disables_external_links(tmp_path):
    seen = {}

    def transport(method, url, params, headers):
        seen.update({"method": method, "url": url, "params": params})
        return 200, {
            "results": [
                {
                    "url": "https://idx.co.id/en/news/example",
                    "title": "IDX source",
                    "content": "First-party context",
                }
            ],
            "usage": {"credits": 1},
        }

    response = _client(tmp_path, transport, max_http_requests=1).crawl(
        "https://www.idx.co.id/en/",
        max_depth=1,
        max_breadth=3,
        limit=2,
        select_paths=[r"/en/news/"],
        allow_external=False,
        instructions="Find official announcement pages only.",
        chunks_per_source=2,
    )

    assert response.endpoint == "/crawl"
    assert seen["method"] == "POST"
    assert seen["url"].endswith("/crawl")
    assert seen["params"]["max_depth"] == 1
    assert seen["params"]["max_breadth"] == 3
    assert seen["params"]["limit"] == 2
    assert seen["params"]["allow_external"] is False
    assert seen["params"]["select_paths"] == [r"/en/news/"]
    assert response.credits_used == 1.0


def test_crawl_rejects_unbounded_or_non_http_url(tmp_path):
    client = _client(tmp_path, lambda *args: pytest.fail("transport should not be called"))

    with pytest.raises(TavilyError, match="http:// or https://"):
        client.crawl("idx.co.id")
    with pytest.raises(TavilyError, match="max_depth"):
        client.crawl("https://idx.co.id", max_depth=6)
    with pytest.raises(TavilyError, match="max_breadth"):
        client.crawl("https://idx.co.id", max_breadth=21)
    with pytest.raises(TavilyError, match="limit"):
        client.crawl("https://idx.co.id", limit=0)


def test_cache_hit_skips_second_request_and_does_not_persist_key(tmp_path):
    calls = {"count": 0}

    def transport(method, url, params, headers):
        calls["count"] += 1
        return 200, {"results": [{"url": "https://idx.co.id/example"}], "usage": {"credits": 1}}

    client = _client(tmp_path, transport)
    first = client.search("IDX cache probe")
    second = client.search("IDX cache probe")

    assert calls["count"] == 1
    assert client.http_requests_made == 1
    assert first.cache_hit is False
    assert second.cache_hit is True
    assert "TAVILY_SECRET" not in str(second.to_dict())


def test_missing_credential_fails_before_transport(tmp_path):
    client = TavilyClient(
        api_key="",
        allow_live=True,
        transport=lambda *args: pytest.fail("transport should not be called"),
        cache=RawCache(root=tmp_path / "cache"),
        ledger=RequestLedger(path=tmp_path / "ledger.jsonl"),
    )
    with pytest.raises(TavilyError, match="TAVILY_API_KEY"):
        client.search("credential probe")


def test_rate_limit_retries_with_bounded_backoff(tmp_path):
    calls = {"count": 0}

    def transport(method, url, params, headers):
        calls["count"] += 1
        if calls["count"] == 1:
            return 429, {"error": "rate limited"}, {"Retry-After": "0"}
        return 200, {"results": [], "usage": {"credits": 1}}

    response = _client(tmp_path, transport, max_retries=1).search("retry probe")
    assert response.endpoint == "/search"
    assert calls["count"] == 2


def test_request_cap_counts_retries_and_blocks_before_transport(tmp_path):
    calls = {"count": 0}

    def transport(method, url, params, headers):
        calls["count"] += 1
        return 429, {"error": "rate limited"}, {"Retry-After": "0"}

    client = _client(tmp_path, transport, max_retries=2, max_http_requests=1)
    with pytest.raises(TavilyError, match="request cap reached"):
        client.search("bounded request probe")

    assert calls["count"] == 1
    assert client.http_requests_made == 1


def test_malformed_response_is_rejected(tmp_path):
    def transport(method, url, params, headers):
        return 200, {"results": ["not an object"]}

    with pytest.raises(TavilyError, match="not an object"):
        _client(tmp_path, transport).search("malformed probe")
