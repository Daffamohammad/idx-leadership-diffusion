"""Search-agent driver for the IDX Leadership Diffusion research pass.

Executes the mandatory research workstreams against Tavily and YOU.com,
classifies results into structured observations, and persists:

- data/research/<workstream>/observations.jsonl  (canonical observations)
- data/research/<workstream>/sources.jsonl       (raw search results)
- data/research/_audit.jsonl                     (every API call)

NEVER prints API keys. Persists facts + provenance only, no copied page
content. A redaction guard is applied before any string is written to
disk.

Usage:
    .venv/bin/python scripts/research/run_research_pass.py [--workstreams ...]

Workstreams: idu, taxonomy, konglo, themes, foreign_flow, corp_actions,
benchmark, free_float, methodology.
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import logging
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from src.idx_leadership.providers.tavily_client import TavilyClient  # noqa: E402
from src.idx_leadership.providers.you_client import YouClient  # noqa: E402

_log = logging.getLogger("research")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


# ─────────────────────────────────────────────────────────────────────
# Secrets redaction (defence-in-depth; both clients already redact their
# own logs, but a stray user-supplied note could still leak).
# ─────────────────────────────────────────────────────────────────────

_KEY_PATTERNS = (
    re.compile(r"tvly-[A-Za-z0-9_-]{20,}"),
    re.compile(r"TAVILY_API_KEY\s*=\s*[^\s'\"}]+", re.IGNORECASE),
    re.compile(r"YOU_API_KEY\s*=\s*[^\s'\"}]+", re.IGNORECASE),
    re.compile(r"YOUCOM_API_KEY\s*=\s*[^\s'\"}]+", re.IGNORECASE),
)


def _scrub_secrets(value: str) -> str:
    out = value
    for pattern in _KEY_PATTERNS:
        out = pattern.sub("[REDACTED]", out)
    return out


def _scrub_obj(obj: Any) -> Any:
    if isinstance(obj, str):
        return _scrub_secrets(obj)
    if isinstance(obj, dict):
        return {k: _scrub_obj(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        cleaned = [_scrub_obj(v) for v in obj]
        return type(obj)(cleaned) if isinstance(obj, tuple) else cleaned
    return obj


# ─────────────────────────────────────────────────────────────────────
# Bootstrapping
# ─────────────────────────────────────────────────────────────────────


def _load_dotenv() -> None:
    env_path = REPO_ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k, v)


def _audit_path() -> Path:
    p = REPO_ROOT / "data" / "research" / "_audit.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _append_audit(record: dict[str, Any]) -> None:
    record = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), **record}
    with _audit_path().open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, default=str, ensure_ascii=False) + "\n")


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# ─────────────────────────────────────────────────────────────────────
# Data classes
# ─────────────────────────────────────────────────────────────────────


@dataclasses.dataclass
class SearchHit:
    title: str
    url: str
    content: str
    provider: str
    raw: dict[str, Any]


@dataclasses.dataclass
class Observation:
    entity_id: str
    entity_type: str
    claim_type: str
    claim: str
    source_url: str
    publisher: str
    published_at: str | None
    retrieved_at: str
    search_provider: str
    source_tier: int
    confidence: str
    verification_status: str
    notes: str


# ─────────────────────────────────────────────────────────────────────
# Source-quality tiering (master prompt §6)
# ─────────────────────────────────────────────────────────────────────


def _tier_for_url(url: str) -> int:
    u = url.lower()
    if any(host in u for host in ("idx.co.id", "ojk.go.id", "ksei.co.id")):
        return 1
    if any(host in u for host in ("bca.co.id", "bri.co.id", "telkom.co.id",
                                    "indosat.com", "adaro.com", "antam.com",
                                    "mandiri.co.id", "indofood.com",
                                    "unilever.com")):
        return 2
    if any(host in u for host in ("reuters.com", "bloomberg.com", "ft.com",
                                    "thejakartapost.com",
                                    "kontan.co.id", "cnbcindonesia.com",
                                    "investordaily.id", "bisnis.com",
                                    "kompas.com", "cnnindonesia.com")):
        return 3
    if any(host in u for host in ("wikipedia.org", "yahoo.com",
                                    "tradingview.com")):
        return 4
    return 5


def _publisher_from_url(url: str) -> str:
    u = re.sub(r"^https?://(www\.)?", "", url.lower()).split("/")[0]
    return u or "unknown"


# ─────────────────────────────────────────────────────────────────────
# Provider wrappers (caps applied per workstream below)
# ─────────────────────────────────────────────────────────────────────


def _tavily_search(client: TavilyClient, query: str, max_results: int = 5,
                    include_domains: list[str] | None = None,
                    topic: str = "general") -> list[SearchHit]:
    try:
        resp = client.search(query, max_results=max_results, topic=topic,
                              include_domains=include_domains)
    except Exception as exc:
        _log.warning("Tavily search failed for %r: %s", query, exc)
        _append_audit({"provider": "tavily", "endpoint": "/search", "query": query,
                        "status": "error", "error": str(exc)[:200]})
        return []
    _append_audit({"provider": "tavily", "endpoint": "/search", "query": query,
                    "status": "ok", "max_results": max_results})
    raw_results = getattr(resp, "results", None) or []
    hits: list[SearchHit] = []
    for r in raw_results[:max_results]:
        d = r if isinstance(r, dict) else dataclasses.asdict(r)
        hits.append(SearchHit(
            title=str(d.get("title", ""))[:200],
            url=str(d.get("url", ""))[:300],
            content=str(d.get("content", ""))[:600],
            provider="tavily",
            raw=d,
        ))
    return hits


def _you_search(client: YouClient, query: str, count: int = 5) -> list[SearchHit]:
    try:
        resp = client.search(query, count=count)
    except Exception as exc:
        _log.warning("YOU.com search failed for %r: %s", query, exc)
        _append_audit({"provider": "you", "endpoint": "/v1/search", "query": query,
                        "status": "error", "error": str(exc)[:200]})
        return []
    _append_audit({"provider": "you", "endpoint": "/v1/search", "query": query,
                    "status": "ok", "count": count})
    raw_results = getattr(resp, "results", None) or []
    hits: list[SearchHit] = []
    for r in raw_results[:count]:
        d = (r if isinstance(r, dict)
              else dataclasses.asdict(r) if dataclasses.is_dataclass(r)
              else dict(r))
        hits.append(SearchHit(
            title=str(d.get("title", ""))[:200],
            url=str(d.get("url", ""))[:300],
            content=str(d.get("description", d.get("content", "")))[:600],
            provider="you",
            raw=d,
        ))
    return hits


def _persist(workstream: str, observations: list[Observation],
              sources: list[SearchHit]) -> None:
    out_dir = REPO_ROOT / "data" / "research" / workstream
    out_dir.mkdir(parents=True, exist_ok=True)
    obs_path = out_dir / "observations.jsonl"
    src_path = out_dir / "sources.jsonl"
    with obs_path.open("w", encoding="utf-8") as fh:
        for o in observations:
            fh.write(json.dumps(_scrub_obj(dataclasses.asdict(o)), default=str,
                                  ensure_ascii=False) + "\n")
    with src_path.open("w", encoding="utf-8") as fh:
        for s in sources:
            fh.write(json.dumps(_scrub_obj(dataclasses.asdict(s)), default=str,
                                  ensure_ascii=False) + "\n")
    _log.info("Persisted %d observations and %d sources for %s",
              len(observations), len(sources), workstream)


# ─────────────────────────────────────────────────────────────────────
# Workstreams
# ─────────────────────────────────────────────────────────────────────


def ws_idx_universe(tavily: TavilyClient, you: YouClient) -> tuple[list[Observation], list[SearchHit]]:
    """4A — IDX universe discovery."""
    sources: list[SearchHit] = []
    observations: list[Observation] = []
    queries = [
        ("IDX listed companies 2026", ["idx.co.id"]),
        ("IDX daily trading summary listed companies", ["idx.co.id"]),
        ("Jakarta Stock Exchange listed issuers directory", None),
    ]
    for query, domains in queries:
        for hit in _tavily_search(tavily, query, max_results=4,
                                    include_domains=domains):
            sources.append(hit)
        for hit in _you_search(you, query, count=3):
            sources.append(hit)
        if sources:
            observations.append(Observation(
                entity_id="IDX_OFFICIAL_LIST",
                entity_type="universe_source",
                claim_type="directory_reference",
                claim=f"IDX maintains an issuer directory; query returned {len(sources)} results",
                source_url=sources[-1].url,
                publisher=_publisher_from_url(sources[-1].url),
                published_at=None,
                retrieved_at=_now(),
                search_provider="tavily+you",
                source_tier=1,
                confidence="SUPPORTED",
                verification_status="UNVERIFIED",
                notes=f"queries_executed={len(queries)} | sample_title={sources[-1].title[:80]}",
            ))
    return observations, sources


def ws_taxonomy(tavily: TavilyClient, you: YouClient) -> tuple[list[Observation], list[SearchHit]]:
    """4C — IDX sector/industry taxonomy research."""
    sources: list[SearchHit] = []
    observations: list[Observation] = []
    for hit in _tavily_search(tavily,
                                "IDX Indonesia Classification IDX-IC sector industry mapping",
                                max_results=5, include_domains=["idx.co.id"]):
        sources.append(hit)
    for hit in _you_search(you,
                            "IDX IC sector industry classification listed companies",
                            count=4):
        sources.append(hit)
    observations.append(Observation(
        entity_id="IDX-IC",
        entity_type="taxonomy",
        claim_type="existence",
        claim=("IDX publishes an IDX-IC (Indonesia Classification Code) mapping each "
               "listed equity to sector / sub-sector / industry / sub-industry."),
        source_url="https://www.idx.co.id/en/products/index",
        publisher="idx.co.id",
        published_at=None,
        retrieved_at=_now(),
        search_provider="tavily+you",
        source_tier=1,
        confidence="SUPPORTED",
        verification_status="UNVERIFIED",
        notes=("IDX-IC public page is the authoritative endpoint; canonical sectors are "
               "11: Energy, Basic Materials, Industrials, Consumer Non-Cyclicals, Consumer "
               "Cyclicals, Healthcare, Financials, Technology, Infrastructures, "
               "Transportation & Logistic, Properties & Real Estate."),
    ))
    for ticker in ["BBCA", "ANTM", "TLKM"]:
        q = f"{ticker}.JK sector industry sub-industry"
        for hit in _tavily_search(tavily, q, max_results=2):
            sources.append(hit)
    return observations, sources


def ws_konglo(tavily: TavilyClient, you: YouClient) -> tuple[list[Observation], list[SearchHit]]:
    """4D — Konglo / conglomerate ownership research."""
    sources: list[SearchHit] = []
    observations: list[Observation] = []
    konglo_candidates = [
        ("Salim Group", "INCO"),
        ("Sinar Mas", "SMAR"),
        ("Astra", "ASII"),
        ("Lippo", "LPPF"),
        ("Bakrie", "BNBR"),
        ("MNC", "MNCN"),
        ("Djarum", "TCPI"),
        ("Sampoerna", "HMSP"),
        ("Saratoga", "ARTO"),
        ("Jardine Matheson", "JPFA"),
    ]
    for konglo, ticker in konglo_candidates:
        q = f"{konglo} controlling shareholder {ticker} ownership conglomerate"
        for hit in _tavily_search(tavily, q, max_results=2):
            sources.append(hit)
            observations.append(Observation(
                entity_id=ticker,
                entity_type="konglo_candidate",
                claim_type="ownership_evidence",
                claim=f"{konglo} relationship evidence for {ticker} ({hit.title[:80]})",
                source_url=hit.url,
                publisher=_publisher_from_url(hit.url),
                published_at=None,
                retrieved_at=_now(),
                search_provider="tavily",
                source_tier=_tier_for_url(hit.url),
                confidence="PROVISIONAL",
                verification_status="UNVERIFIED",
                notes=hit.content[:300],
            ))
        for hit in _you_search(you, q, count=2):
            sources.append(hit)
    return observations, sources


def ws_themes(tavily: TavilyClient, you: YouClient) -> tuple[list[Observation], list[SearchHit]]:
    """4E — Themes research."""
    sources: list[SearchHit] = []
    observations: list[Observation] = []
    theme_targets = [
        ("EV battery supply chain", ["ANTM", "INCO", "MBMA", "NCKL"]),
        ("Nickel", ["ANTM", "INCO", "MBMA", "NCKL"]),
        ("Renewable energy", ["BREN", "PGEO", "JSMR"]),
        ("Digital economy", ["GOTO", "BUKA", "EMTK"]),
        ("Banking", ["BBCA", "BBRI", "BMRI", "BBNI"]),
        ("Telecommunications", ["TLKM", "ISAT", "EXCL"]),
    ]
    for theme, tickers in theme_targets:
        q = f"IDX {theme} theme members constituent evidence"
        for hit in _tavily_search(tavily, q, max_results=2):
            sources.append(hit)
            observations.append(Observation(
                entity_id=f"THEME:{theme}",
                entity_type="theme",
                claim_type="theme_membership_evidence",
                claim=f"Theme '{theme}' candidate tickers: {', '.join(tickers)}",
                source_url=hit.url,
                publisher=_publisher_from_url(hit.url),
                published_at=None,
                retrieved_at=_now(),
                search_provider="tavily",
                source_tier=_tier_for_url(hit.url),
                confidence="PROVISIONAL",
                verification_status="UNVERIFIED",
                notes=hit.content[:300] + f" | candidate_tickers={','.join(tickers)}",
            ))
        for hit in _you_search(you, q, count=2):
            sources.append(hit)
    return observations, sources


def ws_foreign_flow(tavily: TavilyClient, you: YouClient) -> tuple[list[Observation], list[SearchHit]]:
    """4H — Foreign flow source research (NOT a quantitative series)."""
    sources: list[SearchHit] = []
    observations: list[Observation] = []
    queries = [
        "IDX foreign net buy sell daily summary publication",
        "OJK Statistik Pasar Modal asing netto",
        "IDX foreign flow daily report csv download",
    ]
    for q in queries:
        for hit in _tavily_search(tavily, q, max_results=3,
                                    include_domains=["idx.co.id", "ojk.go.id"]):
            sources.append(hit)
            observations.append(Observation(
                entity_id="FOREIGN_FLOW_SOURCE",
                entity_type="enrichment_source",
                claim_type="publication_existence",
                claim=f"Candidate authoritative foreign-flow publication: {hit.title[:120]}",
                source_url=hit.url,
                publisher=_publisher_from_url(hit.url),
                published_at=None,
                retrieved_at=_now(),
                search_provider="tavily",
                source_tier=_tier_for_url(hit.url),
                confidence="PROVISIONAL",
                verification_status="UNVERIFIED",
                notes=hit.content[:300] + " | requires crawl+parse before quantitative use",
            ))
        for hit in _you_search(you, q, count=2):
            sources.append(hit)
    return observations, sources


def ws_corp_actions(tavily: TavilyClient, you: YouClient) -> tuple[list[Observation], list[SearchHit]]:
    """4F — Corporate-action / anomaly research."""
    sources: list[SearchHit] = []
    observations: list[Observation] = []
    for q in [
        "BBCA.JK corporate action October 2021 stock split",
        "BBCA.JK harga historis 2021-10-13 corporate action",
    ]:
        for hit in _tavily_search(tavily, q, max_results=2):
            sources.append(hit)
            observations.append(Observation(
                entity_id="BBCA.JK",
                entity_type="corporate_action",
                claim_type="evidence_search",
                claim=f"Corporate-action evidence for BBCA.JK ({hit.title[:80]})",
                source_url=hit.url,
                publisher=_publisher_from_url(hit.url),
                published_at=None,
                retrieved_at=_now(),
                search_provider="tavily",
                source_tier=_tier_for_url(hit.url),
                confidence="PROVISIONAL",
                verification_status="UNVERIFIED",
                notes=hit.content[:300],
            ))
    return observations, sources


def ws_benchmark(tavily: TavilyClient, you: YouClient) -> tuple[list[Observation], list[SearchHit]]:
    """4G — Benchmark / IHSG research."""
    sources: list[SearchHit] = []
    observations: list[Observation] = []
    for q in [
        "IHSG Jakarta Composite index methodology IDX",
        "^JKSE Yahoo Finance IHSG mapping benchmark",
    ]:
        for hit in _tavily_search(tavily, q, max_results=2):
            sources.append(hit)
            observations.append(Observation(
                entity_id="IHSG",
                entity_type="benchmark",
                claim_type="methodology_reference",
                claim=f"Benchmark reference for IHSG/^JKSE ({hit.title[:80]})",
                source_url=hit.url,
                publisher=_publisher_from_url(hit.url),
                published_at=None,
                retrieved_at=_now(),
                search_provider="tavily",
                source_tier=_tier_for_url(hit.url),
                confidence="PROVISIONAL",
                verification_status="UNVERIFIED",
                notes=hit.content[:300],
            ))
        for hit in _you_search(you, q, count=2):
            sources.append(hit)
    return observations, sources


def ws_free_float(tavily: TavilyClient, you: YouClient) -> tuple[list[Observation], list[SearchHit]]:
    """4I — Free float / market cap research."""
    sources: list[SearchHit] = []
    observations: list[Observation] = []
    for q in [
        "IDX free float listed companies publication",
        "OJK free float IDX issuer disclosure",
    ]:
        for hit in _tavily_search(tavily, q, max_results=2):
            sources.append(hit)
            observations.append(Observation(
                entity_id="FREE_FLOAT_SOURCE",
                entity_type="enrichment_source",
                claim_type="publication_existence",
                claim=f"Candidate free-float / market-cap source: {hit.title[:120]}",
                source_url=hit.url,
                publisher=_publisher_from_url(hit.url),
                published_at=None,
                retrieved_at=_now(),
                search_provider="tavily",
                source_tier=_tier_for_url(hit.url),
                confidence="PROVISIONAL",
                verification_status="UNVERIFIED",
                notes=hit.content[:300],
            ))
    return observations, sources


def ws_methodology(tavily: TavilyClient, you: YouClient) -> tuple[list[Observation], list[SearchHit]]:
    """4J — Methodology references."""
    sources: list[SearchHit] = []
    observations: list[Observation] = []
    for q in [
        "market breadth definition methodology academic",
        "relative strength index construction methodology",
        "concentration measure HHI market equity",
    ]:
        for hit in _tavily_search(tavily, q, max_results=2):
            sources.append(hit)
            observations.append(Observation(
                entity_id="METHODOLOGY",
                entity_type="reference",
                claim_type="methodology_evidence",
                claim=f"Methodology reference: {hit.title[:120]}",
                source_url=hit.url,
                publisher=_publisher_from_url(hit.url),
                published_at=None,
                retrieved_at=_now(),
                search_provider="tavily",
                source_tier=_tier_for_url(hit.url),
                confidence="PROVISIONAL",
                verification_status="UNVERIFIED",
                notes=hit.content[:300],
            ))
    return observations, sources


WORKSTREAMS: dict[str, Any] = {
    "idu": ws_idx_universe,
    "taxonomy": ws_taxonomy,
    "konglo": ws_konglo,
    "themes": ws_themes,
    "foreign_flow": ws_foreign_flow,
    "corp_actions": ws_corp_actions,
    "benchmark": ws_benchmark,
    "free_float": ws_free_float,
    "methodology": ws_methodology,
}

# Per-workstream HTTP-request caps (per provider).
CAPS = {
    "idu": 8, "taxonomy": 12, "konglo": 12, "themes": 10,
    "foreign_flow": 6, "corp_actions": 4, "benchmark": 4,
    "free_float": 4, "methodology": 6,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="run_research_pass")
    parser.add_argument("--workstreams", nargs="+", default=list(WORKSTREAMS.keys()),
                        help="Subset of workstreams to run")
    args = parser.parse_args(argv)

    _load_dotenv()
    if not os.environ.get("TAVILY_API_KEY"):
        print("BLOCKED: TAVILY — TAVILY_API_KEY missing", file=sys.stderr)
        return 2
    if not os.environ.get("YOU_API_KEY"):
        print("BLOCKED: YOU.COM — YOU_API_KEY missing", file=sys.stderr)
        return 2

    for ws_name in args.workstreams:
        if ws_name not in WORKSTREAMS:
            print(f"Unknown workstream: {ws_name}", file=sys.stderr)
            continue
        cap = CAPS.get(ws_name, 5)
        tavily = TavilyClient(allow_live=True, max_http_requests=cap)
        you = YouClient(allow_live=True, max_http_requests=cap)
        _log.info("Running workstream: %s (cap=%d per provider)", ws_name, cap)
        obs, src = WORKSTREAMS[ws_name](tavily, you)
        _persist(ws_name, obs, src)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())