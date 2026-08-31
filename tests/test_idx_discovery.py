"""Offline contracts for search-agent discovery and first-party retrieval."""
from __future__ import annotations

from pathlib import Path

import pytest

import idx_leadership.providers.idx_discovery as discovery
from idx_leadership.providers.idx_discovery import (
    IDXDiscoveryError,
    RetrievedIDXPDF,
    discover_and_retrieve_idx_daily_statistics,
    retrieve_idx_pdf,
    select_daily_statistics_pdf,
    verify_local_idx_pdf,
)
from idx_leadership.providers.tavily_client import TavilyResponse


PDF_URL = "https://www.idx.co.id/Media/liskz5kp/ds_260828.pdf"


def test_selection_is_first_party_and_date_matched():
    url, as_of = select_daily_statistics_pdf(
        [
            {"url": "https://example.com/ds_260828.pdf", "title": "wrong"},
            {"url": PDF_URL, "title": "IDX Daily Statistics Friday, 28 August 2026"},
            {"url": "https://www.idx.co.id/Media/old/ds_260827.pdf", "title": "old"},
        ],
        target_as_of="2026-08-28",
    )
    assert url == PDF_URL
    assert as_of == "2026-08-28"


def test_selection_fails_closed_when_target_release_is_not_found():
    with pytest.raises(IDXDiscoveryError, match="no official IDX Daily Statistics PDF"):
        select_daily_statistics_pdf(
            [{"url": "https://www.idx.co.id/Media/old/ds_260827.pdf", "title": "old"}],
            target_as_of="2026-08-28",
        )


def test_retrieve_verifies_pdf_and_writes_atomic_file(tmp_path: Path, monkeypatch):
    class FakeHeaders:
        def get(self, key, default=None):
            return {"Content-Type": "application/pdf"}.get(key, default)

    class FakeResponse:
        headers = FakeHeaders()

        def __init__(self):
            self.chunks = [b"%PDF-1.7 fixture", b""]

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def geturl(self):
            return PDF_URL

        def read(self, size=-1):
            return self.chunks.pop(0)

    monkeypatch.setattr(discovery, "urlopen", lambda *args, **kwargs: FakeResponse())
    destination = tmp_path / "ds_260828.pdf"
    result = retrieve_idx_pdf(PDF_URL, destination)
    assert result.path == destination
    assert destination.read_bytes().startswith(b"%PDF-")
    assert result.byte_count == len(b"%PDF-1.7 fixture")
    assert result.sha256


def test_retrieve_rejects_html_disguised_as_pdf(tmp_path: Path, monkeypatch):
    class FakeHeaders:
        def get(self, key, default=None):
            return "text/html" if key == "Content-Type" else default

    class FakeResponse:
        headers = FakeHeaders()

        def __init__(self):
            self.chunks = [b"<html>blocked</html>", b""]

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def geturl(self):
            return PDF_URL

        def read(self, size=-1):
            return self.chunks.pop(0)

    monkeypatch.setattr(discovery, "urlopen", lambda *args, **kwargs: FakeResponse())
    with pytest.raises(IDXDiscoveryError, match="non-PDF"):
        retrieve_idx_pdf(PDF_URL, tmp_path / "ds_260828.pdf")


def test_browser_retrieval_handoff_verifies_existing_pdf(tmp_path: Path):
    local = tmp_path / "ds_260828.pdf"
    local.write_bytes(b"%PDF-1.7 browser fixture")
    result = verify_local_idx_pdf(PDF_URL, local)
    assert result.method == "browser_download"
    assert result.url == PDF_URL
    assert result.byte_count == local.stat().st_size


def test_browser_retrieval_handoff_rejects_date_mismatch(tmp_path: Path):
    local = tmp_path / "ds_260827.pdf"
    local.write_bytes(b"%PDF-1.7 browser fixture")
    with pytest.raises(IDXDiscoveryError, match="no official IDX Daily Statistics PDF"):
        # The URL itself is the date contract; a different filename does not
        # bypass it, and the target release must still be explicit.
        select_daily_statistics_pdf(
            [{"url": "https://www.idx.co.id/Media/t3qjbs3b/ds_260827.pdf"}],
            target_as_of="2026-08-28",
        )


def test_tavily_pipeline_records_search_crawl_and_retrieve(tmp_path: Path, monkeypatch):
    stages: list[str] = []

    class FakeTavily:
        def search(self, *args, **kwargs):
            stages.append("search")
            return TavilyResponse(
                endpoint="/search",
                params={"query": "target"},
                payload={
                    "results": [
                        {"url": PDF_URL, "title": "IDX Daily Statistics 28 August 2026"}
                    ]
                },
                elapsed_ms=1.0,
                request_id="search-1",
                usage={"credits": 1},
                retrieved_at="2026-08-31T00:00:00+00:00",
            )

        def crawl(self, *args, **kwargs):
            stages.append("crawl")
            return TavilyResponse(
                endpoint="/crawl",
                params={"url": discovery.IDX_STATISTICS_INDEX_URL},
                payload={"results": [{"url": discovery.IDX_STATISTICS_INDEX_URL}]},
                elapsed_ms=1.0,
                request_id="crawl-1",
                usage={"credits": 1},
                retrieved_at="2026-08-31T00:00:01+00:00",
            )

    def fake_retrieve(url, destination, **kwargs):
        stages.append("retrieve")
        assert url == PDF_URL
        return RetrievedIDXPDF(
            url=url,
            path=Path(destination),
            retrieved_at="2026-08-31T00:00:02+00:00",
            byte_count=123,
            sha256="a" * 64,
            content_type="application/pdf",
        )

    monkeypatch.setattr(discovery, "retrieve_idx_pdf", fake_retrieve)
    result = discover_and_retrieve_idx_daily_statistics(
        target_as_of="2026-08-28",
        search_provider="tavily",
        destination=tmp_path / "ds_260828.pdf",
        allow_live=True,
        allow_credit_spend=True,
        tavily_client_factory=lambda: FakeTavily(),
    )
    assert stages == ["search", "crawl", "retrieve"]
    assert result.pdf_url == PDF_URL
    assert result.as_of == "2026-08-28"
    assert result.provenance["search"]["stage"] == "search"
    assert result.provenance["crawl"]["stage"] == "crawl"
    assert result.provenance["retrieve"]["sha256"] == "a" * 64


def test_pipeline_requires_explicit_search_acknowledgements(tmp_path: Path):
    with pytest.raises(IDXDiscoveryError, match="search-agent live requests"):
        discover_and_retrieve_idx_daily_statistics(
            target_as_of="2026-08-28",
            search_provider="tavily",
            destination=tmp_path / "ds_260828.pdf",
        )
