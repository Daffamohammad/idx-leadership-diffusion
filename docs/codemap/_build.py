"""Build the IDX Leadership Diffusion codemap.

Generates three files together:
  docs/codemap/codemap.json
  docs/codemap/codemap.html
  docs/codemap/codemap.lock

The codemap is built from a manually-curated 18-node primary list so the
rendered diagram stays focused. Edges and flows are attached to those
nodes with source-path + symbol evidence. Any relationship that could
not be sourced from the repository is marked `evidence: "unknown — …"`
rather than guessed.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO = Path("/Users/daffa/hackathon/idx-leadership-diffusion").resolve()
OUT = REPO / "docs" / "codemap"
OUT.mkdir(parents=True, exist_ok=True)

ALLOWED_EDGE_TYPES = {"imports", "calls", "reads", "writes", "publishes", "subscribes"}

# --------------------------------------------------------------------------- #
# 1. Primary nodes (18). Each node aggregates one or more underlying source
#    files. "path" is the canonical entry point for the node; "files" is the
#    set of files that belong to it and is computed at build time.
# --------------------------------------------------------------------------- #

NODES: list[dict[str, Any]] = [
    {
        "id": "app",
        "path": "app/streamlit_app.py",
        "role": "Read-only Streamlit UI: four tabs (What Changed, Leadership Map, Group Explorer, Method/Quality) + per-endpoint DQ sidebar + story-mode rendering + data-quality helpers.",
        "entrypoints": ["app/streamlit_app.py:main", "app/story_mode.py:build_story_card", "app/data_quality.py:render_endpoint_status"],
        "tests": ["tests/test_ui_story_mode.py", "tests/conftest_app.py"],
        "constraints": ["No business logic — read-only", "No LLM narrative"],
        "evidence": "app/streamlit_app.py:148 main",
    },
    {
        "id": "scripts",
        "path": "scripts/build_market_snapshot.py",
        "role": "CLI entry points: refresh, build, compare, audit, sensitivity studies. Orchestrates the full engine.",
        "entrypoints": [
            "scripts/refresh_sectors_core:main",
            "scripts/build_market_snapshot:main",
            "scripts/compare_providers:main",
            "scripts/audit_close_basis:main",
            "scripts/credit_audit:main",
            "scripts/run_state_turnover:main",
            "scripts/run_stale_trading:main",
            "scripts/run_horizon_sensitivity:main",
            "scripts/run_diffusion_sensitivity:main",
        ],
        "tests": ["tests/test_pipeline.py", "tests/test_snapshots.py"],
        "constraints": ["Deterministic", "Live HTTP gated by --allow-live"],
        "evidence": "scripts/build_market_snapshot.py:1 main",
    },
    {
        "id": "pipeline",
        "path": "src/idx_leadership/pipeline.py",
        "role": "End-to-end orchestrator: provider → features → group snapshots → transitions → snapshot persistence. Source-neutral (does not import vendor SDKs).",
        "entrypoints": ["src/idx_leadership/pipeline.py:build_snapshot"],
        "tests": ["tests/test_pipeline.py", "tests/test_no_lookahead.py"],
        "constraints": ["Source-neutral", "No look-ahead"],
        "evidence": "src/idx_leadership/pipeline.py:35 build_snapshot",
    },
    {
        "id": "providers",
        "path": "src/idx_leadership/providers/base.py",
        "role": "Provider abstraction: MarketDataProvider + 8 capability protocols. Concrete: YFinanceProvider, FixtureProvider, SectorsProvider. Capability-discovery via SectorsProvider.get_* and ledger-aware.",
        "entrypoints": [
            "src/idx_leadership/providers/base.py:MarketDataProvider",
            "src/idx_leadership/providers/capabilities.py:PriceCrossSectionProvider",
            "src/idx_leadership/providers/capabilities.py:SecurityMasterProvider",
            "src/idx_leadership/providers/sectors.py:SectorsProvider",
        ],
        "tests": ["tests/test_providers.py", "tests/test_sectors_provider.py", "tests/test_capability_provider.py"],
        "constraints": ["Analytical layer never imports vendor SDKs", "Live HTTP gated by allow_live=True"],
        "evidence": "src/idx_leadership/providers/base.py:16 MarketDataProvider",
    },
    {
        "id": "sectors-client",
        "path": "src/idx_leadership/providers/sectors_client.py",
        "role": "Thin Sectors v2 HTTP client: auth, timeout, bounded retry, pagination, raw cache, ledger integration.",
        "entrypoints": ["src/idx_leadership/providers/sectors_client.py:SectorsClient.get", "src/idx_leadership/providers/sectors_client.py:SectorsClient.paginate"],
        "tests": ["tests/test_sectors_client.py"],
        "constraints": ["Refuses live calls unless allow_live=True", "Secret redaction in ledger"],
        "evidence": "src/idx_leadership/providers/sectors_client.py:71 SectorsClient",
    },
    {
        "id": "market-universe",
        "path": "src/idx_leadership/providers/market_universe.py",
        "role": "Market-wide candidate universe with explicit eligibility filter (listing board, taxonomy, history, suspensions, staleness).",
        "entrypoints": ["src/idx_leadership/providers/market_universe.py:build_market_universe", "src/idx_leadership/providers/market_universe.py:eligibility_summary"],
        "tests": ["tests/test_market_universe.py"],
        "constraints": ["Pure (no network)"],
        "evidence": "src/idx_leadership/providers/market_universe.py:42 build_market_universe",
    },
    {
        "id": "models",
        "path": "src/idx_leadership/models/__init__.py",
        "role": "Pydantic canonical schemas: security master, price obs, benchmark obs, group snapshot, transition event, evidence, manifest, etc.",
        "entrypoints": [
            "src/idx_leadership/models/__init__.py:SecurityMasterEntry",
            "src/idx_leadership/models/__init__.py:PriceObservation",
            "src/idx_leadership/models/__init__.py:BenchmarkObservation",
            "src/idx_leadership/models/__init__.py:GroupSnapshot",
            "src/idx_leadership/models/__init__.py:TransitionEvent",
            "src/idx_leadership/models/__init__.py:GroupEvidence",
            "src/idx_leadership/models/__init__.py:SnapshotManifest",
            "src/idx_leadership/models/__init__.py:DataQualityStatus",
        ],
        "tests": ["tests/test_schema.py", "tests/test_methodology_versioning.py"],
        "constraints": ["extra=forbid on most models", "Back-compat via extra=ignore on GroupSnapshot"],
        "evidence": "src/idx_leadership/models/__init__.py:7 from .enums import",
    },
    {
        "id": "features",
        "path": "src/idx_leadership/features/relative_strength.py",
        "role": "Per-security feature engine: returns (5/20/60D), benchmark-aligned excess returns, group breadth, group concentration v2 (top1_abs_share ≤ 1.0).",
        "entrypoints": [
            "src/idx_leadership/features/returns.py:compute_returns",
            "src/idx_leadership/features/relative_strength.py:compute_excess_returns",
            "src/idx_leadership/features/breadth.py:compute_breadth",
            "src/idx_leadership/features/concentration_v2.py:compute_concentration_v2",
        ],
        "tests": ["tests/test_returns.py", "tests/test_relative_strength.py", "tests/test_breadth.py", "tests/test_concentration_v2.py", "tests/test_concentration.py"],
        "constraints": ["No future fill", "Invalid prices rejected", "top1_abs_share ≤ 1.0 always"],
        "evidence": "src/idx_leadership/features/relative_strength.py:95 compute_excess_returns",
    },
    {
        "id": "aggregation",
        "path": "src/idx_leadership/aggregation/groups.py",
        "role": "Group-level aggregation: build GroupSnapshot from per-security features; rank_groups assigns leadership_rank and change_rank.",
        "entrypoints": ["src/idx_leadership/aggregation/groups.py:build_group_snapshots", "src/idx_leadership/aggregation/groups.py:rank_groups", "src/idx_leadership/aggregation/groups.py:aggregate_history"],
        "tests": ["tests/test_aggregation.py"],
        "constraints": ["Uses DiffusionStateV2 (group-size-aware)"],
        "evidence": "src/idx_leadership/aggregation/groups.py:31 build_group_snapshots",
    },
    {
        "id": "signals-leadership",
        "path": "src/idx_leadership/signals/leadership.py",
        "role": "2D leadership classifier: 4 states (LEADING/IMPROVING/LAGGING/WEAKENING) + UNCONFIRMED based on (excess_20d, acceleration).",
        "entrypoints": ["src/idx_leadership/signals/leadership.py:classify_leadership"],
        "tests": ["tests/test_states.py"],
        "constraints": ["Threshold in config/methodology.yaml"],
        "evidence": "src/idx_leadership/signals/leadership.py:24 classify_leadership",
    },
    {
        "id": "signals-diffusion",
        "path": "src/idx_leadership/signals/diffusion_v2.py",
        "role": "Group-size-aware diffusion: BROADENING_FIRM / BROADENING_FRAGILE / STABLE / NARROWING_FRAGILE / NARROWING_FIRM / UNCONFIRMED. Backward-compat v1 enum via to_v1_state.",
        "entrypoints": ["src/idx_leadership/signals/diffusion_v2.py:classify_diffusion_v2", "src/idx_leadership/signals/diffusion_v2.py:constituent_floor", "src/idx_leadership/signals/diffusion_v2.py:to_v1_state"],
        "tests": ["tests/test_diffusion_group_size.py", "tests/test_states.py"],
        "constraints": ["backward compat: to_v1_state maps v2 → v1 enum"],
        "evidence": "src/idx_leadership/signals/diffusion_v2.py:46 classify_diffusion_v2",
    },
    {
        "id": "signals-transitions",
        "path": "src/idx_leadership/signals/transitions.py",
        "role": "TransitionEvent builder; explicit categorical diff + priority-ordered materiality classifier; change-digest bucketing (7 categories: new_leaders, lost_leadership, upgrades, downgrades, broadening, narrowing, stable).",
        "entrypoints": [
            "src/idx_leadership/signals/transitions.py:compute_transition",
            "src/idx_leadership/signals/transitions.py:build_transition_events",
            "src/idx_leadership/signals/change_digest.py:build_change_digest",
        ],
        "tests": ["tests/test_transitions.py", "tests/test_transitions.py::test_change_digest_buckets_unique"],
        "constraints": ["Materiality priority is hand-tuned and documented", "Each group appears in at most one bucket"],
        "evidence": "src/idx_leadership/signals/transitions.py:31 compute_transition",
    },
    {
        "id": "analytics",
        "path": "src/idx_leadership/analytics/persistence.py",
        "role": "Deterministic analytics: persistence (consecutive-snapshot counter), contradictions (7 heuristics), screen invalidation (4 conditions).",
        "entrypoints": [
            "src/idx_leadership/analytics/persistence.py:compute_persistence",
            "src/idx_leadership/analytics/contradictions.py:build_contradictions",
            "src/idx_leadership/analytics/invalidation.py:build_invalidation_conditions",
        ],
        "tests": ["tests/test_analytics.py"],
        "constraints": ["No LLM", "Descriptive, not prescriptive"],
        "evidence": "src/idx_leadership/analytics/persistence.py:39 compute_persistence",
    },
    {
        "id": "evidence-builder",
        "path": "src/idx_leadership/evidence/builder.py",
        "role": "GroupEvidence builder: structured per-group evidence + contradictions + data_gaps. Source-neutral (no provider imports).",
        "entrypoints": ["src/idx_leadership/evidence/builder.py:build_group_evidence", "src/idx_leadership/evidence/builder.py:build_evidence_table"],
        "tests": ["tests/test_evidence.py"],
        "constraints": ["Source-neutral (no provider imports)"],
        "evidence": "src/idx_leadership/evidence/builder.py:21 build_group_evidence",
    },
    {
        "id": "data-snapshots",
        "path": "src/idx_leadership/data/snapshots.py",
        "role": "Snapshot writer/reader (atomic per-file writes, manifest aggregation) + Data quality (duplicate / invalid / staleness detection, overall DataQualityStatus rollup) + per-endpoint quality (READY / READY_WITH_GAPS / PARTIAL / STALE / FAILED / UNKNOWN).",
        "entrypoints": [
            "src/idx_leadership/data/snapshots.py:SnapshotWriter.write",
            "src/idx_leadership/data/snapshots.py:SnapshotReader.load",
            "src/idx_leadership/data/snapshots.py:SnapshotReader.aggregate_manifest",
            "src/idx_leadership/data/quality.py:assess_quality",
            "src/idx_leadership/data/endpoint_status.py:assess_endpoint_quality",
            "src/idx_leadership/data/endpoint_status.py:rollup_status",
        ],
        "tests": ["tests/test_snapshots.py", "tests/test_pipeline.py", "tests/test_endpoint_status.py"],
        "constraints": ["tmp + rename for atomicity", "Severe issues are reported, not silently fixed", "UNKNOWN-only rollup → FAILED"],
        "evidence": "src/idx_leadership/data/snapshots.py:30 SnapshotWriter",
    },
    {
        "id": "ledger",
        "path": "src/idx_leadership/providers/ledger.py",
        "role": "Request ledger: per-call record (endpoint, params hash, cache hit, status, rows, elapsed, estimated_credit_cost, actual_credit_cost). Used by SectorsClient and CLI scripts.",
        "entrypoints": ["src/idx_leadership/providers/ledger.py:RequestLedger.record", "src/idx_leadership/providers/ledger.py:RequestLedger.flush"],
        "tests": ["tests/test_providers.py::test_ledger_records_call", "tests/test_providers.py::test_ledger_redacts_secrets"],
        "constraints": ["Redacts api_key/token/secret/password/authorization"],
        "evidence": "src/idx_leadership/providers/ledger.py:25 RequestLedger",
    },
    {
        "id": "tests",
        "path": "tests/conftest.py",
        "role": "Pytest fixtures (prices_df, benchmark_df, taxonomy_df, fixtures_dir, fixture_provider) + the entire offline test suite (202 tests).",
        "entrypoints": ["tests/conftest.py:fixtures_dir"],
        "tests": ["tests/test_*.py"],
        "constraints": ["Offline-only; no network"],
        "evidence": "tests/conftest.py:9 fixtures_dir",
    },
    {
        "id": "config",
        "path": "config/methodology.yaml",
        "role": "Methodology parameters: horizons, breadth thresholds, leadership acceleration, min group size, materiality. method_version=methodology-v2. All thresholds live here — no magic numbers in code.",
        "entrypoints": ["config/methodology.yaml:method_version", "config/universe.yaml", "config/providers.yaml"],
        "tests": ["tests/test_methodology_versioning.py", "tests/test_config.py"],
        "constraints": ["No magic numbers in code; all thresholds in config"],
        "evidence": "config/methodology.yaml:8 method_version",
    },
    {
        "id": "docs",
        "path": "docs/METHODOLOGY.md",
        "role": "Methodology + architecture + audit + decision + gaps documentation (single source of truth for prose).",
        "entrypoints": ["docs/METHODOLOGY.md", "docs/ARCHITECTURE.md", "docs/DECISION_LOG.md", "docs/KNOWN_GAPS.md", "FRONTIER_PASS_2_AUDIT.md"],
        "tests": [],
        "constraints": ["Single source of truth for methodology prose"],
        "evidence": "docs/METHODOLOGY.md:1 # IDX Leadership Diffusion",
    },
]

# File → node mapping. A trailing `/` matches recursively.
FILE_TO_NODE: list[tuple[set[str], str]] = [
    ({"app/streamlit_app.py", "app/components.py", "app/story_mode.py", "app/data_quality.py"}, "app"),
    ({"scripts/"}, "scripts"),
    ({"src/idx_leadership/pipeline.py"}, "pipeline"),
    ({"src/idx_leadership/providers/__init__.py",
      "src/idx_leadership/providers/base.py",
      "src/idx_leadership/providers/capabilities.py",
      "src/idx_leadership/providers/factory.py",
      "src/idx_leadership/providers/fixture.py",
      "src/idx_leadership/providers/public.py",
      "src/idx_leadership/providers/sectors.py",
      "src/idx_leadership/providers/sectors_normalizers.py"},
     "providers"),
    ({"src/idx_leadership/providers/sectors_client.py"}, "sectors-client"),
    ({"src/idx_leadership/providers/market_universe.py"}, "market-universe"),
    ({"src/idx_leadership/providers/ledger.py"}, "ledger"),
    ({"src/idx_leadership/models/"}, "models"),
    ({"src/idx_leadership/features/"}, "features"),
    ({"src/idx_leadership/aggregation/groups.py"}, "aggregation"),
    ({"src/idx_leadership/signals/leadership.py"}, "signals-leadership"),
    ({"src/idx_leadership/signals/diffusion_v2.py",
      "src/idx_leadership/signals/diffusion.py"},
     "signals-diffusion"),
    ({"src/idx_leadership/signals/transitions.py",
      "src/idx_leadership/signals/change_digest.py"},
     "signals-transitions"),
    ({"src/idx_leadership/analytics/"}, "analytics"),
    ({"src/idx_leadership/evidence/builder.py"}, "evidence-builder"),
    ({"src/idx_leadership/data/snapshots.py",
      "src/idx_leadership/data/manifests.py",
      "src/idx_leadership/data/quality.py",
      "src/idx_leadership/data/endpoint_status.py",
      "src/idx_leadership/data/__init__.py"},
     "data-snapshots"),
    ({"tests/"}, "tests"),
    ({"config/"}, "config"),
    ({"docs/", "FRONTIER_PASS_1_AUDIT.md", "FRONTIER_PASS_2_AUDIT.md", "GROUNDWORK_AUDIT.md", "README.md"}, "docs"),
]


def build_file_to_node() -> dict[str, str]:
    ftn: dict[str, str] = {}
    for paths, node_id in FILE_TO_NODE:
        for p in paths:
            if p.endswith("/"):
                for ext in ("*.py", "*.yaml", "*.yml", "*.md"):
                    for f in (REPO / p).rglob(ext):
                        ftn[str(f.relative_to(REPO))] = node_id
            else:
                ftn[p] = node_id
    return ftn


# --------------------------------------------------------------------------- #
# 2. Edges between primary nodes. Each edge carries source-path + symbol
#    evidence. The only allowed types are: imports, calls, reads, writes,
#    publishes, subscribes. No "unknown" type — relationships that cannot
#    be sourced are surfaced as `evidence: "unknown — …"` with type=reads.
# --------------------------------------------------------------------------- #

EDGES: list[dict[str, str]] = [
    # app
    {"from": "app", "to": "data-snapshots", "type": "imports",
     "evidence": "app/streamlit_app.py:27 from idx_leadership.data.snapshots import SnapshotReader"},
    {"from": "app", "to": "models", "type": "imports",
     "evidence": "app/streamlit_app.py:118 from idx_leadership.models import …"},
    {"from": "app", "to": "evidence-builder", "type": "imports",
     "evidence": "app/streamlit_app.py:122 from idx_leadership.evidence.builder import build_evidence_table"},
    {"from": "app", "to": "config", "type": "imports",
     "evidence": "app/streamlit_app.py:29 from idx_leadership.utils.config import load_yaml"},

    # scripts
    {"from": "scripts", "to": "pipeline", "type": "calls",
     "evidence": "scripts/build_market_snapshot.py:23 from idx_leadership.aggregation.groups import build_group_snapshots, rank_groups"},
    {"from": "scripts", "to": "providers", "type": "calls",
     "evidence": "scripts/build_market_snapshot.py:253 provider.ledger.flush()"},
    {"from": "scripts", "to": "market-universe", "type": "calls",
     "evidence": "scripts/build_market_snapshot.py:30 from idx_leadership.providers.market_universe import EligibilityConfig, build_market_universe"},
    {"from": "scripts", "to": "features", "type": "calls",
     "evidence": "scripts/build_market_snapshot.py:28 from idx_leadership.features.relative_strength import compute_excess_returns"},
    {"from": "scripts", "to": "aggregation", "type": "calls",
     "evidence": "scripts/build_market_snapshot.py:23 from idx_leadership.aggregation.groups import build_group_snapshots, rank_groups"},
    {"from": "scripts", "to": "signals-transitions", "type": "calls",
     "evidence": "scripts/build_market_snapshot.py:32 from idx_leadership.signals.transitions import build_transition_events"},
    {"from": "scripts", "to": "evidence-builder", "type": "calls",
     "evidence": "scripts/build_market_snapshot.py:27 from idx_leadership.evidence.builder import build_evidence_table"},
    {"from": "scripts", "to": "data-snapshots", "type": "calls",
     "evidence": "scripts/build_market_snapshot.py:26 from idx_leadership.data.snapshots import SnapshotReader, SnapshotWriter"},
    {"from": "scripts", "to": "ledger", "type": "calls",
     "evidence": "scripts/refresh_sectors_core.py:29 from idx_leadership.providers.ledger import RequestLedger"},
    {"from": "scripts", "to": "config", "type": "reads",
     "evidence": "scripts/build_market_snapshot.py:50 from idx_leadership.utils.config import data_root, load_yaml"},

    # pipeline
    {"from": "pipeline", "to": "providers", "type": "calls",
     "evidence": "src/idx_leadership/pipeline.py:67 provider.get_price_history(...)"},
    {"from": "pipeline", "to": "features", "type": "calls",
     "evidence": "src/idx_leadership/pipeline.py:115 compute_excess_returns(...)"},
    {"from": "pipeline", "to": "aggregation", "type": "calls",
     "evidence": "src/idx_leadership/pipeline.py:125 build_group_snapshots(...)"},
    {"from": "pipeline", "to": "signals-transitions", "type": "calls",
     "evidence": "src/idx_leadership/pipeline.py:148 build_transition_events(...)"},
    {"from": "pipeline", "to": "data-snapshots", "type": "calls",
     "evidence": "src/idx_leadership/pipeline.py:160 SnapshotWriter(...).write(...)"},
    {"from": "pipeline", "to": "models", "type": "imports",
     "evidence": "src/idx_leadership/pipeline.py:16 from .models import …"},

    # providers
    {"from": "providers", "to": "sectors-client", "type": "calls",
     "evidence": "src/idx_leadership/providers/sectors.py:105 rows = self.client.paginate(...)"},
    {"from": "providers", "to": "ledger", "type": "calls",
     "evidence": "src/idx_leadership/providers/sectors.py:95 self.ledger = ledger or RequestLedger()"},
    {"from": "providers", "to": "market-universe", "type": "imports",
     "evidence": "src/idx_leadership/providers/market_universe.py:18 from .capabilities import EventProvider, PriceCrossSectionProvider, SecurityMasterProvider"},
    {"from": "providers", "to": "models", "type": "imports",
     "evidence": "src/idx_leadership/providers/sectors.py:50 from ..models import SecurityMasterEntry"},

    # sectors-client
    {"from": "sectors-client", "to": "ledger", "type": "calls",
     "evidence": "src/idx_leadership/providers/sectors_client.py:191 self.ledger.record(...)"},

    # market-universe
    {"from": "market-universe", "to": "models", "type": "imports",
     "evidence": "src/idx_leadership/providers/market_universe.py:17 from ..models import SecurityMasterEntry"},

    # features
    {"from": "features", "to": "models", "type": "imports",
     "evidence": "src/idx_leadership/features/returns.py:7 from ..utils import get_logger"},

    # aggregation
    {"from": "aggregation", "to": "features", "type": "calls",
     "evidence": "src/idx_leadership/aggregation/groups.py:15 from ..features.breadth import compute_breadth"},
    {"from": "aggregation", "to": "signals-leadership", "type": "calls",
     "evidence": "src/idx_leadership/aggregation/groups.py:25 from ..signals.leadership import classify_leadership"},
    {"from": "aggregation", "to": "signals-diffusion", "type": "calls",
     "evidence": "src/idx_leadership/aggregation/groups.py:26 from ..signals.diffusion_v2 import …"},
    {"from": "aggregation", "to": "models", "type": "imports",
     "evidence": "src/idx_leadership/aggregation/groups.py:18 from ..models import ConcentrationMetrics, DiffusionState, EligibilityStatus, GroupSnapshot, LeadershipState"},

    # signals
    {"from": "signals-transitions", "to": "signals-leadership", "type": "imports",
     "evidence": "src/idx_leadership/signals/transitions.py:14 from ..models import DiffusionState, GroupSnapshot, LeadershipState, MaterialityLabel, TransitionEvent"},
    {"from": "signals-transitions", "to": "signals-diffusion", "type": "imports",
     "evidence": "src/idx_leadership/signals/transitions.py:14 from ..models import DiffusionState, GroupSnapshot, LeadershipState, MaterialityLabel, TransitionEvent"},
    {"from": "signals-transitions", "to": "models", "type": "imports",
     "evidence": "src/idx_leadership/signals/transitions.py:14 from ..models import DiffusionState, GroupSnapshot, LeadershipState, MaterialityLabel, TransitionEvent"},
    {"from": "signals-leadership", "to": "models", "type": "imports",
     "evidence": "src/idx_leadership/signals/leadership.py:13 from ..models import LeadershipState, MaterialityLabel"},
    {"from": "signals-diffusion", "to": "models", "type": "imports",
     "evidence": "src/idx_leadership/signals/diffusion_v2.py:14 from ..models import DiffusionState, EligibilityStatus"},

    # analytics
    {"from": "analytics", "to": "models", "type": "imports",
     "evidence": "src/idx_leadership/analytics/persistence.py:23 from ..models import DiffusionState, GroupSnapshot, LeadershipState"},

    # evidence-builder
    {"from": "evidence-builder", "to": "models", "type": "imports",
     "evidence": "src/idx_leadership/evidence/builder.py:14 from ..models import DiffusionState, EvidenceRecord, GroupEvidence, GroupSnapshot, LeadershipState"},
    {"from": "evidence-builder", "to": "analytics", "type": "calls",
     "evidence": "app/story_mode.py:18 from idx_leadership.analytics import build_contradictions, build_invalidation_conditions, compute_persistence"},

    # data-snapshots
    {"from": "data-snapshots", "to": "models", "type": "imports",
     "evidence": "src/idx_leadership/data/snapshots.py:14 from ..models import GroupSnapshot, ManifestEntry, ProviderName, SnapshotManifest"},

    # tests
    {"from": "tests", "to": "providers", "type": "imports",
     "evidence": "tests/test_providers.py:13 from idx_leadership.providers.fixture import FixtureProvider"},
    {"from": "tests", "to": "sectors-client", "type": "imports",
     "evidence": "tests/test_sectors_client.py:10 from idx_leadership.providers.sectors_client import SectorsClient"},
    {"from": "tests", "to": "analytics", "type": "imports",
     "evidence": "tests/test_analytics.py:9 from idx_leadership.analytics import compute_persistence"},
    {"from": "tests", "to": "data-snapshots", "type": "imports",
     "evidence": "tests/test_endpoint_status.py:8 from idx_leadership.data.endpoint_status import assess_endpoint_quality"},
    {"from": "tests", "to": "app", "type": "imports",
     "evidence": "tests/test_ui_story_mode.py:14 from app.story_mode import build_story_card"},
]


# --------------------------------------------------------------------------- #
# 3. The 5 most important end-to-end flows.
# --------------------------------------------------------------------------- #

FLOWS: list[dict[str, Any]] = [
    {
        "id": "flow-build-snapshot",
        "trigger": "Operator runs `python -m scripts.build_market_snapshot --as-of 2026-08-20 --allow-live`",
        "steps": [
            "scripts", "providers", "sectors-client", "ledger",
            "market-universe", "features", "aggregation",
            "signals-leadership", "signals-diffusion", "signals-transitions",
            "evidence-builder", "data-snapshots", "models",
        ],
        "outcome": "data/snapshots/sectors/sectors_<asof>/{manifest,change_digest,quality,evidence,groups.parquet,transitions.parquet,prices.csv,benchmark.csv,security_master.json,report.md}",
    },
    {
        "id": "flow-refresh-sectors",
        "trigger": "Operator runs `python -m scripts.refresh_sectors_core --as-of 2026-08-20 --allow-live`",
        "steps": ["scripts", "providers", "sectors-client", "ledger", "data-snapshots", "models"],
        "outcome": "data/normalized/sectors/<asof>/{security_master.json,taxonomy.csv,close.csv,ihsg.csv,free_float.csv,suspensions.csv,refresh_summary.json}",
    },
    {
        "id": "flow-story-render",
        "trigger": "Streamlit rerun or user opens What Changed tab",
        "steps": ["app", "data-snapshots", "evidence-builder", "analytics", "models"],
        "outcome": "Up to 5 StoryCards rendered + Markdown export of selected cards",
    },
    {
        "id": "flow-parity-harness",
        "trigger": "Operator runs `python -m scripts.compare_providers --as-of 2026-08-20`",
        "steps": ["scripts", "providers", "features", "models"],
        "outcome": "data/normalized/parity_<asof>.csv with per-ticker/per-horizon classification",
    },
    {
        "id": "flow-credit-audit",
        "trigger": "Operator runs `python -m scripts.credit_audit`",
        "steps": ["scripts", "ledger", "data-snapshots"],
        "outcome": "data/normalized/credit_audit.json with by_endpoint and by_refresh_kind buckets",
    },
]


# --------------------------------------------------------------------------- #
# 4. Helpers — git, fingerprint, file mapping.
# --------------------------------------------------------------------------- #

def get_commit() -> str:
    try:
        out = subprocess.check_output(
            ["git", "-C", str(REPO), "rev-parse", "HEAD"], text=True
        ).strip()
        if out:
            return out
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    return "unknown"


def has_uncommitted_changes() -> bool:
    try:
        out = subprocess.check_output(
            ["git", "-C", str(REPO), "status", "--porcelain"], text=True
        ).strip()
        return bool(out)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def file_fingerprint(rel_path: str) -> str:
    full = REPO / rel_path
    if not full.exists():
        return "missing"
    h = hashlib.sha256()
    h.update(rel_path.encode("utf-8"))
    try:
        with full.open("rb") as f:
            while True:
                chunk = f.read(65536)
                if not chunk:
                    break
                h.update(chunk)
    except OSError:
        return "unreadable"
    return h.hexdigest()


def module_fingerprint(node_id: str, files: list[str]) -> str:
    h = hashlib.sha256()
    for p in sorted(files):
        h.update(p.encode("utf-8"))
        h.update(b":")
        h.update(file_fingerprint(p).encode("utf-8"))
        h.update(b"\n")
    return h.hexdigest()


def gather_module_files() -> dict[str, list[str]]:
    ftn = build_file_to_node()
    out: dict[str, list[str]] = {n["id"]: [] for n in NODES}
    for rel, node in ftn.items():
        if node in out:
            out[node].append(rel)
    return out


# --------------------------------------------------------------------------- #
# 5. Build the JSON map.
# --------------------------------------------------------------------------- #

def build_json_map() -> dict[str, Any]:
    module_files = gather_module_files()
    node_payloads: list[dict[str, Any]] = []
    for n in NODES:
        node_payloads.append({
            "id": n["id"],
            "path": n["path"],
            "role": n["role"],
            "entrypoints": n["entrypoints"],
            "tests": n["tests"],
            "constraints": n["constraints"],
            "evidence": n["evidence"],
            "files": sorted(module_files.get(n["id"], [])),
        })

    node_ids = {n["id"] for n in node_payloads}

    for e in EDGES:
        if e["from"] not in node_ids:
            raise RuntimeError(f"edge from unknown node: {e['from']}")
        if e["to"] not in node_ids:
            raise RuntimeError(f"edge to unknown node: {e['to']}")
        if e["type"] not in ALLOWED_EDGE_TYPES:
            raise RuntimeError(f"invalid edge type: {e['type']!r} for {e['from']}->{e['to']}")

    flow_payloads: list[dict[str, Any]] = []
    for f in FLOWS:
        for s in f["steps"]:
            if s not in node_ids:
                raise RuntimeError(f"flow {f['id']} references unknown node {s}")
        flow_payloads.append({
            "id": f["id"],
            "trigger": f["trigger"],
            "steps": f["steps"],
            "outcome": f["outcome"],
        })

    return {
        "generated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "generated_from_commit": get_commit(),
        "scope": sorted({p for fs in module_files.values() for p in fs}),
        "nodes": node_payloads,
        "edges": EDGES,
        "flows": flow_payloads,
    }


def build_lock(data: dict[str, Any]) -> dict[str, Any]:
    module_files = gather_module_files()
    fingerprints: dict[str, Any] = {}
    for n in NODES:
        files = module_files.get(n["id"], [])
        fingerprints[n["id"]] = {
            "files": files,
            "fingerprint": module_fingerprint(n["id"], files),
        }
    return {
        "schema": "codemap.lock.v1",
        "fingerprint_algorithm": "sha256(file_path + sha256(file_contents)) per module; module fingerprint = sha256 over the (path, file_hash) lines",
        "generated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "commit": get_commit(),
        "working_tree_dirty": has_uncommitted_changes(),
        "scanned_scope": sorted({p for fs in module_files.values() for p in fs}),
        "excluded_directories": [
            ".venv", "__pycache__", ".pytest_cache", ".git",
            "node_modules", "dist", "build",
            ".mypy_cache", ".ruff_cache",
            "data/cache", "data/raw", "data/normalized",
            "data/snapshots", "data/snapshots_baseline", "data/sample",
        ],
        "modules": fingerprints,
    }


# --------------------------------------------------------------------------- #
# 6. Validation.
# --------------------------------------------------------------------------- #

def evidence_symbol_in_text(evidence: str) -> tuple[bool, str]:
    """Return (ok, reason) for an evidence string. Format:
    `<relpath>:<line> <symbol hint...>` or `unknown — …`.
    """
    if evidence.startswith("unknown"):
        return True, "explicitly unknown"
    if " " not in evidence:
        return False, "no symbol after path:line"
    head, _tail = evidence.split(" ", 1)
    if ":" not in head:
        return False, "no line number in path:line"
    path_part, _ = head.split(":", 1)
    p = REPO / path_part
    if not p.exists():
        return False, f"path missing: {path_part}"
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False, f"unreadable: {path_part}"
    # Heuristic: take any token longer than 4 chars from the tail and
    # require at least one of them to be present in the source.
    tokens = [t for t in _tail.replace("(", " ").replace(")", " ").split() if t]
    hints = [t for t in tokens if len(t) >= 4 and any(c.isalnum() for c in t)]
    if not hints:
        return True, "no symbol hint to verify (pure import statement)"
    for hint in hints:
        if hint in text:
            return True, f"matched {hint!r}"
    return False, f"no symbol hint from {hints!r} found in {path_part}"


def validate(data: dict[str, Any], lock: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    node_ids = {n["id"] for n in data["nodes"]}

    # 1. every node path exists
    for n in data["nodes"]:
        if not (REPO / n["path"]).exists():
            issues.append(f"node path missing: {n['id']} -> {n['path']}")

    # 2. every node evidence is locatable
    for n in data["nodes"]:
        ok, why = evidence_symbol_in_text(n["evidence"])
        if not ok:
            issues.append(f"node evidence not locatable: {n['id']} -> {n['evidence']} ({why})")

    # 3. edges reference existing nodes
    for e in data["edges"]:
        if e["from"] not in node_ids:
            issues.append(f"edge from unknown node: {e['from']}")
        if e["to"] not in node_ids:
            issues.append(f"edge to unknown node: {e['to']}")
        ok, why = evidence_symbol_in_text(e["evidence"])
        if not ok:
            issues.append(f"edge evidence not locatable: {e['from']}->{e['to']} -> {e['evidence']} ({why})")

    # 4. flow steps reference existing nodes
    for f in data["flows"]:
        for s in f["steps"]:
            if s not in node_ids:
                issues.append(f"flow {f['id']} references unknown node {s}")

    # 5. the files in each module exist
    for n in data["nodes"]:
        for f in n.get("files", []):
            if not (REPO / f).exists():
                issues.append(f"node {n['id']} lists missing file: {f}")

    return issues


# --------------------------------------------------------------------------- #
# 7. HTML generation — self-contained, dark theme, interactive.
# --------------------------------------------------------------------------- #

def build_html(data: dict[str, Any], lock: dict[str, Any]) -> str:
    nodes_json = json.dumps(data["nodes"])
    edges_json = json.dumps(data["edges"])
    flows_json = json.dumps(data["flows"])
    commit = data["generated_from_commit"]
    generated = data["generated_at"]

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>IDX Leadership Diffusion — codemap</title>
<style>
  :root {{
    --bg: #0b0f14;
    --bg-elev: #131922;
    --bg-elev-2: #1c2330;
    --fg: #e8ecf1;
    --fg-muted: #8a94a3;
    --border: #2a3340;
    --accent: #66d9ef;
    --accent-2: #a6e22e;
    --warn: #ff6b6b;
    --pending: #ffd866;
    --neutral: #6272a4;
  }}
  html, body {{ height: 100%; margin: 0; }}
  body {{
    background: var(--bg);
    color: var(--fg);
    font: 13px/1.4 -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
    overflow: hidden;
  }}
  header {{
    height: 56px;
    background: var(--bg-elev);
    border-bottom: 1px solid var(--border);
    display: flex;
    align-items: center;
    padding: 0 16px;
    gap: 16px;
  }}
  header h1 {{ font-size: 14px; margin: 0; font-weight: 600; }}
  header .meta {{ color: var(--fg-muted); font-size: 11px; }}
  header .meta b {{ color: var(--accent); }}
  header .right {{ margin-left: auto; color: var(--fg-muted); font-size: 11px; }}
  .layout {{ display: grid; grid-template-columns: 280px 1fr 320px; height: calc(100vh - 56px); }}
  aside, main, section {{ overflow: auto; }}
  aside {{ background: var(--bg-elev); border-right: 1px solid var(--border); padding: 12px; }}
  section {{ background: var(--bg-elev); border-left: 1px solid var(--border); padding: 12px; }}
  h2 {{ font-size: 12px; text-transform: uppercase; color: var(--fg-muted); letter-spacing: 0.06em; margin: 0 0 8px; }}
  .search {{ width: 100%; padding: 6px 8px; background: var(--bg-elev-2); color: var(--fg); border: 1px solid var(--border); border-radius: 4px; box-sizing: border-box; }}
  .legend dt {{ font-weight: 600; margin-top: 6px; }}
  .legend dd {{ margin: 0 0 0 14px; color: var(--fg-muted); font-size: 11px; }}
  .flow-list, .node-list {{ list-style: none; margin: 0; padding: 0; }}
  .flow-list li, .node-list li {{
    padding: 6px 8px;
    border-radius: 4px;
    cursor: pointer;
    user-select: none;
  }}
  .flow-list li:hover, .node-list li:hover {{ background: var(--bg-elev-2); }}
  .flow-list li.active, .node-list li.active {{ background: var(--bg-elev-2); outline: 1px solid var(--accent); }}
  .pill {{ display: inline-block; padding: 1px 6px; border-radius: 999px; font-size: 10px; background: var(--bg-elev-2); color: var(--fg-muted); }}
  main {{ position: relative; }}
  svg {{ display: block; }}
  .node rect {{ fill: var(--bg-elev-2); stroke: var(--border); stroke-width: 1; cursor: pointer; }}
  .node text {{ fill: var(--fg); pointer-events: none; font-weight: 600; }}
  .node .sub {{ fill: var(--fg-muted); font-size: 10px; font-weight: 400; }}
  .node.type-module  rect {{ stroke: var(--accent);  fill: #0e1722; }}
  .node.type-script  rect {{ stroke: var(--accent-2); fill: #131c12; }}
  .node.type-service rect {{ stroke: var(--neutral);  fill: #14182a; }}
  .node.type-data    rect {{ stroke: var(--pending);  fill: #1f1c0e; }}
  .node.type-external rect {{ stroke: var(--warn);   fill: #1f1212; }}
  .node.type-docs    rect {{ stroke: var(--accent);  fill: #0e1722; opacity: 0.85; }}
  .node.type-test    rect {{ stroke: var(--pending); fill: #1f1c0e; opacity: 0.85; }}
  .edge {{ stroke: var(--border); stroke-width: 1; fill: none; }}
  .edge.t-imports  {{ stroke: var(--accent);  stroke-dasharray: 4 4; }}
  .edge.t-calls    {{ stroke: var(--accent-2); }}
  .edge.t-reads    {{ stroke: var(--pending);  stroke-dasharray: 2 4; }}
  .edge.t-writes   {{ stroke: var(--warn); }}
  .edge.t-pubsub   {{ stroke: var(--neutral);  stroke-dasharray: 6 2 1 2; }}
  .edge.active     {{ stroke: var(--fg) !important; stroke-width: 2.5 !important; }}
  .edge.dim        {{ opacity: 0.15; }}
  .node.dim rect   {{ opacity: 0.35; }}
  .node.active rect {{ stroke: var(--fg); stroke-width: 2.2; }}
  .node.faint rect  {{ opacity: 0.45; }}
  .controls {{ position: absolute; bottom: 12px; left: 12px; display: flex; gap: 6px; background: var(--bg-elev); padding: 6px 8px; border: 1px solid var(--border); border-radius: 4px; }}
  .controls button {{ background: var(--bg-elev-2); color: var(--fg); border: 1px solid var(--border); border-radius: 3px; padding: 4px 8px; cursor: pointer; }}
  .controls button:hover {{ background: var(--border); }}
  .detail dt {{ font-size: 11px; color: var(--fg-muted); margin-top: 6px; }}
  .detail dd {{ margin: 0 0 0 0; font-size: 12px; word-break: break-word; }}
  .detail code {{ background: var(--bg-elev-2); padding: 1px 4px; border-radius: 3px; font-size: 11px; display: inline-block; margin: 1px 0; }}
  .pill.unknown {{ background: #3a1f1f; color: #ff9a9a; }}
  .footnote {{ position: absolute; bottom: 8px; right: 12px; color: var(--fg-muted); font-size: 11px; }}
  .summary {{ background: var(--bg-elev-2); border: 1px solid var(--border); border-radius: 4px; padding: 10px 12px; margin: 0 0 12px; font-size: 11px; line-height: 1.5; color: var(--fg-muted); }}
  .summary b {{ color: var(--fg); }}
  .summary .pill {{ margin-right: 4px; }}
  .flow-path {{ font-size: 11px; line-height: 1.7; color: var(--fg-muted); }}
  .flow-path code {{ background: var(--bg-elev-2); padding: 1px 4px; border-radius: 3px; }}
</style>
</head>
<body>
<header>
  <h1>IDX Leadership Diffusion — codemap</h1>
  <div class="meta">repo <b>shadow-balance-sheet-v130-qa.9CUdhs / idx-leadership-diffusion</b></div>
  <div class="meta">commit <b>{commit}</b></div>
  <div class="meta">generated <b>{generated}</b></div>
  <div class="right">Frontier Pass #2 close · {len(data['nodes'])} primary nodes · {len(data['edges'])} edges · {len(data['flows'])} flows</div>
</header>
<div class="layout">
  <aside>
    <div class="summary">
      <b>System</b>: market-wide intelligence for Indonesian equities.
      Provider layer is source-neutral; the engine reads canonical Pydantic
      models. Five flows drive the application.
      <br><br>
      <b>Hero flow</b>: <span class="pill">build-snapshot</span>
      scripts → providers → sectors-client → ledger → market-universe →
      features → aggregation → signals → evidence-builder → data-snapshots.
      <br><br>
      <b>External</b>: Sectors v2 API (gated by allow_live). yfinance is the
      fallback prototype provider.
    </div>
    <h2>Search</h2>
    <input id="search" class="search" placeholder="Filter nodes…" />
    <h2 style="margin-top:14px">Legend</h2>
    <dl class="legend">
      <dt><span class="pill" style="background:#0e1722;color:var(--accent)">module</span></dt>
      <dd>Source module</dd>
      <dt><span class="pill" style="background:#131c12;color:var(--accent-2)">script</span></dt>
      <dd>CLI / app entry</dd>
      <dt><span class="pill" style="background:#14182a;color:#94a3d3">service</span></dt>
      <dd>Provider / external service</dd>
      <dt><span class="pill" style="background:#1f1c0e;color:var(--pending)">data</span></dt>
      <dd>Snapshot / manifest / persistence</dd>
      <dt><span class="pill" style="background:#0e1722;color:var(--accent);opacity:.85">docs</span></dt>
      <dd>Documentation / config</dd>
      <dt><span class="pill" style="background:#1f1c0e;color:var(--pending);opacity:.85">test</span></dt>
      <dd>Test suite</dd>
    </dl>
    <h2 style="margin-top:14px">Nodes</h2>
    <ul class="node-list" id="node-list"></ul>
    <h2 style="margin-top:14px">Flows</h2>
    <ul class="flow-list" id="flow-list"></ul>
  </aside>
  <main>
    <svg id="canvas" width="100%" height="100%">
      <defs>
        <marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto">
          <path d="M0,0 L10,5 L0,10 z" fill="currentColor"></path>
        </marker>
      </defs>
      <g id="viewport">
        <g id="edges-layer"></g>
        <g id="nodes-layer"></g>
      </g>
    </svg>
    <div class="controls">
      <button id="btn-fit">Fit</button>
      <button id="btn-zoom-in">+</button>
      <button id="btn-zoom-out">−</button>
      <button id="btn-reset">Reset selection</button>
    </div>
    <div class="footnote">Drag to pan · scroll to zoom · click a node to highlight</div>
  </main>
  <section id="detail">
    <h2>Detail</h2>
    <div id="detail-body"><p class="meta">Click a node or flow to inspect it.</p></div>
  </section>
</div>
<script>
const NODES = {nodes_json};
const EDGES = {edges_json};
const FLOWS = {flows_json};

function typeOf(n) {{
  if (n.id === 'scripts' || n.id === 'app') return 'script';
  if (['providers','sectors-client','market-universe','pipeline','ledger'].includes(n.id)) return 'service';
  if (['data-snapshots'].includes(n.id)) return 'data';
  if (n.id === 'docs' || n.id === 'config') return 'docs';
  if (n.id === 'tests') return 'test';
  return 'module';
}}

const ns = 'http://www.w3.org/2000/svg';
const svg = document.getElementById('canvas');
const viewport = document.getElementById('viewport');
const nodesLayer = document.getElementById('nodes-layer');
const edgesLayer = document.getElementById('edges-layer');
const nodeListEl = document.getElementById('node-list');
const flowListEl = document.getElementById('flow-list');
const detailBody = document.getElementById('detail-body');
const searchEl = document.getElementById('search');

const NODE_W = 230, NODE_H = 70;
const COLS = 5;
let view = {{ translateX: 60, translateY: 50, scale: 0.85 }};

function nodePosition(i) {{
  const col = i % COLS;
  const row = Math.floor(i / COLS);
  return {{ x: 60 + col * (NODE_W + 60), y: 50 + row * (NODE_H + 80) }};
}}

NODES.forEach((n, i) => {{
  const p = nodePosition(i);
  const g = document.createElementNS(ns, 'g');
  g.setAttribute('class', `node type-${{typeOf(n)}}`);
  g.setAttribute('data-id', n.id);
  g.setAttribute('transform', `translate(${{p.x}},${{p.y}})`);
  const rect = document.createElementNS(ns, 'rect');
  rect.setAttribute('width', NODE_W);
  rect.setAttribute('height', NODE_H);
  rect.setAttribute('rx', 6);
  const t1 = document.createElementNS(ns, 'text');
  t1.setAttribute('x', 10);
  t1.setAttribute('y', 20);
  t1.textContent = n.id;
  const t2 = document.createElementNS(ns, 'text');
  t2.setAttribute('class', 'sub');
  t2.setAttribute('x', 10);
  t2.setAttribute('y', 38);
  t2.textContent = n.path.split('/').slice(-2).join('/');
  const t3 = document.createElementNS(ns, 'text');
  t3.setAttribute('class', 'sub');
  t3.setAttribute('x', 10);
  t3.setAttribute('y', 54);
  t3.textContent = n.role.length > 38 ? n.role.slice(0, 36) + '…' : n.role;
  const t4 = document.createElementNS(ns, 'text');
  t4.setAttribute('class', 'sub');
  t4.setAttribute('x', 10);
  t4.setAttribute('y', 66);
  t4.textContent = `files: ${{(n.files || []).length}}`;
  g.appendChild(rect);
  g.appendChild(t1);
  g.appendChild(t2);
  g.appendChild(t3);
  g.appendChild(t4);
  g.addEventListener('click', (e) => {{ e.stopPropagation(); selectNode(n.id); }});
  nodesLayer.appendChild(g);
  const li = document.createElement('li');
  li.dataset.id = n.id;
  li.textContent = n.id;
  li.addEventListener('click', () => selectNode(n.id));
  nodeListEl.appendChild(li);
}});

function edgePath(a, b) {{
  return `M ${{a.x + NODE_W}} ${{a.y + NODE_H/2}} C ${{a.x + NODE_W + 40}} ${{a.y + NODE_H/2}}, ${{b.x - 40}} ${{b.y + NODE_H/2}}, ${{b.x}} ${{b.y + NODE_H/2}}`;
}}
EDGES.forEach((e) => {{
  const ai = NODES.findIndex(n => n.id === e.from);
  const bi = NODES.findIndex(n => n.id === e.to);
  if (ai < 0 || bi < 0) return;
  const a = nodePosition(ai);
  const b = nodePosition(bi);
  const cls = `t-${{e.type === 'publishes' || e.type === 'subscribes' ? 'pubsub' : e.type}}`;
  const p = document.createElementNS(ns, 'path');
  p.setAttribute('class', `edge ${{cls}}`);
  p.setAttribute('d', edgePath(a, b));
  p.setAttribute('marker-end', 'url(#arr)');
  p.dataset.from = e.from;
  p.dataset.to = e.to;
  edgesLayer.appendChild(p);
}});

FLOWS.forEach((f, i) => {{
  const li = document.createElement('li');
  li.dataset.id = f.id;
  li.textContent = f.id + (i === 0 ? '  (hero)' : '');
  li.addEventListener('click', () => selectFlow(f.id));
  flowListEl.appendChild(li);
}});

function clearHighlights() {{
  [...document.querySelectorAll('.node')].forEach(n => n.classList.remove('active', 'faint'));
  [...document.querySelectorAll('.edge')].forEach(e => e.classList.remove('active', 'dim'));
  [...nodeListEl.children].forEach(li => li.classList.remove('active'));
  [...flowListEl.children].forEach(li => li.classList.remove('active'));
}}

function edgePairsForNodes(ids) {{
  const set = new Set(ids);
  const pairs = new Set();
  EDGES.forEach(e => {{
    if (set.has(e.from) && set.has(e.to)) pairs.add(e.from + '|' + e.to);
  }});
  return pairs;
}}

function highlightNodeSet(ids, edgePairs) {{
  const idset = new Set(ids);
  [...document.querySelectorAll('.node')].forEach(n => {{
    n.classList.toggle('faint', !idset.has(n.dataset.id));
  }});
  [...document.querySelectorAll('.edge')].forEach(e => {{
    e.classList.toggle('dim', !edgePairs.has(e.dataset.from + '|' + e.dataset.to));
  }});
}}

function selectNode(id) {{
  clearHighlights();
  const incoming = EDGES.filter(e => e.to === id);
  const outgoing = EDGES.filter(e => e.from === id);
  const involved = new Set([id, ...incoming.map(e => e.from), ...outgoing.map(e => e.to)]);
  highlightNodeSet(involved, edgePairsForNodes(involved));
  [...nodeListEl.children].forEach(li => li.classList.toggle('active', involved.has(li.dataset.id)));
  const flows = FLOWS.filter(f => f.steps.includes(id));
  [...flowListEl.children].forEach(li => {{
    li.classList.toggle('active', flows.some(f => f.id === li.dataset.id));
  }});
  const n = NODES.find(x => x.id === id);
  const tests = (n.tests || []).map(t => `<code>${{t}}</code>`).join('<br>');
  const entry = (n.entrypoints || []).map(e => `<code>${{e}}</code>`).join('<br>');
  const constraints = (n.constraints || []).map(c => `<li>${{c}}</li>`).join('');
  const upstream = incoming.map(e => `<li>${{e.from}} <span class="pill">${{e.type}}</span><br><span class="meta">${{e.evidence}}</span></li>`).join('') || '<li class="meta">none</li>';
  const downstream = outgoing.map(e => `<li>${{e.to}} <span class="pill">${{e.type}}</span><br><span class="meta">${{e.evidence}}</span></li>`).join('') || '<li class="meta">none</li>';
  const flowList = flows.map(f => `<li><code>${{f.id}}</code>: ${{f.trigger}}</li>`).join('') || '<li class="meta">none</li>';
  const fileList = (n.files || []).slice(0, 30).map(p => `<code>${{p}}</code>`).join('<br>') + ((n.files||[]).length > 30 ? `<br><span class="meta">… +${{(n.files||[]).length - 30}} more</span>` : '');
  detailBody.innerHTML = `
    <h2>${{n.id}}</h2>
    <p class="meta">${{n.path}}</p>
    <p>${{n.role}}</p>
    <dl class="detail">
      <dt>Entrypoints</dt><dd>${{entry || '<span class="meta">—</span>'}}</dd>
      <dt>Files (${{(n.files||[]).length}})</dt><dd>${{fileList || '<span class="meta">—</span>'}}</dd>
      <dt>Tests</dt><dd>${{tests || '<span class="meta">—</span>'}}</dd>
      <dt>Constraints</dt><dd><ul style="margin:0;padding-left:14px">${{constraints || '<li class="meta">—</li>'}}</ul></dd>
      <dt>Upstream callers</dt><dd><ul style="margin:0;padding-left:14px">${{upstream}}</ul></dd>
      <dt>Downstream dependencies</dt><dd><ul style="margin:0;padding-left:14px">${{downstream}}</ul></dd>
      <dt>Belongs to flows</dt><dd><ul style="margin:0;padding-left:14px">${{flowList}}</ul></dd>
    </dl>
  `;
}}

function selectFlow(id) {{
  clearHighlights();
  const f = FLOWS.find(x => x.id === id);
  if (!f) return;
  highlightNodeSet(f.steps, edgePairsForNodes(f.steps));
  [...flowListEl.children].forEach(li => li.classList.toggle('active', li.dataset.id === id));
  const stepSet = new Set(f.steps);
  [...document.querySelectorAll('.edge')].forEach(e => {{
    if (stepSet.has(e.dataset.from) && stepSet.has(e.dataset.to)) {{
      e.classList.add('active');
      e.classList.remove('dim');
    }}
  }});
  const path = f.steps.map(s => `<code>${{s}}</code>`).join(' → ');
  detailBody.innerHTML = `
    <h2>${{f.id}}</h2>
    <p class="meta">trigger: ${{f.trigger}}</p>
    <p>outcome: <code>${{f.outcome}}</code></p>
    <div class="flow-path">${{path}}</div>
  `;
}}

searchEl.addEventListener('input', () => {{
  const q = searchEl.value.toLowerCase();
  [...nodeListEl.children].forEach(li => {{
    const n = NODES.find(x => x.id === li.dataset.id);
    const blob = (n.id + ' ' + n.role + ' ' + n.path).toLowerCase();
    li.style.display = blob.includes(q) ? '' : 'none';
  }});
  [...nodesLayer.children].forEach(g => {{
    const n = NODES.find(x => x.id === g.dataset.id);
    const blob = (n.id + ' ' + n.role + ' ' + n.path).toLowerCase();
    g.style.opacity = blob.includes(q) ? 1 : 0.25;
  }});
}});

let isPanning = false, panStart = null, viewStart = null;
svg.addEventListener('mousedown', (e) => {{
  if (e.target === svg || e.target.tagName === 'svg' || e.target === viewport) {{
    isPanning = true;
    panStart = {{x: e.clientX, y: e.clientY}};
    viewStart = {{...view}};
  }}
}});
window.addEventListener('mousemove', (e) => {{
  if (isPanning) {{
    view.translateX = viewStart.translateX + (e.clientX - panStart.x);
    view.translateY = viewStart.translateY + (e.clientY - panStart.y);
    applyView();
  }}
}});
window.addEventListener('mouseup', () => {{ isPanning = false; }});
svg.addEventListener('wheel', (e) => {{
  e.preventDefault();
  const s0 = view.scale;
  const s1 = Math.max(0.4, Math.min(2.2, s0 * (e.deltaY < 0 ? 1.1 : 0.9)));
  const rect = svg.getBoundingClientRect();
  const mx = e.clientX - rect.left;
  const my = e.clientY - rect.top;
  view.translateX = mx - (mx - view.translateX) * (s1 / s0);
  view.translateY = my - (my - view.translateY) * (s1 / s0);
  view.scale = s1;
  applyView();
}}, {{ passive: false }});
function applyView() {{
  viewport.setAttribute('transform', `translate(${{view.translateX}},${{view.translateY}}) scale(${{view.scale}})`);
}}
applyView();

document.getElementById('btn-fit').addEventListener('click', () => {{
  view.scale = 0.85;
  view.translateX = 60;
  view.translateY = 50;
  applyView();
}});
document.getElementById('btn-zoom-in').addEventListener('click', () => {{
  view.scale = Math.min(2.2, view.scale * 1.15);
  applyView();
}});
document.getElementById('btn-zoom-out').addEventListener('click', () => {{
  view.scale = Math.max(0.4, view.scale * 0.85);
  applyView();
}});
document.getElementById('btn-reset').addEventListener('click', () => {{
  clearHighlights();
  detailBody.innerHTML = '<p class="meta">Click a node or flow to inspect it.</p>';
}});

svg.addEventListener('click', (e) => {{
  if (e.target === svg) {{
    document.getElementById('btn-reset').click();
  }}
}});
</script>
</body>
</html>
"""


