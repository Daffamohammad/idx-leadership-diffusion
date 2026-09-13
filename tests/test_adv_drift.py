"""Agent B — malicious provider-response tests (contract drift via fakes).

Missing results, bad URLs, non-advancing pagination (must terminate via page
cap / raise, never loop forever), oversized payloads, no-retry-on-4xx, and
Retry-After honor — all against Sectors/Tavily/You clients with injected
transports. Zero live calls.
"""
from __future__ import annotations

import time

import pytest

from idx_leadership.data import RawCache
from idx_leadership.models import ProviderMode
from idx_leadership.providers.ledger import RequestLedger
from idx_leadership.providers.sectors_client import SectorsClient
from idx_leadership.providers.tavily_client import TavilyClient, TavilyError
from idx_leadership.providers.you_client import YouClient, YouError
from idx_leadership.utils.errors import ProviderError


def _sectors(tmp_path, transport, **kwargs):
    defaults = dict(
        api_key="K", mode=ProviderMode.SECTORS_FIXTURE, transport=transport,
        cache=RawCache(root=tmp_path / "c"), ledger=RequestLedger(path=tmp_path / "l.jsonl"),
        backoff_seconds=0.0,
    )
    defaults.update(kwargs)
    return SectorsClient(**defaults)


def _tavily(tmp_path, transport, **kwargs):
    return TavilyClient(
        api_key="K", allow_live=True, transport=transport,
        cache=RawCache(root=tmp_path / "c"), ledger=RequestLedger(path=tmp_path / "l.jsonl"),
        backoff_seconds=0.0, **kwargs,
    )


def _you(tmp_path, transport, **kwargs):
    return YouClient(
        api_key="K", allow_live=True, transport=transport,
        cache=RawCache(root=tmp_path / "c"), ledger=RequestLedger(path=tmp_path / "l.jsonl"),
        backoff_seconds=0.0, **kwargs,
    )


def test_sectors_missing_results_tolerated_as_empty_frame(tmp_path):
    client = _sectors(tmp_path, lambda m, u, p, h: (200, {"results": []}))
    response = client.get("/v2/close/", {"date": "2026-08-20"})
    assert response.status == 200
    assert response.rows == 0


def test_tavily_missing_results_normalized_to_empty(tmp_path):
    client = _tavily(tmp_path, lambda m, u, p, h: (200, {"usage": {}}))
    assert client.search("probe").results == []


def test_you_missing_results_normalized_to_empty(tmp_path):
    client = _you(tmp_path, lambda m, u, p, h: (200, {}))
    assert client.search("probe").results == []
    assert client.search_context("probe") == []


def test_tavily_bad_url_result_rejected(tmp_path):
    def transport(method, url, params, headers):
        return 200, {"results": [{"title": "no url here"}], "usage": {}}

    with pytest.raises(TavilyError, match="no URL"):
        _tavily(tmp_path, transport).search("probe")


def test_you_bad_url_result_skipped_not_promoted(tmp_path):
    def transport(method, url, params, headers):
        return 200, {"results": {"web": [{"title": "no url"}], "news": []}}

    assert _you(tmp_path, transport).search_context("probe") == []


def test_sectors_non_advancing_pagination_raises_fail_closed(tmp_path):
    def stuck(method, url, params, headers):
        return 200, {
            "results": [{"symbol": "A.JK"}],
            "pagination": {"has_next": True, "next_offset": int(params.get("offset", 0))},
        }

    with pytest.raises(ProviderError, match="did not advance"):
        _sectors(tmp_path, stuck).paginate("/v2/close/", {"limit": 30}, page_limit=3)


