"""Search-agent discovery and first-party retrieval for IDX Daily Statistics.

This module is the boundary between the project's web-search agents and the
quantitative PDF parser. Search results and crawl content are used only to
locate an official IDX publication. Numeric values are never read from those
responses. The selected PDF is retrieved locally, verified as a first-party
PDF, and only then uploaded to LlamaParse.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
import hashlib
import os
from pathlib import Path
import re
import tempfile
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from .idx_statistics import IDX_STATISTICS_INDEX_URL
from .tavily_client import TavilyClient, TavilyError, TavilyResponse
from .you_client import YouClient, YouError, YouResponse


DISCOVERY_SCHEMA_VERSION = "idx-daily-statistics-discovery-v1"
_FIRST_PARTY_HOSTS = {"idx.co.id", "www.idx.co.id"}
_PDF_LINK_RE = re.compile(r"https?://[^\s\"'<>]+?\.pdf(?:\?[^\s\"'<>]*)?", re.I)
_COMPACT_DATE_RE = re.compile(r"(?:ds|daily)[_/-]?(\d{2})(\d{2})(\d{2})", re.I)
_ISO_DATE_RE = re.compile(r"20\d{2}[-/]\d{2}[-/]\d{2}")
_MONTHS = {
    "jan": 1,
    "january": 1,
    "januari": 1,
    "feb": 2,
    "february": 2,
    "februari": 2,
    "mar": 3,
    "march": 3,
    "maret": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "mei": 5,
    "jun": 6,
    "june": 6,
    "juni": 6,
    "jul": 7,
    "july": 7,
    "juli": 7,
    "aug": 8,
    "august": 8,
    "agustus": 8,
    "sep": 9,
    "september": 9,
    "oct": 10,
    "okt": 10,
    "october": 10,
    "oktober": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "des": 12,
    "december": 12,
    "desember": 12,
}


class IDXDiscoveryError(ValueError):
    """Raised when search/retrieval cannot establish an official PDF."""


@dataclass(frozen=True)
class RetrievedIDXPDF:
    """A locally verified first-party PDF and its retrieval evidence."""

    url: str
    path: Path
    retrieved_at: str
    byte_count: int
    sha256: str
    content_type: str | None
    method: str = "first_party_http_download"

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": "READY",
            "method": self.method,
            "url": self.url,
            "retrieved_at": self.retrieved_at,
            "file_name": self.path.name,
            "byte_count": self.byte_count,
            "sha256": self.sha256,
            "content_type": self.content_type,
            "quantitative_use": False,
            "note": "Retrieved bytes are uploaded to LlamaParse; search/crawl text is not used as numeric evidence.",
        }


@dataclass(frozen=True)
class IDXDiscoveryResult:
    """Selected official PDF plus bounded search/crawl/retrieval provenance."""

    as_of: str
    pdf_url: str
    local_pdf: RetrievedIDXPDF
    provenance: dict[str, Any]


def _assert_first_party_url(url: str, *, pdf: bool = False) -> str:
    clean = str(url or "").strip()
    parsed = urlparse(clean)
    if parsed.scheme != "https" or parsed.hostname not in _FIRST_PARTY_HOSTS:
        raise IDXDiscoveryError(
            "discovery selected a non-first-party URL; only HTTPS idx.co.id is allowed"
        )
    if pdf and not parsed.path.lower().endswith(".pdf"):
        raise IDXDiscoveryError("discovery selected a non-PDF IDX URL")
    return clean


def _parse_date_from_text(value: str) -> date | None:
    text = str(value or "")
    iso = _ISO_DATE_RE.search(text)
    if iso:
        try:
            return date.fromisoformat(iso.group(0).replace("/", "-"))
        except ValueError:
            pass
    compact = _COMPACT_DATE_RE.search(text)
    if compact:
        yy, month, day = (int(part) for part in compact.groups())
        try:
            return date(2000 + yy, month, day)
        except ValueError:
            pass
    match = re.search(r"\b([0-3]?\d)\s+([A-Za-z]+)\s+(20\d{2})\b", text)
    if match:
        day, month_name, year = match.groups()
        month = _MONTHS.get(month_name.lower())
        if month is not None:
            try:
                return date(int(year), month, int(day))
            except ValueError:
                pass
    return None


def _candidate_date(row: Mapping[str, Any], url: str) -> date | None:
    for value in (url, row.get("title"), row.get("name"), row.get("content")):
        parsed = _parse_date_from_text(str(value or ""))
        if parsed is not None:
            return parsed
    return None


def _urls_from_row(row: Mapping[str, Any], *, base_url: str) -> list[str]:
    values: list[str] = []
    direct = row.get("url")
    if isinstance(direct, str) and direct.strip():
        values.append(urljoin(base_url, direct.strip()))
    for key in ("content", "markdown", "text", "raw_content"):
        value = row.get(key)
        if isinstance(value, str):
            values.extend(_PDF_LINK_RE.findall(value))
    return values


def select_daily_statistics_pdf(
    rows: Sequence[Mapping[str, Any]],
    *,
    target_as_of: str | None = None,
) -> tuple[str, str]:
    """Select an official, date-matched PDF from search/crawl link rows.

    Returns ``(url, as_of)``. This function only uses links and labels for
    discovery; it does not inspect web text for market values.
    """
    target = None
    if target_as_of:
        try:
            target = date.fromisoformat(target_as_of)
        except ValueError as exc:
            raise IDXDiscoveryError(f"invalid target date: {target_as_of!r}") from exc
    candidates: dict[str, tuple[date | None, Mapping[str, Any]]] = {}
    for row in rows:
        for raw_url in _urls_from_row(row, base_url=IDX_STATISTICS_INDEX_URL):
            try:
                url = _assert_first_party_url(raw_url, pdf=True)
            except IDXDiscoveryError:
                continue
            candidate_date = _candidate_date(row, url)
            if target is not None and candidate_date != target:
                continue
            previous = candidates.get(url)
            if previous is None or (previous[0] is None and candidate_date is not None):
                candidates[url] = (candidate_date, row)
    if not candidates:
        target_label = target_as_of or "the latest dated release"
        raise IDXDiscoveryError(f"no official IDX Daily Statistics PDF found for {target_label}")
    ordered = sorted(
        candidates.items(),
        key=lambda item: (item[1][0] or date.min, item[0]),
        reverse=True,
    )
    selected_url, (selected_date, _) = ordered[0]
    if selected_date is None:
        raise IDXDiscoveryError("selected IDX PDF has no verifiable publication date")
    return selected_url, selected_date.isoformat()


def _response_summary(response: TavilyResponse | YouResponse, *, stage: str) -> dict[str, Any]:
    params = response.params
    rows = response.results
    candidates = []
    for row in rows[:20]:
        url = row.get("url")
        if not isinstance(url, str) or not url.strip():
            continue
        candidates.append(
            {
                "url": url,
                "title": str(row.get("title") or row.get("name") or "").strip()[:300],
                "date_candidate": _candidate_date(row, url).isoformat()
                if _candidate_date(row, url)
                else None,
            }
        )
    return {
        "stage": stage,
        "provider": "tavily" if isinstance(response, TavilyResponse) else "you",
        "endpoint": response.endpoint,
        "query": params.get("query"),
        "url": params.get("url") or (rows[0].get("url") if rows else None),
        "request_id": response.request_id,
        "retrieved_at": response.retrieved_at,
        "cache_hit": response.cache_hit,
        "credits": response.credits_used,
        "result_count": len(rows),
        "candidates": candidates,
        "quantitative_use": False,
    }


def retrieve_idx_pdf(
    url: str,
    destination: Path,
    *,
    timeout: int = 30,
    max_bytes: int = 25 * 1024 * 1024,
) -> RetrievedIDXPDF:
    """Download and verify an official IDX PDF before parser upload."""
    clean_url = _assert_first_party_url(url, pdf=True)
    if max_bytes < 1024:
        raise IDXDiscoveryError("max_bytes is too small for an IDX PDF")
    request = Request(
        clean_url,
        headers={
            "Accept": "application/pdf,application/octet-stream;q=0.9,*/*;q=0.1",
            "Accept-Language": "id-ID,id;q=0.9,en;q=0.7",
            "Referer": IDX_STATISTICS_INDEX_URL,
            "User-Agent": "IDXLeadershipDiffusion/0.2 (+official-release-retrieval)",
        },
    )
    try:
        with urlopen(request, timeout=max(1, int(timeout))) as response:
            final_url = _assert_first_party_url(str(response.geturl() or clean_url), pdf=True)
            content_type = response.headers.get("Content-Type")
            chunks: list[bytes] = []
            total = 0
            while True:
                chunk = response.read(min(1024 * 1024, max_bytes - total + 1))
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise IDXDiscoveryError(f"IDX PDF exceeds retrieval cap of {max_bytes} bytes")
                chunks.append(chunk)
    except IDXDiscoveryError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise IDXDiscoveryError(f"official IDX PDF retrieval failed: {type(exc).__name__}") from exc
    content = b"".join(chunks)
    if not content.startswith(b"%PDF-"):
        raise IDXDiscoveryError("official IDX retrieval returned non-PDF content")
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        Path(temporary_name).replace(destination)
    finally:
        temporary = Path(temporary_name)
        if temporary.exists():
            temporary.unlink()
    return RetrievedIDXPDF(
        url=final_url,
        path=destination,
        retrieved_at=datetime.now(timezone.utc).isoformat(),
        byte_count=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
        content_type=content_type,
    )


def verify_local_idx_pdf(
    url: str,
    path: Path,
    *,
    max_bytes: int = 25 * 1024 * 1024,
    method: str = "browser_download",
) -> RetrievedIDXPDF:
    """Verify a PDF retrieved by a browser session without re-downloading it."""
    clean_url = _assert_first_party_url(url, pdf=True)
    local_path = Path(path).expanduser()
    if not local_path.is_file() or local_path.suffix.lower() != ".pdf":
        raise IDXDiscoveryError("browser-retrieved IDX PDF is missing or has no .pdf extension")
    size = local_path.stat().st_size
    if size > max_bytes:
        raise IDXDiscoveryError(f"browser-retrieved IDX PDF exceeds retrieval cap of {max_bytes} bytes")
    with local_path.open("rb") as handle:
        content = handle.read(max_bytes + 1)
    if not content.startswith(b"%PDF-"):
        raise IDXDiscoveryError("browser-retrieved IDX file is not a PDF")
    return RetrievedIDXPDF(
        url=clean_url,
        path=local_path,
        retrieved_at=datetime.now(timezone.utc).isoformat(),
        byte_count=size,
        sha256=hashlib.sha256(content).hexdigest(),
        content_type="application/pdf",
        method=method,
    )


def _search_query(target_as_of: str | None) -> str:
    if target_as_of:
        parsed = date.fromisoformat(target_as_of)
        label = parsed.strftime("%d %B %Y")
        compact = f"ds_{parsed.strftime('%y%m%d')}"
        return f'IDX Daily Statistics "{label}" {compact} PDF site:idx.co.id'
    return 'latest IDX Daily Statistics PDF site:idx.co.id'


def discover_and_retrieve_idx_daily_statistics(
    *,
    target_as_of: str | None = None,
    search_provider: str = "auto",
    destination: Path,
    allow_live: bool = False,
    allow_credit_spend: bool = False,
    max_search_results: int = 10,
    max_crawl_results: int = 5,
    max_http_requests: int = 3,
    resolved_pdf_url: str | None = None,
    local_pdf_path: Path | None = None,
    tavily_client_factory: Callable[[], TavilyClient] | None = None,
    you_client_factory: Callable[[], YouClient] | None = None,
) -> IDXDiscoveryResult:
    """Run bounded search → crawl/contents → retrieve for one release."""
    if not allow_live:
        raise IDXDiscoveryError("search-agent live requests are blocked; pass --allow-search-live")
    if not allow_credit_spend:
        raise IDXDiscoveryError(
            "search-agent credit spend is blocked; pass --allow-search-credit-spend"
        )
    if search_provider not in {"auto", "tavily", "you"}:
        raise IDXDiscoveryError(f"unsupported search provider: {search_provider!r}")
    query = _search_query(target_as_of)
    if search_provider == "auto":
        if os.environ.get("TAVILY_API_KEY", "").strip():
            search_provider = "tavily"
        elif os.environ.get("YOU_API_KEY", "").strip():
            search_provider = "you"
        else:
            raise IDXDiscoveryError("auto search provider found neither TAVILY_API_KEY nor YOU_API_KEY")
    provenance: dict[str, Any] = {
        "schema_version": DISCOVERY_SCHEMA_VERSION,
        "status": "READY_WITH_GAPS",
        "search_provider": search_provider,
        "query": query,
        "search": None,
        "crawl": None,
        "retrieve": None,
        "quantitative_use": False,
        "limitations": [
            "Search-agent and crawl output are discovery evidence only; no numeric metric is read from them.",
            "The selected first-party PDF bytes are uploaded to LlamaParse for numeric extraction.",
        ],
    }
    rows: list[Mapping[str, Any]] = []
    if search_provider == "tavily":
        client = tavily_client_factory() if tavily_client_factory else TavilyClient(
            allow_live=True, max_http_requests=max_http_requests
        )
        search = client.search(
            query,
            search_depth="basic",
            topic="finance",
            max_results=max_search_results,
            include_domains=["idx.co.id"],
            include_raw_content=False,
        )
        rows.extend(search.results)
        provenance["search"] = _response_summary(search, stage="search")
        crawl = client.crawl(
            IDX_STATISTICS_INDEX_URL,
            max_depth=1,
            max_breadth=min(5, max_crawl_results),
            limit=max_crawl_results,
            select_paths=[r"/id/data-pasar/laporan-statistik/statistik/"],
            allow_external=False,
            instructions="Find dated official IDX Daily Statistics PDF publication links only.",
        )
        rows.extend(crawl.results)
        provenance["crawl"] = _response_summary(crawl, stage="crawl")
    else:
        client = you_client_factory() if you_client_factory else YouClient(
            allow_live=True, max_http_requests=max_http_requests
        )
        search = client.search(
            query,
            count=max_search_results,
            include_domains=["idx.co.id"],
            extraction_mode="full_page",
        )
        rows.extend(search.results)
        provenance["search"] = _response_summary(search, stage="search")
        contents = client.extract([IDX_STATISTICS_INDEX_URL], formats=["markdown"])
        rows.extend(contents.results)
        crawl_summary = _response_summary(contents, stage="crawl_retrieve")
        crawl_summary["note"] = "You.com uses /v1/contents for bounded crawl/retrieval; the existing client has no separate crawl endpoint."
        provenance["crawl"] = crawl_summary
    try:
        pdf_url, as_of = select_daily_statistics_pdf(rows, target_as_of=target_as_of)
        selection_source = "search_or_bounded_crawl_link"
    except (IDXDiscoveryError, TavilyError, YouError):
        if not resolved_pdf_url:
            raise
        # Dynamic IDX pages may expose the final asset only to a browser DOM.
        # The override is still checked as a first-party, date-matched PDF URL;
        # it cannot bypass the provenance or file verification gates.
        pdf_url, as_of = select_daily_statistics_pdf(
            [{"url": resolved_pdf_url, "title": resolved_pdf_url}],
            target_as_of=target_as_of,
        )
        selection_source = "browser_resolved_dynamic_asset"
    if local_pdf_path is not None:
        local_pdf = verify_local_idx_pdf(pdf_url, local_pdf_path)
    else:
        local_pdf = retrieve_idx_pdf(pdf_url, destination)
    provenance["selected"] = {
        "pdf_url": pdf_url,
        "as_of": as_of,
        "source": selection_source,
    }
    provenance["retrieve"] = local_pdf.to_dict()
    provenance["status"] = "READY"
    return IDXDiscoveryResult(
        as_of=as_of,
        pdf_url=pdf_url,
        local_pdf=local_pdf,
        provenance=provenance,
    )


__all__ = [
    "DISCOVERY_SCHEMA_VERSION",
    "IDXDiscoveryError",
    "IDXDiscoveryResult",
    "RetrievedIDXPDF",
    "discover_and_retrieve_idx_daily_statistics",
    "retrieve_idx_pdf",
    "verify_local_idx_pdf",
    "select_daily_statistics_pdf",
]
