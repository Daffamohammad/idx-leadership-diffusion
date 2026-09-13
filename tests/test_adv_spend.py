"""Agent B — spend-safety tests with fake transports + call counting.

Retries re-reserve budget, max_http_requests caps all attempts including
retries, budget exhaustion raises BEFORE any HTTP, and a retried request
produces no duplicate paid side effects (single cache write, single ledger
entry). Zero live calls.
"""
from __future__ import annotations

import pytest

from idx_leadership.data import RawCache
from idx_leadership.models import ProviderMode
from idx_leadership.providers.ledger import RequestLedger
from idx_leadership.providers.sectors_client import SectorsClient
from idx_leadership.providers.tavily_client import TavilyClient, TavilyError
from idx_leadership.providers.you_client import YouClient, YouError
from idx_leadership.utils.errors import CreditBudgetExceeded


def _sectors(tmp_path, transport, **kwargs):
    defaults = dict(
        api_key="K", mode=ProviderMode.SECTORS_LIVE, allow_live=True,
        transport=transport, cache=RawCache(root=tmp_path / "c"),
        ledger=RequestLedger(path=tmp_path / "l.jsonl"), backoff_seconds=0.0,
    )
    defaults.update(kwargs)
    return SectorsClient(**defaults)


def test_sectors_retry_rereserves_budget_and_exhausts_fail_closed(tmp_path):
    calls = {"n": 0}

    def transport(method, url, params, headers):
        calls["n"] += 1
        if calls["n"] == 1:
            return 429, {"error": "RATE_LIMIT_EXCEEDED"}, {"Retry-After": "0"}
        return 200, {"results": []}

    client = _sectors(tmp_path, transport, max_retries=1, max_estimated_credits=1.0)
    with pytest.raises(CreditBudgetExceeded, match="credit budget exhausted"):
        client.get("/v2/close/", {})
    assert calls["n"] == 1  # second attempt never left the process
    assert client.budget_reserved_credits == pytest.approx(1.0)


def test_sectors_budget_exhaustion_raises_before_http(tmp_path):
    calls = {"n": 0}

    def transport(method, url, params, headers):
        calls["n"] += 1
        return 200, {"results": [], "pagination": {"has_next": False}}

    client = _sectors(tmp_path, transport, max_estimated_credits=1.0)
    client.get("/v2/close/", {"date": "2026-08-20"})
    with pytest.raises(CreditBudgetExceeded, match="credit budget exhausted"):
        client.get("/v2/close/", {"date": "2026-08-21"})
    assert calls["n"] == 1


def test_sectors_unknown_pricing_blocked_before_http(tmp_path):
    calls = {"n": 0}

    def transport(method, url, params, headers):
        calls["n"] += 1
        return 200, {"results": []}

    client = _sectors(tmp_path, transport, max_estimated_credits=1.0)
    with pytest.raises(CreditBudgetExceeded, match="cannot certify endpoint pricing"):
        client.get("/v2/companies/", {})
    assert calls["n"] == 0


def test_tavily_cap_enforced_including_retries(tmp_path):
    calls = {"n": 0}

    def transport(method, url, params, headers):
        calls["n"] += 1
        return 429, {"error": "rate limited"}, {"Retry-After": "0"}

    client = TavilyClient(
        api_key="K", allow_live=True, transport=transport,
        cache=RawCache(root=tmp_path / "c"), ledger=RequestLedger(path=tmp_path / "l.jsonl"),
        backoff_seconds=0.0, max_retries=2, max_http_requests=1,
    )
    with pytest.raises(TavilyError, match="request cap reached"):
        client.search("probe")
    assert calls["n"] == 1
    assert client.http_requests_made == 1


def test_you_cap_enforced_including_retries(tmp_path):
    calls = {"n": 0}

    def transport(method, url, params, headers):
        calls["n"] += 1
        return 429, {"error": "rate limited"}, {"Retry-After": "0"}

    client = YouClient(
        api_key="K", allow_live=True, transport=transport,
        cache=RawCache(root=tmp_path / "c"), ledger=RequestLedger(path=tmp_path / "l.jsonl"),
        backoff_seconds=0.0, max_retries=2, max_http_requests=1,
    )
    with pytest.raises(YouError, match="request cap reached"):
        client.search("probe")
    assert calls["n"] == 1
    assert client.http_requests_made == 1


def test_no_duplicate_paid_side_effects_on_retry(tmp_path):
    calls = {"n": 0}

    def flaky(method, url, params, headers):
        calls["n"] += 1
        if calls["n"] == 1:
            return 500, {"error": "server error"}, {}
        return 200, {"results": [{"symbol": "BBCA.JK", "close": 1.0}]}

    cache = RawCache(root=tmp_path / "c")
    ledger = RequestLedger(path=tmp_path / "l.jsonl")
    client = SectorsClient(
        api_key="K", mode=ProviderMode.SECTORS_FIXTURE, transport=flaky,
        cache=cache, ledger=ledger, backoff_seconds=0.0, max_estimated_credits=None,
    )
    response = client.get("/v2/close/", {"date": "2026-08-20"})
    assert response.status == 200
    assert calls["n"] == 2  # one retry happened
    assert len(ledger.entries()) == 1  # exactly one logical-request entry
    # Second identical request is a cache hit: no further transport.
    client.get("/v2/close/", {"date": "2026-08-20"})
    assert calls["n"] == 2
