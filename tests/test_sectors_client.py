"""Tests for the Sectors HTTP client.

All tests inject a fake `transport` and a `tmp_path` cache so no network
or shared state is touched.
"""
from __future__ import annotations

import pytest

from idx_leadership.data import RawCache
from idx_leadership.providers.ledger import RequestLedger
from idx_leadership.providers.sectors_client import (
    DOCUMENTED_COST,
    SectorsClient,
    _estimated_credit_cost,
)
from idx_leadership.utils.errors import ProviderError


def _transport_ok(method, url, params, headers):
    return 200, {"results": [{"symbol": "BBCA.JK", "close": 6175}], "pagination": {"has_next": False, "next_offset": None}}


def _transport_paginated(method, url, params, headers):
    offset = int(params.get("offset", 0))
    limit = int(params.get("limit", 20))
    page = [{"symbol": f"T{offset + i}.JK", "close": 100 + offset + i} for i in range(min(limit, 5))]
    return 200, {"results": page, "pagination": {"has_next": offset + limit < 30, "next_offset": offset + limit}}


def _client(tmp_path, **kwargs):
    cache = RawCache(root=tmp_path / "cache")
    ledger = RequestLedger(path=tmp_path / "ledger.jsonl")
    defaults = dict(api_key="K", cache=cache, ledger=ledger, allow_live=True, backoff_seconds=0.0)
    defaults.update(kwargs)
    return SectorsClient(**defaults)


def test_auth_header_uses_raw_key(tmp_path):
    c = _client(tmp_path, transport=_transport_ok)
    headers = c._auth_header()
    assert headers["Authorization"] == "K"
    assert "Bearer" not in headers["Authorization"]


def test_get_with_fake_transport_returns_response(tmp_path):
    c = _client(tmp_path, transport=_transport_ok)
    resp = c.get("/v2/close/", {"date": "2026-08-20"})
    assert resp.status == 200
    assert resp.rows == 1
    assert resp.estimated_credit_cost == 1.0  # /v2/close/ is per_page
    assert resp.cache_hit is False


def test_client_builds_v2_url_once(tmp_path):
    seen = {}

    def transport(method, url, params, headers):
        seen["url"] = url
        return 200, {"results": []}

    c = _client(tmp_path, transport=transport)
    c.get("/v2/close/", {})
    assert seen["url"] == "https://api.sectors.app/v2/close/"

    # Configurations that still include `/v2` are normalized for compatibility.
    c = _client(tmp_path, base_url="https://api.sectors.app/v2", transport=transport)
    c.get("/v2/close/", {}, use_cache=False)
    assert seen["url"] == "https://api.sectors.app/v2/close/"


def test_paginate_walks_pages(tmp_path):
    c = _client(tmp_path, transport=_transport_paginated)
    rows = c.paginate("/v2/close/", {}, page_limit=10, max_rows=30)
    assert len(rows) >= 5


def test_retry_on_429(tmp_path):
    attempts = {"n": 0}

    def t(method, url, params, headers):
        attempts["n"] += 1
        if attempts["n"] < 2:
            return 429, {"error": "RATE_LIMIT_EXCEEDED"}
        return 200, {"results": []}

    c = _client(tmp_path, transport=t, max_retries=2)
    resp = c.get("/v2/close/", {})
    assert resp.status == 200
    assert attempts["n"] == 2


def test_retry_exhausted_raises(tmp_path):
    def t(method, url, params, headers):
        return 500, {"error": "server error"}

    c = _client(tmp_path, transport=t, max_retries=1)
    with pytest.raises(ProviderError):
        c.get("/v2/close/", {})


def test_non_retryable_4xx_raises_immediately(tmp_path):
    attempts = {"n": 0}

    def t(method, url, params, headers):
        attempts["n"] += 1
        return 400, {"error": "bad request"}

    c = _client(tmp_path, transport=t, max_retries=3)
    with pytest.raises(ProviderError):
        c.get("/v2/close/", {})
    assert attempts["n"] == 1


def test_live_blocked_when_disallowed(tmp_path):
    # allow_live=False raises ProviderError BEFORE attempting transport.
    def t(method, url, params, headers):
        raise AssertionError("transport should not be called")

    c = _client(tmp_path, transport=t, allow_live=False)
    with pytest.raises(ProviderError):
        c.get("/v2/close/", {})


def test_live_blocked_when_no_key_no_allow(tmp_path):
    c = SectorsClient(api_key="", cache=RawCache(root=tmp_path / "cache"),
                      ledger=RequestLedger(path=tmp_path / "ledger.jsonl"),
                      allow_live=False)
    with pytest.raises(ProviderError):
        c.get("/v2/close/", {})


def test_ledger_records_call(tmp_path):
    c = _client(tmp_path, transport=_transport_ok)
    c.get("/v2/close/", {"date": "2026-08-20"})
    entries = c.ledger.entries()
    assert len(entries) == 1
    assert entries[0].provider == "sectors"
    assert entries[0].estimated_credit_cost == 1.0


def test_raw_cache_hits_skip_transport(tmp_path):
    calls = {"n": 0}

    def t(method, url, params, headers):
        calls["n"] += 1
        return 200, {"results": [{"x": 1}], "pagination": {"has_next": False}}

    c = _client(tmp_path, transport=t)
    r1 = c.get("/v2/close/", {"date": "2026-08-20"})
    r2 = c.get("/v2/close/", {"date": "2026-08-20"})
    assert calls["n"] == 1
    assert r1.cache_hit is False
    assert r2.cache_hit is True


def test_documented_cost_table_has_no_unknown_for_used_endpoints():
    used = [
        "/v2/close/",
        "/v2/free-float/",
        "/v2/foreign-flow/{symbol}/",
        "/v2/company/corporate-actions/{symbol}/",
        "/v2/suspensions/",
    ]
    for ep in used:
        assert DOCUMENTED_COST[ep] != "unknown_verify"


def test_estimated_credit_cost_for_per_page():
    payload = {"results": [1] * 30, "pagination": {}}
    assert _estimated_credit_cost("/v2/close/", payload) == 1.0


def test_estimated_credit_cost_for_per_100_companies():
    payload = [{"x": i} for i in range(150)]
    assert _estimated_credit_cost("/v2/free-float/", payload) == 2.0  # ceil(150/100)