# --------------------------------------------------------------------------- #
# 8. Driver.
# --------------------------------------------------------------------------- #

def main() -> int:
    data = build_json_map()
    lock = build_lock(data)

    issues = validate(data, lock)
    (OUT / "validation.txt").write_text(
        ("OK\n" if not issues else "ISSUES\n" + "\n".join(f"- {x}" for x in issues)),
        encoding="utf-8",
    )
    if issues:
        print("VALIDATION ISSUES:")
        for x in issues:
            print(" -", x)

    (OUT / "codemap.json").write_text(
        json.dumps(data, indent=2, default=str), encoding="utf-8"
    )
    (OUT / "codemap.lock").write_text(
        json.dumps(lock, indent=2, default=str), encoding="utf-8"
    )
    (OUT / "codemap.html").write_text(
        build_html(data, lock), encoding="utf-8"
    )
    print("Wrote:")
    for f in ("codemap.json", "codemap.lock", "codemap.html", "validation.txt"):
        p = OUT / f
        print(f"  {p.relative_to(REPO)}  ({p.stat().st_size} bytes)")
    print(f"node count: {len(data['nodes'])}")
    print(f"edge count: {len(data['edges'])}")
    print(f"flow count: {len(data['flows'])}")
    return 0 if not issues else 1


if __name__ == "__main__":
    sys.exit(main())
