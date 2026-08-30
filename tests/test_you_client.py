"""Offline contract tests for the server-side You.com context client."""
from __future__ import annotations

import pytest

from idx_leadership.data import RawCache
from idx_leadership.providers.ledger import RequestLedger
from idx_leadership.providers.you_client import YouClient, YouError


def _client(tmp_path, transport, **kwargs):
    return YouClient(
        api_key="YOU_SECRET",
        allow_live=True,
        transport=transport,
        cache=RawCache(root=tmp_path / "cache"),
        ledger=RequestLedger(path=tmp_path / "ledger.jsonl"),
        backoff_seconds=0.0,
        **kwargs,
    )


def test_search_uses_api_key_header_and_targets_search_base(tmp_path):
    seen = {}

    def transport(method, url, params, headers):
        seen.update({"method": method, "url": url, "params": params, "headers": headers})
        return 200, {
            "results": {
                "web": [
                    {
                        "title": "IDX",
                        "url": "https://idx.co.id/example",
                        "description": "context",
                        "snippets": ["snippet one"],
                    }
                ],
                "news": [],
            },
            "metadata": {"search_uuid": "abc", "query": params["query"]},
        }

    client = _client(tmp_path, transport)
    response = client.search("IDX sector taxonomy", count=5, include_domains=["idx.co.id"])

    assert seen["method"] == "POST"
    assert seen["url"] == "https://ydc-index.io/v1/search"
    assert seen["headers"]["X-API-Key"] == "YOU_SECRET"
    assert "YOU_SECRET" not in str(seen["params"])
    assert seen["params"]["include_domains"] == ["idx.co.id"]
    assert response.results[0]["url"] == "https://idx.co.id/example"
    assert response.results[0]["_section" if False else "title"] == "IDX"


def test_search_context_marks_web_evidence_non_quantitative(tmp_path):
    def transport(method, url, params, headers):
        return 200, {
            "results": {
                "web": [
                    {
                        "title": "IDX",
                        "url": "https://idx.co.id/example",
                        "description": "context",
                    }
                ],
                "news": [],
            },
        }

    records = _client(tmp_path, transport).search_context(
        "IDX sector taxonomy", max_results=3
    )
    assert records[0]["source_type"] == "WEB_CONTEXT"
    assert records[0]["quantitative_use"] is False
    assert records[0]["provider"] == "you"


def test_research_targets_research_base_and_returns_citations(tmp_path):
    seen = {}

    def transport(method, url, params, headers):
        seen.update({"method": method, "url": url, "params": params})
        return 200, {
            "output": {
                "content": "IDX listed companies disclosure [[1]]",
                "content_type": "text",
                "sources": [
                    {
                        "url": "https://www.idx.co.id/en/news/",
                        "title": "IDX official",
                        "snippets": ["official disclosure data"],
                    },
                ],
            },
            "warnings": [],
        }

    response = _client(tmp_path, transport).research(
        "IDX listed companies disclosure requirements",
        research_effort="lite",
    )

    assert seen["url"] == "https://api.you.com/v1/research"
    assert seen["params"]["research_effort"] == "lite"
    assert response.endpoint == "/v1/research"
    assert response.answer is not None
    assert "IDX listed companies" in response.answer
    assert response.results[0]["url"] == "https://www.idx.co.id/en/news/"


def test_research_frontier_requires_background(tmp_path):
    client = _client(tmp_path, lambda *a: pytest.fail("transport should not be called"))
    with pytest.raises(YouError, match="background=true"):
        client.research("deep dive", research_effort="frontier")


def test_research_lite_rejects_output_schema(tmp_path):
    client = _client(tmp_path, lambda *a: pytest.fail("transport should not be called"))
    with pytest.raises(YouError, match="output_schema"):
        client.research(
            "quick question",
            research_effort="lite",
            output_schema={"type": "object", "properties": {}},
        )


def test_search_rejects_combined_domain_filters(tmp_path):
    client = _client(tmp_path, lambda *a: pytest.fail("transport should not be called"))
    with pytest.raises(YouError, match="cannot be combined"):
        client.search(
            "probe", include_domains=["a.com"], exclude_domains=["b.com"]
        )


def test_extract_wraps_bare_array_response(tmp_path):
    def transport(method, url, params, headers):
        return 200, [
            {
                "url": "https://idx.co.id/en/news/",
                "title": "IDX news",
                "markdown": "content here",
            },
        ]

    response = _client(tmp_path, transport).extract(
        ["https://idx.co.id/en/news/"], formats=["markdown"]
    )

    assert response.endpoint == "/v1/contents"
    assert response.results[0]["title"] == "IDX news"
    assert response.results[0]["markdown"] == "content here"


def test_cache_hit_skips_second_request_and_does_not_persist_key(tmp_path):
    calls = {"count": 0}

    def transport(method, url, params, headers):
        calls["count"] += 1
        return 200, {
            "results": {
                "web": [{"url": "https://idx.co.id/example", "title": "x"}],
                "news": [],
            }
        }

    client = _client(tmp_path, transport)
    first = client.search("IDX cache probe")
    second = client.search("IDX cache probe")

    assert calls["count"] == 1
    assert client.http_requests_made == 1
    assert first.cache_hit is False
    assert second.cache_hit is True
    assert "YOU_SECRET" not in str(second.to_dict())


def test_missing_credential_fails_before_transport(tmp_path):
    client = YouClient(
        api_key="",
        allow_live=True,
        transport=lambda *args: pytest.fail("transport should not be called"),
        cache=RawCache(root=tmp_path / "cache"),
        ledger=RequestLedger(path=tmp_path / "ledger.jsonl"),
    )
    with pytest.raises(YouError, match="YOU_API_KEY"):
        client.search("credential probe")


def test_rate_limit_retries_with_bounded_backoff(tmp_path):
    calls = {"count": 0}

    def transport(method, url, params, headers):
        calls["count"] += 1
        if calls["count"] == 1:
            return 429, {"error": "rate limited"}, {"Retry-After": "0"}
        return 200, {"results": {"web": [], "news": []}}

    response = _client(tmp_path, transport, max_retries=1).search("retry probe")
    assert response.endpoint == "/v1/search"
    assert calls["count"] == 2


def test_request_cap_counts_retries_and_blocks_before_transport(tmp_path):
    calls = {"count": 0}

    def transport(method, url, params, headers):
        calls["count"] += 1
        return 429, {"error": "rate limited"}, {"Retry-After": "0"}

    client = _client(tmp_path, transport, max_retries=2, max_http_requests=1)
    with pytest.raises(YouError, match="request cap reached"):
        client.search("bounded request probe")

    assert calls["count"] == 1
    assert client.http_requests_made == 1


def test_malformed_response_is_rejected(tmp_path):
    def transport(method, url, params, headers):
        return 200, "not an object or array"

    with pytest.raises(YouError, match="not an object or array"):
        _client(tmp_path, transport).search("malformed probe")


def test_research_includes_source_control_when_provided(tmp_path):
    seen = {}

    def transport(method, url, params, headers):
        seen["params"] = params
        return 200, {
            "output": {"content": "ok", "content_type": "text", "sources": []},
            "warnings": [],
        }

    _client(tmp_path, transport).research(
        "IDX disclosure",
        research_effort="standard",
        source_include_domains=["idx.co.id", "ojk.go.id"],
        source_country="ID",
        source_freshness="month",
    )

    source_control = seen["params"]["source_control"]
    assert source_control["include_domains"] == ["idx.co.id", "ojk.go.id"]
    assert source_control["country"] == "ID"
    assert source_control["freshness"] == "month"
