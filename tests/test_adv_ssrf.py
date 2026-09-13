"""Agent B — SSRF URL-refusal tests for Tavily/You extract+crawl.

The clients fetch nothing directly (URLs go to the vendor API), but the
extract/crawl boundary refuses localhost, metadata-IP, IP literals and
non-http(s) schemes as defense-in-depth. Search domain scoping stays
caller-enforced by design (documented in the client docstrings); this file
proves both properties with injected fakes only — zero live calls.
"""
from __future__ import annotations

import pytest

from idx_leadership.data import RawCache
from idx_leadership.providers.ledger import RequestLedger
from idx_leadership.providers.tavily_client import TavilyClient, TavilyError
from idx_leadership.providers.you_client import YouClient, YouError

REFUSED = [
    "http://localhost/",
    "http://localhost:8080/x",
    "http://127.0.0.1/",
    "http://0.0.0.0/",
    "http://[::1]/",
    "http://[0:0:0:0:0:ffff:127.0.0.1]/",
    "https://169.254.169.254/",
    "http://169.254.169.254/latest/meta-data/",
    "http://metadata.google.internal/",
    "https://metadata.google.internal/computeMetadata/v1/",
    "http://10.0.0.1/",
    "http://192.168.1.1/x",
    "file:///etc/passwd",
    "data:text/html,hi",
    "javascript:alert(1)",
    "ftp://example.com/x",
    "gopher://example.com/x",
    "",
    "   ",
    "idx.co.id/no-scheme",
]

ALLOWED = [
    "https://idx.co.id/en/",
    "https://www.idx.co.id/en/news/example",
    "http://ojk.go.id/id/berita-dan-kegiatan/info-terkini",
]


def _tavily(tmp_path, **kwargs):
    return TavilyClient(
        api_key="K", allow_live=True,
        transport=lambda *a: pytest.fail("transport must not be called"),
        cache=RawCache(root=tmp_path / "c"), ledger=RequestLedger(path=tmp_path / "l.jsonl"),
        backoff_seconds=0.0, **kwargs,
    )


def _you(tmp_path, **kwargs):
    return YouClient(
        api_key="K", allow_live=True,
        transport=lambda *a: pytest.fail("transport must not be called"),
        cache=RawCache(root=tmp_path / "c"), ledger=RequestLedger(path=tmp_path / "l.jsonl"),
        backoff_seconds=0.0, **kwargs,
    )


@pytest.mark.parametrize("url", REFUSED)
def test_tavily_extract_refuses_unsafe_urls(tmp_path, url):
    with pytest.raises(TavilyError, match="(?i)URL|host|parseable"):
        _tavily(tmp_path).extract([url])


@pytest.mark.parametrize("url", REFUSED)
def test_tavily_crawl_refuses_unsafe_urls(tmp_path, url):
    with pytest.raises(TavilyError, match="(?i)URL|host|parseable"):
        _tavily(tmp_path).crawl(url)


@pytest.mark.parametrize("url", REFUSED)
def test_you_extract_refuses_unsafe_urls(tmp_path, url):
    with pytest.raises(YouError, match="(?i)URL|host|parseable"):
        _you(tmp_path).extract([url])


@pytest.mark.parametrize("url", ALLOWED)
def test_safe_first_party_urls_pass_validation(tmp_path, url):
    # Validation happens before transport; a fake transport proves the URL
    # was accepted without performing any live call.
    seen = {}

    def transport(method, url_, params, headers):
        seen["called"] = True
        return 200, {"results": [], "usage": {}}

    tavily = TavilyClient(
        api_key="K", allow_live=True, transport=transport,
        cache=RawCache(root=tmp_path / "c"), ledger=RequestLedger(path=tmp_path / "l.jsonl"),
        backoff_seconds=0.0,
    )
    tavily.extract([url])
    assert seen.get("called") is True


@pytest.mark.parametrize(
    "host",
    ["2130706433", "0x7f.0.0.1", "0177.0.0.1", "0x7f000001"],
    ids=["decimal", "hex-dotted", "octal-dotted", "hex-flat"],
)
def test_numeric_ip_literal_hosts_are_refused(tmp_path, host):
    # glibc inet_aton resolves these to 127.0.0.1; the guard must refuse them.
    with pytest.raises(TavilyError):
        _tavily(tmp_path).extract([f"http://{host}/"])
    with pytest.raises(YouError):
        _you(tmp_path).extract([f"http://{host}/"])


def test_search_domain_scoping_is_caller_enforced_and_documented(tmp_path):
    # By design the client forwards caller domains verbatim (no allowlist);
    # the docstring says so. Prove pass-through with a fake transport.
    seen = {}

    def transport(method, url, params, headers):
        seen["params"] = params
        return 200, {"results": [], "usage": {}}

    tavily = TavilyClient(
        api_key="K", allow_live=True, transport=transport,
        cache=RawCache(root=tmp_path / "c"), ledger=RequestLedger(path=tmp_path / "l.jsonl"),
        backoff_seconds=0.0,
    )
    tavily.search("probe", include_domains=["idx.co.id"])
    assert seen["params"]["include_domains"] == ["idx.co.id"]
    assert "caller-enforced" in (TavilyClient.search.__doc__ or "")
    assert "caller-enforced" in (YouClient.search.__doc__ or "")
