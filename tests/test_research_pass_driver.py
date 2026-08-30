"""Tests for scripts/research/run_research_pass.py."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts.research import run_research_pass as rp  # noqa: E402


def test_persist_writes_observations_and_sources(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`_persist` writes JSONL files with the expected shape and no secrets."""
    monkeypatch.setattr(rp, "REPO_ROOT", tmp_path)
    obs = [rp.Observation(
        entity_id="X", entity_type="konglo_candidate", claim_type="ownership_evidence",
        claim="Salim Group controls INCO",
        source_url="https://www.indofood.com/about", publisher="indofood.com",
        published_at=None,
        retrieved_at=rp._now(),
        search_provider="tavily", source_tier=2,
        confidence="PROVISIONAL", verification_status="UNVERIFIED",
        notes="avoid this leak: TAVILY_API_KEY=tvly-XXXDEADBEEF",
    )]
    src = [rp.SearchHit(
        title="Salim Group profile", url="https://www.indofood.com/about",
        content="PT Indofood Sukses Makmur Tbk is part of the Salim Group.",
        provider="tavily", raw={"url": "https://www.indofood.com/about", "title": "Salim Group"},
    )]
    rp._persist("idu", obs, src)
    out = tmp_path / "data" / "research" / "idu"
    obs_lines = (out / "observations.jsonl").read_text().splitlines()
    src_lines = (out / "sources.jsonl").read_text().splitlines()
    assert len(obs_lines) == 1
    assert len(src_lines) == 1
    o = json.loads(obs_lines[0])
    s = json.loads(src_lines[0])
    # Required fields
    for required in ("entity_id", "entity_type", "claim_type", "claim",
                      "source_url", "publisher", "retrieved_at",
                      "search_provider", "source_tier", "confidence",
                      "verification_status"):
        assert required in o
    for required in ("title", "url", "content", "provider"):
        assert required in s
    # No secrets persisted
    raw = obs_lines[0]
    assert "tvly-" not in raw
    assert "TAVILY_API_KEY=" not in raw
    assert "YOU_API_KEY=" not in raw


def test_tier_for_url_idx_official() -> None:
    """Tier-1 for IDX / OJK / KSEI."""
    assert rp._tier_for_url("https://www.idx.co.id/en/products/index") == 1
    assert rp._tier_for_url("https://ojk.go.id/en/berita-dan-kegiatan") == 1
    assert rp._tier_for_url("https://ksei.co.id") == 1


def test_tier_for_url_issuer_website() -> None:
    """Tier-2 for known issuer websites."""
    assert rp._tier_for_url("https://www.indofood.com/about") == 2
    assert rp._tier_for_url("https://www.bca.co.id") == 2


def test_tier_for_url_tier3_publication() -> None:
    """Tier-3 for reputable publications, tier-4 for aggregators."""
    assert rp._tier_for_url("https://www.reuters.com/markets") == 3
    assert rp._tier_for_url("https://kontan.co.id/news") == 3
    assert rp._tier_for_url("https://en.wikipedia.org/wiki/Salim_Group") == 4


def test_tier_for_url_default_five() -> None:
    """Unknown host → tier 5."""
    assert rp._tier_for_url("https://unknown-blog.example.com/post") == 5


def test_publisher_from_url_strips_www_and_host() -> None:
    assert rp._publisher_from_url("https://www.idx.co.id/en/products") == "idx.co.id"
    assert rp._publisher_from_url("http://ojk.go.id") == "ojk.go.id"


def test_workstream_registry_complete() -> None:
    """All 9 expected workstreams registered."""
    expected = {"idu", "taxonomy", "konglo", "themes", "foreign_flow",
                "corp_actions", "benchmark", "free_float", "methodology"}
    assert set(rp.WORKSTREAMS.keys()) == expected
    # Caps exist for every workstream
    for ws in expected:
        assert ws in rp.CAPS, f"missing cap for {ws}"


def test_caps_bounds() -> None:
    """Per-provider HTTP caps must be positive integers and reasonable."""
    for ws, cap in rp.CAPS.items():
        assert isinstance(cap, int)
        assert 1 <= cap <= 50, f"unreasonable cap for {ws}: {cap}"


def test_audit_appends_jsonl(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`_append_audit` writes a valid JSON line to data/research/_audit.jsonl."""
    monkeypatch.setattr(rp, "REPO_ROOT", tmp_path)
    rp._append_audit({"provider": "tavily", "endpoint": "/search", "query": "test",
                       "status": "ok", "max_results": 3})
    rp._append_audit({"provider": "you", "endpoint": "/v1/search", "query": "test",
                       "status": "ok", "count": 2})
    audit_path = tmp_path / "data" / "research" / "_audit.jsonl"
    lines = audit_path.read_text().splitlines()
    assert len(lines) == 2
    for line in lines:
        rec = json.loads(line)
        assert "ts" in rec
        assert "provider" in rec
        assert "status" in rec