def test_sectors_has_next_forever_terminates_at_page_cap(tmp_path):
    calls = {"n": 0}

    def advancing(method, url, params, headers):
        calls["n"] += 1
        offset = int(params.get("offset", 0))
        limit = int(params.get("limit", 30))
        return 200, {
            "results": [{"symbol": f"T{offset}.JK"}],
            "pagination": {"has_next": True, "next_offset": offset + limit},
        }

    client = _sectors(tmp_path, advancing)
    rows = client.paginate("/v2/close/", {"limit": 30}, page_limit=3)
    assert calls["n"] == 3
    assert len(rows) == 3
    assert client.last_pagination_diagnostics["capped_by_max_pages"] is True
    assert client.last_pagination_diagnostics["completeness"] == "PARTIAL"


def test_sectors_paginate_has_default_page_cap(tmp_path):
    import inspect

    from idx_leadership.providers import sectors_client as mod

    source = inspect.getsource(mod.SectorsClient.paginate)
    assert "DEFAULT" in source and "page_limit is None" in source


def test_oversized_payload_rejected_or_bounded(tmp_path):
    def big(method, url, params, headers):
        return 200, {
            "results": [
                {"title": "t", "url": "https://idx.co.id/x", "content": "y"}
                for _ in range(50_000)
            ],
            "usage": {},
        }

    with pytest.raises((TavilyError, ProviderError)):
        _tavily(tmp_path, big).search("probe")


@pytest.mark.parametrize("status", [400, 403, 404, 422])
def test_no_retry_on_4xx_sectors(tmp_path, status):
    calls = {"n": 0}

    def transport(method, url, params, headers):
        calls["n"] += 1
        return status, {"error": "bad"}

    with pytest.raises(ProviderError):
        _sectors(tmp_path, transport, max_retries=3).get("/v2/close/", {})
    assert calls["n"] == 1


@pytest.mark.parametrize("status", [400, 403, 404, 422])
def test_no_retry_on_4xx_tavily_you(tmp_path, status):
    for make in (_tavily, _you):
        calls = {"n": 0}

        def transport(method, url, params, headers):
            calls["n"] += 1
            return status, {"error": "bad"}

        with pytest.raises((TavilyError, YouError)):
            make(tmp_path, transport, max_retries=3).search("probe")
        assert calls["n"] == 1


def test_retry_after_honored_tavily(tmp_path, monkeypatch):
    sleeps = []
    monkeypatch.setattr(time, "sleep", lambda s: sleeps.append(s))
    calls = {"n": 0}

    def transport(method, url, params, headers):
        calls["n"] += 1
        if calls["n"] == 1:
            return 429, {"error": "rate limited"}, {"Retry-After": "7"}
        return 200, {"results": [], "usage": {}}

    _tavily(tmp_path, transport, max_retries=1).search("probe")
    assert calls["n"] == 2
    assert sleeps and sleeps[0] == pytest.approx(7.0)


def test_retry_after_honored_sectors(tmp_path, monkeypatch):
    sleeps = []
    monkeypatch.setattr(time, "sleep", lambda s: sleeps.append(s))
    calls = {"n": 0}

    def transport(method, url, params, headers):
        calls["n"] += 1
        if calls["n"] == 1:
            return 429, {"error": "RATE_LIMIT_EXCEEDED"}, {"Retry-After": "5"}
        return 200, {"results": []}

    _sectors(tmp_path, transport, max_retries=1).get("/v2/close/", {})
    assert calls["n"] == 2
    assert sleeps and sleeps[0] == pytest.approx(5.0)


def test_retry_after_honored_you(tmp_path, monkeypatch):
    sleeps = []
    monkeypatch.setattr(time, "sleep", lambda s: sleeps.append(s))
    calls = {"n": 0}

    def transport(method, url, params, headers):
        calls["n"] += 1
        if calls["n"] == 1:
            return 429, {"error": "rate limited"}, {"Retry-After": "3"}
        return 200, {"results": {"web": [], "news": []}}

    _you(tmp_path, transport, max_retries=1).search("probe")
    assert calls["n"] == 2
    assert sleeps and sleeps[0] == pytest.approx(3.0)
