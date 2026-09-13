# ARCHITECTURE_BASELINE.md — Canonical Architecture

**Purpose:** Single canonical architecture for IDX Leadership Diffusion, synthesized from Agent 1 (`docs/architecture/agent-1-runtime.md` + `agent-1-runtime.json` diagram spec), Agent 2 (`docs/architecture/agent-2-product.md` + `agent-2-feature-matrix.json`), Agent 3 (`docs/architecture/agent-3-data-control.md` + `agent-3-contracts.json`).

**No Sectors API call performed.** `SECTORS_API_KEY` never read, exported, or used. No `yfinance`, `You.com`, `Tavily`, `LlamaParse` live execution. All claims trace to repository files (`docs/`, `src/`, `app/`, `tests/`, `config/`, `data/`).

**Date:** 2026-09-13. **Repo:** `/Users/daffa/Hackathon/idx-leadership-diffusion`.

---

## 1. Architecture at a glance (canonical)

The architecture is a **seven-plane, single-process, synchronous, file-based pipeline** (`docs/ARCHITECTURE.md` §3; `docs/ARCHITECTURE_DECISIONS.md` §1; `docs/FEATURE_ARCHITECTURE.md` §1). Planes are separated by dependency direction and data-flow firewalls. No concurrent writer, no service, no async worker, no scheduler (`docs/ARCHITECTURE.md` §4; `docs/ARCHITECTURE_DECISIONS.md` §1 `PLANE E` / `G`).

```text
QUANTITATIVE MARKET-DATA (A)  ────────>  DETERMINISTIC ANALYTICS (C)
  providers (yfinance / Sectors / Fixture)   features / aggregation / signals
  normalize → canonical models                evidence builder / contracts
         │                                      │
         ▼                                      ▼
RESEARCH DISCOVERY / INGESTION (B)  ───>  EVIDENCE / PROVENANCE (D)  ──> SNAPSHOT GENERATION (E)
  You.com / Tavily / LlamaParse              frozen contracts                  atomic manifest
  bounded crawl / extract / parse             brief-v1 / intelligence-v1          replayable bundle
         │                                      │                                    │
         └──────────────>  READ-ONLY SURFACES (F)  <──────────────────────────────┘
                            Streamlit + React SPA
                            snapshot adapter / adapter.ts
         │
         ▼
CONTROL PLANE (G) — wraps every provider touchpoint
  RawCache / RequestLedger / Budget Preflight / Fail-closed gates
```

The **only permitted path from research (B) into quantitative (A/C)** is through the **B3 IDX-official reducer** (`llama_parse.py`) emitting a validated market-level payload (`quantitative_use=true`, scope `DAILY_STATISTICS_TARGET_METRICS`) with full reconciliation proof (`docs/ARCHITECTURE.md` §3 Key invariant; `docs/ARCHITECTURE_DECISIONS.md` §1; `docs/ARCHITECTURE_DECISIONS.md` §5.3).

---

## 2. Component map (canonical, resolved from agent 1)

Source: `docs/ARCHITECTURE.md` §2 (`Layer responsibilities`); `docs/ARCHITECTURE_DECISIONS.md` §1; `docs/FEATURE_ARCHITECTURE.md` §2.

| Component (repo path) | Plane | Owns | Must NOT own | Evidence path |
|---|---|---|---|---|
| `pipeline.py` (`build_snapshot`, ~979 lines) | E (orchestrator) | Provider pull → taxonomy → features → aggregation → signals → evidence → atomic snapshot write → change digest / quality / manifest | Rendering; provider fallback; future-dated comparison; any provider import other than through `base.py` interface | `docs/ARCHITECTURE.md` §1; `agent-1-runtime.md` §1a |
| `providers/base.py` (`MarketDataProvider`) | A (interface boundary) | Combined interface: security master, price history, benchmark, taxonomy; ABC-free base to avoid MRO conflicts | Any business logic; any threshold/classification/UI copy; direct `yfinance` import outside `public.py` | `docs/ARCHITECTURE.md` §1; `agent-1-runtime.md` §1b |
| `providers/capabilities.py` (`CapabilityNotSupported`) | G (fail-closed) | Protocol definitions; `CapabilityNotSupported` = no silent fallback; `CapabilitySet` introspection | Any vendor-specific HTTP logic | `agent-1-runtime.md` §1b |
| `providers/public.py` (`YFinanceProvider`) | A (market-data) | Replayable market-data support (`yfinance` SDK encapsulated); retry; `RawCache`; canonical frame (`ticker,date,close,adjusted_close,volume`) | Any analysis/classification/aggregation/signal logic | `docs/ARCHITECTURE.md` §1; `agent-1-runtime.md` §1b |
| `providers/sectors*.py` (`sectors_client.py`, `sectors_contracts.py`, `sectors_normalizers.py`, `sectors_fixture.py`) | A (target market-wide) | Live HTTP (`--allow-live` opt-in); paginated; 429-aware; fixture replay (`FixtureProvider`) for regression | Any feature/aggregation/signal/evidence logic; any silent fallback to `public` or `fixture` (`factory.py` raises on conflict) | `docs/ARCHITECTURE.md` §1; `agent-1-runtime.md` §1b; `agent-3-data-control.md` §8 |
| `providers/fixture.py` (`FixtureProvider`) | A (regression) | Deterministic synthetic/demo data; offline regression path | Any live call; any feature logic beyond data provision | `tests/test_aggregation.py`, `tests/test_e2e_demo.py` |
| `providers/ledger.py` (`RequestLedger`) | G (audit) | Append-only request ledger (`provider`, `endpoint`, `params-hash`, `cache_hit`, `status`, `rows`, `elapsed`, `estimated+reserved+actual`); flush to `data/raw/request_ledger.jsonl` | Any metric computation; any UI rendering | `agent-1-runtime.md` §1b; `docs/ARCHITECTURE.md` §4 |
| `providers/you_client.py` (`YouClient`) | B (discovery) | `search_context()` → `WEB_CONTEXT` records; `quantitative_use: False` hardcoded; `max_http_requests=3`; `YOU_API_KEY` gate (`allow_live=False` default) | Any feature/aggregation/signal/evidence metric; any `quantitative_use` promotion | `docs/ARCHITECTURE.md` §1; `agent-1-runtime.md` §1b |
| `providers/tavily_client.py` (`TavilyClient`) | B (retrieval) | `search`/`extract`/`crawl` bounded (`depth ≤5`, `breadth ≤20`, `external` off by default); `TAVILY_API_KEY` gate (`allow_live=False` default) | Any feature logic; any crawl without depth/limit; any metric promotion | `agent-1-runtime.md` §1b; `agent-3-data-control.md` §7 |
| `providers/llama_parse.py` (`run_llama_parse`, `normalize_daily_statistics_markdown`) | B3 (document adapter — target) | Bounded `target_pages` (default `"1-2"`); official `idx.co.id` HTTPS PDF allowlist; tier-priced estimate vs ceiling; deterministic reducer (`close`, `previous`, `change`, `net foreign` with reconciliation); full parse kept as audit sidecar; `DAILY_STATISTICS_TARGET_METRICS` only; dual upload/spend gates | Any per-ticker metric; any silent remap; any value/unit/sign change without proof; any `quantitative_use=true` without full gate (`agent-3-data-control.md` §14) | `agent-1-runtime.md` §1b; `agent-3-data-control.md` §7 |
| `providers/fixture.py` (fixture replay for B3) | B (offline regression) | Fixture/offline parser; regression path for `LlamaParse` adapter | Any cloud upload; any credit spend; any live HTTP | `agent-3-data-control.md` §15 Phase B |
| `features/*.py` (`returns`, `breadth`, `concentration`, `relative_strength`, `concentration_v2`) | C (analytics — pure) | Per-security features; no vendor objects reach this layer (`docs/ARCHITECTURE.md` §4 design principle 3) | Any provider/network/credential import | `agent-1-runtime.md` §1c; `tests/test_breadth.py`, `tests/test_concentration.py`, `tests/test_concentration_v2.py` |
| `aggregation/groups.py` (`build_group_snapshots`, `rank_groups`) | C | Group snapshots + deterministic ranking; min constituents + min coverage gates | Any provider import; any future-dated comparison (rejected by `_load_compatible_history`) | `tests/test_aggregation.py` |
| `signals/*.py` (`leadership.py`, `diffusion.py`, `diffusion_v2.py`, `change_digest.py`, `transitions.py`) | C | Independent dimensions (Leadership / Diffusion / Concentration / Confirmation); `UNCONFIRMED` default; no shared score | Any feature-engine mutation; any provider/network import | `tests/test_diffusion_group_size.py`, `tests/test_states.py` |
| `analytics/*.py` (`contradictions.py`, `invalidation.py`, `data_gaps.py`, `persistence.py`, `turnover.py`, `sensitivity.py`) | C / D | Deterministic contradiction rules; frozen gap categories (`DataGapCategory` ×7); persistence; screen invalidation; sensitivity audits | Any non-deterministic model judgment; any research-text ingestion without promotion gate | `docs/ARCHITECTURE.md` §5; `tests/test_brief_contract.py` |
| `evidence/builder.py` (`build_group_evidence`) | D | `GroupEvidence`: `confirmation=ConfirmationEvidence()` (empty by construction); contradiction rows; frozen gap categories; invalidation records; contract version `intelligence-v1` | Any raw data fetch; any metric computation; any promotion without gate (`agent-3-data-control.md` §14) | `agent-1-runtime.md` §1d; `tests/test_evidence.py` |
| `intelligence/contract.py` (`BRIEF_SECTIONS` ×9 frozen; `brief-v1`; `intelligence-v1`) | D | Frozen contract for brief sections, gap categories, status enums | Any contract change without new version (`v1` → `v2`) | `tests/test_brief_contract.py` |
| `models/*.py` (`security_master.py`, `price_observation.py`, `group_snapshot.py`, `security_feature_snapshot.py`, `manifest.py`, `evidence.py`, `flow.py`) | A3 / C / E (canonical truth) | Schema truth; `None`/`UNCONFIRMED` for missing; extra-forbid at intelligence boundary; `ProviderMode` enum (`DEMO_FIXTURE` / `PUBLIC_PROTOTYPE` / `SECTORS_FIXTURE` / `SECTORS_LIVE`) | Any I/O / network import; any rendering logic | `tests/test_schema.py` |
| `pipeline.py` (`build_snapshot`, `_atomic_json`) | E | Atomic write (`tmp` + `rename`); version-stamped (`snapshot-v2`, `methodology-v3`, `features-v3`, `schemas-v2`); manifest aggregation; comparable-history gate (`snap_as_of < current`, contract match required) | Any future-dated comparison; any partial snapshot visibility; any provider fallback (`factory.py` raises); any rendering import | `tests/test_pipeline.py`, `tests/test_snapshot_adapter.py` |
| `data/snapshots.py` (`SnapshotWriter`, `SnapshotReader`) | E (store) | Atomic writes; parquet + CSV duals; manifest (`manifest.json`); snapshot-id allowlist (`^[A-Za-z0-9_-]+$`); history loader with comparability gate | Any write without manifest; any non-atomic update; any partial visibility | `tests/test_snapshot_comparability.py`, `tests/test_e2e_snapshot_export.py` |
| `data/quality.py`, `manifests.py`, `comparability.py`, `endpoint_status.py` | E / G | Quality assessment; manifest aggregation; endpoint status; compatibility checks | Any imputation (`STALE` surfaces but never replaced by `READY` synthetic value) | `tests/test_endpoint_status.py` |
| `app/streamlit_app.py` (915 lines) | F1 | Read-only harness; 4 tabs; `available_sources()` reads local artifacts only (`snapshots/**/snap_*/manifest.json`); `_safe_mode_hint` (provider name alone never proves live call) | Any provider import; any credential/network call (`tests/test_provider_modes_and_readiness.py`) | `docs/ARCHITECTURE.md` §1; `agent-1-runtime.md` §1e |
| `app/web/src/App.tsx` + `pages/` (MarketOverview, LeadershipMap, GroupExplorer, TickerAnalysis, WhatChanged, Methodology) | F2 | React surface consuming exported JSON (`SnapshotPayload`); defensive normalization (`normalizeDataStatus` → `UNAVAILABLE`, never `READY`); comparability suppression (`INCOMPARABLE` suppresses previous states and material shifts) | Any provider/network call at serve time; any metric computation (`tests/test_ui_productization.py`) | `agent-2-product.md` §1; `tests/test_ui_story_mode.py` |
| `app/web/src/components/AppShell.tsx` | F2 (chrome) | 9-item sidebar nav (`What Changed 01` … `Methodology 09`); provider-mode label; quality-status dot; taxonomy toggle (Sector/Industry, disabled with explanation); error/loading states | Any provider/network call; any metric computation | `agent-2-product.md` §1 |
| `scripts/export_snapshot_json.py` | F2 (export lane) | Snapshot-directory → single JSON (`public/snapshots/<id>.json`) for React; presentation-only transforms (`rebase` to 100); never feeds back into signals | Any signal recomputation; any live provider call (`tests/test_e2e_snapshot_export.py`) | `agent-1-runtime.md` §1d |
| `scripts/enrich_tavily_context.py`, `scripts/enrich_you_context.py`, `scripts/build_research_events.py`, `scripts/refresh_idx_statistics.py`, `scripts/refresh_idx_daily_statistics.py` | B (research sidecars) | Sidecar JSON output (`tavily_context.json`, `you_context.json`, `research_events`, `idx_daily_statistics`) — never quantitative inputs | Any snapshot-core mutation; any feature-engine import | `agent-1-runtime.md` §1a; `tests/test_research_context.py` |
| `tests/test_provider_contracts.py`, `tests/test_parity_public_sectors.py`, `tests/test_live_preflight.py`, `tests/test_429_blocked_path.py`, `tests/test_provider_modes_and_readiness.py`, `tests/test_comparability_and_adapter.py`, `tests/test_snapshot_comparability.py`, `tests/test_no_lookahead_synthetic.py`, `tests/test_synthetic_scenarios.py` (scenarios A–G) | G (regression / guardrail) | Offline regression walls for provider contracts, parity, budget/preflight gates, 429 honor, provider-mode readiness, comparability suppression, no-lookahead rules, synthetic market scenarios | Any live network call (`tests/test_...` all use fixtures or mock clients) | `tests/test_...` file list (`agent-1-runtime.md` §1d); `agent-3-data-control.md` §5 (`Phase B`) |

---

## 3. Dependency directions and forbidden dependencies (canonical)

Source: `docs/ARCHITECTURE.md` §5 (`Allowed` / `Forbidden` dependency list); `docs/ARCHITECTURE_DECISIONS.md` §5 (`Allowed` / `Forbidden` dependency list); `docs/FEATURE_ARCHITECTURE.md` §5 (`Quantitative plane rules` / `Research plane rules`).

### 3.1 Allowed (caller → callee, inward toward determinism)

```text
scripts/* → pipeline (E) → providers (base interface only) → features (C) → aggregation (C) → signals (C) → analytics (C) → evidence (D) → data.snapshots (E)

evidence (D) → models (canonical) + analytics (contradictions / invalidation / gaps)

intelligence/contract (D) → evidence (D) (never raw frames)

app/* (F) → data_sources (local artifacts) → snapshot_adapter → view_models → streamlit_app / adapter.ts

app/web (F) → exported JSON (`export_snapshot_json.py`) → adapter.ts → snapshot.ts / pages / components

providers/* (A/B) → {data.RawCache, providers.ledger, utils.config, models} only

pipeline (E) → data.snapshots (E) → manifest + snapshot bundles; never → app/* / app/web/*
```

### 3.2 Forbidden (load-bearing; regression-test candidates)

1. `features | aggregation | signals | analytics | evidence | intelligence` → `providers.public | providers.sectors | providers.you_client | providers.tavily_client | providers.llama_parse` or any `urllib` / `yfinance` / `llama_cloud` direct import outside the provider boundary (`agent-1-runtime.md` §5 item 1; `docs/FEATURE_ARCHITECTURE.md` §5.1).
2. `you_client | tavily_client` → `features | aggregation | signals | analytics` or any `ConfirmationEvidence` numeric field (`agent-1-runtime.md` §5 item 2; `docs/FEATURE_ARCHITECTURE.md` §5.1 `Forbidden inputs`).
3. `app/streamlit_app | app/data_sources | app/view_models | app/snapshot_adapter | app/web/src/*` → any provider, credential, socket, `allow_live` flag, or `urllib` call (`agent-1-runtime.md` §5 item 3; `docs/FEATURE_ARCHITECTURE.md` §4 `Critical rules`).
4. `pipeline` (`build_snapshot`) → `app/*` or `app/web/*` (orchestrator never renders; `agent-1-runtime.md` §5 item 4; `docs/FEATURE_ARCHITECTURE.md` §1).
5. `Sectors-live` → `YFinanceProvider` or `FixtureProvider` as silent fallback (`provider/factory.py` raises; `agent-1-runtime.md` §5 item 5; `docs/FEATURE_ARCHITECTURE.md` §4 `No feature writes to snapshot core`).
6. `snapshot history reader` (`_load_compatible_history`) → future-dated (`snap_as_of >= current`) or contract-incompatible (`manifest` version mismatch) snapshots for transitions / persistence (`agent-1-runtime.md` §5 item 6; `tests/test_no_lookahead.py`, `tests/test_no_lookahead_synthetic.py`).
7. `export_snapshot_json.py` / React adapter → any metric promotion (`READY` never synthesized from `UNAVAILABLE`); any unknown enum mapped to `READY` (`normalizeDataStatus` maps unknown → `UNAVAILABLE`; `snapshot_adapter.py` maps unknown enum → `UNCONFIRMED` default) (`agent-1-runtime.md` §5 item 7; `tests/test_comparability_and_adapter.py`).
8. Any writer → partial snapshot visibility (atomic `tmp + rename`; snapshot-id allowlist enforced; `agent-1-runtime.md` §5 item 8; `data/snapshots.py`).

---

## 4. Provider responsibility matrix (canonical)

Source: `docs/ARCHITECTURE.md` §1; `docs/PRODUCT_ARCHITECTURE_PLAN.md` §4; `docs/ARCHITECTURE_DECISIONS.md` §3; `docs/FEATURE_ARCHITECTURE.md` §2.

| Work | Primary provider | Secondary (only for cross-check / gap-fill) | Forbidden behavior |
|---|---|---|---|
| Daily price + benchmark (quantitative) | `Sectors` live (`sectors_client.py`, `sectors_contracts.py`) — **only after** auth + full-universe pagination + price-basis verification + taxonomy parity + benchmark parity + credit economics verified (`agent-3-data-control.md` §15 Phase D/E) | `yfinance` (`public.py`) for replay/regression (`FixtureProvider` for offline regression) | Never use search-result text (`tavily_context.json`, `you_context.json`) as a price value; never treat `FixtureProvider` synthetic prices as market truth without `provider_mode` label |
| Discovery (broad recall / research) | `YouClient` (`you_client.py`; `search_context`) | `TavilyClient` (`tavily_client.py`; `search`) — only for cross-check of specific URLs/sources; never both by default for same query | Never run both providers for same query by default (`agent-3-data-control.md` §7 `routing.research_query_policy`); never inject `WEB_CONTEXT` into `SF`/`GS` without promotion gate |
| Targeted search / crawl / extract | `TavilyClient` (`search`/`extract`/`crawl`; bounded `depth ≤5`, `breadth/limit ≤20`, `allow_external=false` default) | `YouClient` (`contents`) — only for official source retrieval; never crawl without explicit limit | Crawl without depth/limit (`agent-3-data-control.md` §7); any crawl result that does not pass promotion gate (`agent-3-data-control.md` §14) must stay `CONTEXT ONLY` |
| Official IDX PDF parsing (B3 adapter) | `LlamaParse` adapter (`run_llama_parse`; bounded `target_pages`; first-party `https://*.idx.co.id` URL allowlist; dual upload/spend gates; tier-priced estimate vs ceiling) | Fixture/offline parser (`fixture.py`) for regression; manual parser (`normalize_daily_statistics_markdown`) for deterministic reducer | Any full-document upload without page budget; any value remap without reconciliation proof (`close - previous = change`; `change / previous = pct`; decimal/comma repair only with proof); any `quantitative_use=true` without full gate (`agent-3-data-control.md` §14) |
| Document retrieval over staged docs (LlamaIndex adapter) | `LlamaIndex` adapter (planned — `agent-3-contracts.json` `routing.llamaindex_constraint`) — retrieval over `data/research/` or `data/snapshots/` staged docs; output `WEB_CONTEXT` with `quantitative_use=false` preserved | Not applicable (planned adapter only) | Any retrieval that produces `quantitative_use=true` without promotion gate; any retrieval over unstaged/unverified documents |
| Synthesis / research answers | `YouClient` research (`search` mode with explicit approval only; `agent-3-data-control.md` §7 `routing.research_query_policy`) | Not applicable (no synthesis model assigned; `agent-2-product.md` non-goal #1 excludes chatbot/recommender) | Any synthesis output treated as a number, confirmation metric, or recommendation; any `WEB_CONTEXT` promoted to `SNAPSHOT` without promotion gate |

---

## 5. Quantitative data flow (canonical, evidence-backed)

Source: `docs/ARCHITECTURE.md` §2 (`High-level flow`); `docs/ARCHITECTURE.md` §6 (`Quantitative data flow` in `agent-1-runtime.md`); `docs/FEATURE_ARCHITECTURE.md` §2 (`Feature-to-module` mapping); `docs/ARCHITECTURE_DECISIONS.md` §1 (`Quantitative plane rules`).

```text
config/universe.yaml (tickers, benchmark ^JKSE, taxonomy)
config/methodology.yaml (horizons 5/20/60, ±10pp breadth gate, ±10pp diffusion v2 gate, floor 10%, min 5 constituents, 60% coverage gate — methodology-v3 / features-v3; no magic numbers in code)
config/providers.yaml (provider mode pin: `public` ≡ `YFinanceProvider`; `sectors` ≡ `SectorsProvider`; `fixture` ≡ `FixtureProvider`; `allow_live`, `allow_credit_spend` gates)
         │
         ▼
MarketDataProvider.get_price_history / get_benchmark_history / get_group_taxonomy (`base.py` interface; `public.py`, `sectors*.py`, `fixture.py`)
         │ (RawCache TTL hit? → `provider/ledger.py`: `cache_hit=true`, 0ms, 0 credits, `data/cache/` sha-keyed JSON)
         │ (Cache miss → vendor call with retry → ledger miss + rows + elapsed + estimated reserve; `public.py` retry; `sectors_client.py` pagination + 429 honor)
         ▼
Canonical frames (`public.py`: `ticker,date,close,adjusted_close,volume`; `sectors_normalizers.py`: taxonomy fields; benchmark frame)
         │ (Effective price basis: `Sectors` modes force `close` with `adjusted_close` alias until full corp-action audit; `pipeline.py` `resolve_effective_price_basis`)
         ▼
Quality assessment (`data/quality.py`: `STALE`, `FAILED`, `UNAVAILABLE`; coverage %, duplicate checks; `market_universe.py`: eligible set + sha-hash; policy exclusion vs acquisition failure kept distinct — `docs/ARCHITECTURE.md` design principle 1)
         ▼
Feature engine (`features/returns.py`: 5/20/60d excess + YTD; `relative_strength.py`)
         ▼
Taxonomy filter (`taxonomy/registry.py`: sector / konglo / themes; `aggregation.py`: group aggregation; policy gate — ineligible tickers excluded before feature computation — `docs/ARCHITECTURE.md` §2 A2-A4)
         ▼
Aggregation / Group snapshot (`aggregation/groups.py`: `build_group_snapshots`, `rank_groups`; `models/group_snapshot.py`; `min_constituents` + `min_coverage` gates; `group_snapshot` carries nested `ConcentrationMetrics` from `concentration_v2.py`)
         ▼
Signals (independent dimensions, no shared score — `docs/ARCHITECTURE.md` design principle; `agent-1-runtime.md` §1c)
         ├─ Leadership (`signals/leadership.py`: 4-state + UNCONFIRMED; from excess + acceleration; `LeadershipState` enum `models/enums.py`)
         ├─ Diffusion v1 (`signals/diffusion.py`: `BROADENING` / `STABLE` / `NARROWING`; `DiffusionState` enum)
         ├─ Diffusion v2 (`signals/diffusion_v2.py`: `FIRM` / `FRAGILE`; ±10pp gate + group-size floor; `DiffusionStateV2` enum)
         ├─ Concentration v2 (`features/concentration_v2.py`: `absolute_move_v2` + HHI + signed share; top-1/3/5 capped at 1.0 — never merged into single score; `ConcentrationMetrics` nested in `group_snapshot`)
         └─ Confirmation (`evidence/builder.py`: `ConfirmationEvidence()` empty by construction; `UNAVAILABLE` / `DATA_GAP` default — `docs/ARCHITECTURE.md` design principle)
         ▼
Transitions (`signals/transitions.py`: categorical change + quantitative corroboration required; `signal_change_digest.py`: ranked digest; `TE` contract)
         ▼
Persistence / Contradictions / Invalidation / Gaps (`analytics/*.py`)
         ▼
Snapshot writer (`pipeline.py`: `SnapshotWriter.write` — atomic `tmp + rename`; `snapshot-v2` version; `manifest.json`; full directory bundle)
         ├── `prices.parquet`, `benchmark.parquet`, `security_master.json`
         ├── `features.parquet`, `groups.parquet`, `groups.parquet` (nested `ConcentrationMetrics`)
         ├── `transitions.parquet`, `evidence.json`, `manifest.json`
         ├── `quality.json`, `coverage.json`, `change_digest.json`, `market_read.json`
         ├── `story_mode.json`, `security_master.json` (canonical master, not raw vendor response)
         └── `comparability.json` (`snap_as_of` + contract version match — `_load_compatible_history` rejects future / incompatible)
         │
         ├── Streamlit (`app/streamlit_app.py`): `load_snapshot_payload` → `snapshot_adapter.row_to_group_snapshot` (NaN → None; unknown enum → `UNCONFIRMED` default) → `build_dashboard_view` → `overview()` / `leadership_map_page()` / `group_explorer()` / `method_quality()`
         │
         └── React (`scripts/export_snapshot_json.py` → `app/web/dist/snapshots/<id>.json` → `SnapshotProvider` + `adapter.ts` → pages; `adapter.ts`: `normalizeDataStatus` → `UNAVAILABLE` for unknown; `INCOMPARABLE` suppresses previous state / material shift — `tests/test_comparability_and_adapter.py`)
```

**No step after `assess_quality` performs I/O (`agent-1-runtime.md` §6: `No step after assess_quality performs I/O`). No UI step performs I/O beyond local artifact reads (`agent-1-runtime.md` §6: `No UI step performs I/O beyond local reads`).**

---

## 6. Research-evidence data flow (canonical, evidence-backed)

Source: `docs/ARCHITECTURE.md` §7 (`Research-evidence flow`); `docs/ARCHITECTURE_DECISIONS.md` §5.2 (`Research plane rules`); `docs/FEATURE_ARCHITECTURE.md` §5.2; `docs/ARCHITECTURE_DECISIONS.md` §4.2 (`Promotion rule`).

```text
Explicit CLI only (never pipeline.build_snapshot; never UI open at serve time):

  scripts/enrich_tavily_context.py  /  scripts/enrich_you_context.py
  scripts/build_research_events.py  /  scripts/refresh_idx_statistics.py
  scripts/refresh_idx_daily_statistics.py  /  scripts/enrich_tavily_context.py
         │ (each client: `allow_live=False` default; needs key + explicit flag; `You`/`Tavily` max 3 HTTP attempts; `LlamaParse` needs `allow_cloud_upload` + `allow_credit_spend` + budget reserve; `429`/`5xx` honor `Retry-After`; `test_429_blocked_path.py` verifies 429 honor; `test_live_preflight.py` verifies preflight gates)
         ▼
B1 Discovery (`YouClient` / `TavilyClient`): bounded queries (`max_http_requests=3`; `search_context()` / `search()` with bounded count/depth/topic); `quantitative_use: False` hardcoded (`agent-3-contracts.json` `contracts.claim.quantitative_use_default`)
         ▼
B2 Retrieval (`YouClient.contents` / `TavilyClient.extract` / `TavilyClient.crawl`): bounded (`crawl` depth ≤5, `breadth/limit` ≤20, `external` off by default; first-party `https://*.idx.co.id` preferred for `LlamaParse` allowlist)
         ▼
B3 Parse (`LlamaParse` adapter): bounded pages (`default "1-2"`); official IDX Daily Statistics PDF allowlist (`first_party_https_idx_co_id`); tier-priced estimate vs ceiling (`agentic` / `agentic_plus` / `cost_effective` / `fast` tiers; `cost_tables` in `agent-3-contracts.json`); full parse kept as audit sidecar (`raw_artifact_path`); deterministic reducer promotes **only** validated market-level cards (`IHSG close/previous/change/change-pct` with reconciliation; `net foreign Today/YTD` with units + labels; market `PER/PBV` with reconciliation — `agent-3-data-control.md` §7); any unreconciled value / missing label → `LlamaParseError` (fail loudly, not remap silently — `agent-3-data-control.md` §7; `agent-2-product.md` §2 `LlamaParse layout dependence` warning)
         ▼
Sidecar outputs (never snapshot-core mutations; never quantitative input unless promotion gate passed):
  ├─ `tavily_context.json` (`WEB_CONTEXT`; `quantitative_use: false`)
  ├─ `you_context.json` (`WEB_CONTEXT`; `quantitative_use: false`)
  ├─ `research_events` (`event_id`, `date`, `category`, `context` — `quantitative_use: false`)
  ├─ `idx_daily_statistics` (official release cards: `OFFICIAL_RELEASE` badge; `DAILY_STATISTICS_TARGET_METRICS` only; `quantitative_use: true` allowed only after full reconciliation — `agent-1-runtime.md` §7; `agent-3-data-control.md` §7)
  ├─ `tavily_context.json` / `you_context.json` referenced by snapshot as `R-SIDE` (sidecar), never as `SF`/`GS`/`TE`
  └─ Evidence sidecar (`evidence.json` / `EV`) carries `data_gaps` (`DataGapCategory` ×7 frozen) and `confirmation` (`UNAVAILABLE` / `DATA_GAP` by default — `evidence/builder.py`; `intelligence/contract.py`)
```

**No web text enters Planes A (quantitative) / C (deterministic analytics) / E (snapshot core) (`agent-1-runtime.md` §6 Key invariant; `docs/ARCHITECTURE_DECISIONS.md` §1 Key invariant; `docs/FEATURE_ARCHITECTURE.md` §5.1 Forbidden inputs).**

---

## 7. Read-only product surfaces (canonical, no provider/network at serve time)

Source: `docs/ARCHITECTURE.md` §5 (`Read-only product surfaces`); `docs/FEATURE_ARCHITECTURE.md` §2 (`Feature-to-module` mapping); `docs/ARCHITECTURE_DECISIONS.md` §1 (`PLANE F`).

### 7.1 Streamlit (`F1`)

Path: `app/streamlit_app.py` (915 lines); `app/data_sources.py`; `app/snapshot_adapter.py`; `app/view_models.py` (1207 lines); `app/components.py`.

- Read-only harness: `available_sources()` = demo fixture (`fixture.py`) + local `data/snapshots/**/snap_*/manifest.json` (`data_sources.py`); `load_snapshot_payload()` never constructs a provider (`tests/test_provider_modes_and_readiness.py` verifies credit-inert open); `_safe_mode_hint` (`provider` name alone never proves a live call — `data_sources.py` docstring).
- Four tabs (`overview`, `leadership_map_page`, `group_explorer`, `method_quality`): read from `DashboardView` / `GroupView` / `MaterialShiftView` / `ContradictionRow` / `InvalidationRow` dataclasses (`view_models.py`).
- Provider pill (`_provider_pill`): `SECTORS LIVE` / `SECTORS FIXTURE` / `DEMO FIXTURE` / `PUBLIC PROTOTYPE` (`streamlit_app.py` line 203-211).
- Evidence contract (`BRIEF_SECTIONS` frozen ×9): `Market Read`, `Official Release`, `Source-backed Sample`, `Static Lens`, `Static Context`, `Methodology`, `Data Quality`, `Evidence`, `Provenance` (`docs/HYBRID_PRODUCT_MODEL.md` §6).
- Data-gap rollup (`data_gap_rollup`): frozen 7 categories (`docs/ARCHITECTURE.md` §5; `intelligence/contract.py` `BRIEF_CONTRACT_VERSION="brief-v1"`); `STALE` / `FAILED` / `UNAVAILABLE` / `UNCONFIRMED` surfaces (`analytics/data_gaps.py`).
- No chatbot/recommender/broker terminal (`docs/ARCHITECTURE.md` §5 non-goals; `docs/ARCHITECTURE_DECISIONS.md` §6).

### 7.2 React SPA (`F2`)

Path: `app/web/src/App.tsx` (12 routes); `pages/` (`MarketOverview`, `LeadershipMap`, `GroupExplorer`, `TickerAnalysis`, `WhatChanged`, `Methodology`); `components/AppShell.tsx` (9-item sidebar); `components/EvidenceModel.tsx` (badge kinds: `SNAPSHOT`, `OFFICIAL_RELEASE`, `SAMPLE`, `PROTOTYPE`, `CONTEXT`); `components/StatusChips.tsx` (7 states); `components/EmptyState.tsx` (dashed card pattern); `data/adapter.ts` (1400+ lines); `data/snapshot.ts` (wire types `SnapshotPayload`); `SnapshotProvider` / `SnapshotContext` (read-only fetch); `data/readiness.ts` (`buildDiffusionReadiness` with `DATA_GAP` / `READY_WITH_GAPS` / `READY`); `data/researchContext.ts` (hardcoded `quantitative_use: false`); `data/mapGeometry.ts`, `mapLabels.ts`, `rotation.ts`, `format.ts`.

- Read-only (`SnapshotProvider`): fetch `/snapshots/index.json` + `/snapshots/<id>.json` + optional `official_release_*.json`; index/payload mismatch guard; never calls a provider (`tests/test_ui_productization.py`).
- Defensive normalization (`adapter.ts` `normalizeDataStatus`): unknown status → `UNAVAILABLE` (never `READY`); `INCOMPARABLE` suppresses previous-state fabrication and material-shift claims (`tests/test_comparability_and_adapter.py`).
- `RouteErrorElement` (`App.tsx`): fail-visible snapshot error (`"Snapshot unavailable"`); `RouteErrorElement` never suppresses errors.
- `AppShell.tsx`: taxonomy toggle (`Sector` / `Industry`) disabled with explanation when `Industry` absent (`Industry` deferred — `docs/FEATURE_ARCHITECTURE.md` §4 deferred); `provider_mode` pill; `quality` dot.
- Page-level evidence badges (`SNAPSHOT` / `OFFICIAL_RELEASE` / `SAMPLE` / `PROTOTYPE` / `CONTEXT`) fixed; no badge promotion (`docs/HYBRID_PRODUCT_MODEL.md` §6 lanes).

---

## 8. Cache / ledger / budget / fail-closed (canonical, G plane)

Source: `docs/ARCHITECTURE.md` §4 (`Cache / Ledger / Budget / Fail-closed`); `docs/ARCHITECTURE_DECISIONS.md` §6 (`Explicit DATA GAP / UNCONFIRMED` list); `docs/FEATURE_ARCHITECTURE.md` §4 (`Critical rules`).

| Control | Implementation (`repo` evidence) | Status | Evidence path |
|---|---|---|---|
| `RawCache` (`G1`) | `data/__init__.py` (`RawCache`); filesystem TTL cache (`data/cache/`); sha-keyed JSON (`sha256` of request fingerprint); separate roots for market (`data/cache/00..`) and research (`data/cache/you`, `data/cache/tavily`) | Implemented | `agent-1-runtime.md` §1b (`RawCache`); `tests/test_...` (fixture replay uses cached artifacts) |
| `RequestLedger` (`G2`) | `providers/ledger.py` (`RequestLedger`); append-only (`.jsonl`); `provider` / `endpoint` / `params-hash` / `cache_hit` / `status` / `rows` / `elapsed` / `estimated+reserved+actual` credits; `flush` method; `data/raw/request_ledger.jsonl` / `data/raw/you_request_ledger.jsonl` / `data/raw/tavily_request_ledger.jsonl` | Partial (per-provider; unified cross-provider envelope is target-state — `agent-3-data-control.md` §20) | `agent-1-runtime.md` §1b; `docs/ARCHITECTURE.md` §4; `tests/test_provider_contracts.py` (fixture-only) |
| Budget / Preflight (`G3`) | `providers/factory.py` (`build_provider_from_config`, `parse_provider_mode`, `allow_live` gate, credit ceiling + reserve); `tests/test_live_preflight.py` (preflight reserve + estimated cost); `tests/test_429_blocked_path.py` (429 honor); `tests/test_provider_modes_and_readiness.py` (mode pinning) | Partial (per-provider gates exist; unified cross-provider budget reconciliation is target-state) | `agent-1-runtime.md` §1b (`G3`); `agent-3-data-control.md` §20 (`post_request_accounting`) |
| Fail-closed (`G4`) | `providers/capabilities.py` (`CapabilityNotSupported`); `provider/factory.py` (mode pinning — raises on conflict, no implicit fallback); `tests/test_429_blocked_path.py` (429 honor); `tests/test_provider_contracts.py` (capability contract); `tests/test_sentinel_and_429.py` (429 + sentinel) | Implemented (per-provider) | `agent-1-runtime.md` §1b (`G4`); `agent-1-runtime.md` §5 (forbidden dependency list includes no silent fallback) |

**Explicit `DATA GAP` / `UNCONFIRMED` / `CONTEXT ONLY` status (canonical list — from `docs/ARCHITECTURE_DECISIONS.md` §6; `docs/FEATURE_ARCHITECTURE.md` §3; `docs/ARCHITECTURE.md` §5; `docs/ARCHITECTURE_DECISIONS.md` §6):**

- `DATA GAP` — `Sectors` live auth / coverage / pagination / price basis / taxonomy parity / benchmark parity / credit economics not load-tested (`docs/SECTORS_BLOCKERS.md`; `docs/SECTORS_MIGRATION_READINESS.md`; `docs/SECTORS_CREDIT_AUDIT.md`; `tests/test_provider_contracts.py` — fixture-only; `tests/test_sectors_client.py` — pagination exists but live full-universe not verified).
- `DATA GAP` — Cross-provider budget reconciliation (reserve vs actual debit vs account balance unavailable client-side — `docs/SECTORS_CREDIT_AUDIT.md`; `agent-3-data-control.md` §19 `Credit observability gap`).
- `UNCONFIRMED` — Typed claim envelope (`R-CLAIM`) designed (`agent-3-contracts.json`) but not implemented (`docs/ARCHITECTURE_DECISIONS.md` §6; `agent-2-product.md` §2).
- `UNCONFIRMED` — Generic parser adapter (`B3`) beyond IDX Daily Statistics (`llama_parse.py` adapter exists; broader interface target-state — `agent-1-runtime.md` §1b; `agent-2-product.md` §2).
- `UNCONFIRMED` — `LlamaIndex` adapter (retrieval over staged docs; planned — `agent-3-contracts.json` `routing.llamaindex_constraint`); no `llama_index` module in `src/`.
- `CONTEXT ONLY` — Foreign-flow / broker / fundamental confirmation / corporate actions / industry/sub-industry taxonomy / alert service (`agent-2-product.md` §4 deferred list; `docs/ARCHITECTURE.md` §6 deferred enrichment).
- `DATA GAP` — SPA contradiction / invalidation records (`agent-1-runtime.md` §2; `agent-2-product.md` §2; `agent-2-product.md` §2 `Current vs target` — Streamlit renders them; React shows placeholder).
- `DATA GAP` — Background scheduler / concurrent writer (`docs/ARCHITECTURE.md` §4 threading & async; `docs/KNOWN_GAPS.md` low-priority; `agent-1-runtime.md` §9).
- `UNCONFIRMED` — `Sectors` live full-universe pagination (`tests/test_sectors_client.py` exists; live pagination unverified — `docs/SECTORS_MIGRATION_READINESS.md`).

---

## 9. Evidence and verification (offline, synthesis-level)

Source: `docs/ARCHITECTURE_DECISIONS.md` §8 (`Verification`); `docs/FEATURE_ARCHITECTURE.md` §7 (`Verification`); `docs/ARCHITECTURE_DECISIONS.md` §7 (`Files created / modified`); `docs/ARCHITECTURE_DECISIONS.md` §6 (`Explicit DATA GAP` list).

- **No live call performed during this sprint.** Confirmed by agent reports (`agent-1-runtime.md` §17; `agent-2-product.md` §1; `agent-3-data-control.md` §22) and this synthesis process (only `python3 -c` JSON validation; no `urllib`, `requests`, `yfinance.Ticker` execution; `tests/test_...` fixtures used only through `pytest` offline runs if needed — but this synthesis performs only offline file reads and JSON validation).
- **No `SECTORS_API_KEY` read or exported.** Confirmed by `grep -n` over agent reports (`agent-3-data-control.md` §22: `SECTORS_API_KEY` noted only as a gate key, never read or executed).
- **No source code edited.** Confirmed by `ls` before and after synthesis (only new files: `docs/ARCHITECTURE_DECISIONS.md`, `docs/ARCHITECTURE_BASELINE.md`, `docs/FEATURE_ARCHITECTURE.md`); `docs/ARCHITECTURE.md`, `docs/PRODUCT_ARCHITECTURE_PLAN.md`, `docs/DATA_CONTRACTS.md`, `docs/METHODOLOGY.md` unchanged; `docs/ARCHITECTURE_DECISIONS.md` references them as preserved evidence.
- **Agent artifacts preserved.** `docs/architecture/agent-1-runtime.md` (499 lines), `agent-1-runtime.json` (21 nodes, 31 edges, validated), `agent-2-product.md` (574 lines), `agent-2-feature-matrix.json` (14 feature rows, validated), `agent-3-data-control.md` (637 lines), `agent-3-contracts.json` (validated, contracts: `raw_response`, `document`, `claim` with `quantitative_use_default=false`, `evidence`, `snapshot`; routing; budget; cache; fail-closed) — all preserved as evidence source.
- **JSON contracts validated.** `python3 -c "import json; json.load(open('docs/architecture/agent-3-contracts.json'))"` passes; same for `agent-1-runtime.json`, `agent-2-feature-matrix.json`.
- **Concrete paths referenced throughout.** Every claim traces to `docs/ARCHITECTURE.md` (line references in `agent-1-runtime.md`), `src/idx_leadership/pipeline.py`, `tests/test_...`, `app/web/src/App.tsx`, `docs/DATA_CONTRACTS.md`, `docs/METHODOLOGY.md`, etc.

## 10. Reconciliation addendum (2026-09-13 full-stack pass)
- Canonical: 7 planes (A–G), 14 feature rows (8 MVP incl. Research-Evidence NEXT + Methodology, 5 deferred bundles), named promotion gates (no numeric gate count; agent-3 "8-gate" cell is docs-only).
- Diagram scopes: `docs/architecture/agent-1-runtime.json` (21 nodes/31 edges, full runtime) vs `docs/architecture.json` (8-component read-path view) — different scopes, not a conflict.
- Isolated harness `OUTPUT_ROOT` packs (agent-a/b/c) are validated evidence, not canonical; repo-local `agent-a-runtime/` is a separate stray artifact, untouched.
- Implementation deltas in this pass: PARTIAL→READY_WITH_GAPS rollup, per-file atomic + COMPLETE sentinel (tolerated, not enforced), valid empty parquet, UTC ledger timestamps, log-filter wiring, Tavily/You extract/crawl SSRF guards, Sectors explicit cross-section flag + deprecated-override warning, snapshot-id guards (library + export/enrich CLIs), Streamlit/React injection hardening, keyboard headers, copy/stale/illustrative fixes. Open: pagination values, 90-day cap, yfinance failure sets, search-lane allowlist, --out containment, lockfile, synthesis cap, contradiction/invalidation exporter gap, 0 new tests (pytest unavailable).

## 11. Continuation pass (2026-09-13, post-second-audit)
Closed: `complete` sentinel now reported by `SnapshotReader.load` (pre-sentinel bundles load with `complete=false`); pagination completeness + 90-day window-cap flag threaded from provider diagnostics into `coverage.json` (`pagination_incomplete`, `history_window_capped_90d` + note); yfinance per-ticker failed/empty sets exposed via `history_diagnostics` (feeds `_provider_acquisition_sets`, no longer swallowed); snapshot-id guards extended to export/enrich CLIs; `--out` outside web snapshots dir requires `--allow-outside-root`; Tavily/You extract/crawl SSRF guards + search caller-enforced scope documented; `RawCache.get` annotation fixed; Streamlit/React injection hardening; keyboard headers + aria-sort; stale explainer; contradiction/invalidation now exported (`evidence` payload key) → projected in `adapter.ts` → rendered in Group Explorer (placeholders only when absent); regression tests added (sentinel, traversal, pagination threading).
Verification: 534/534 pytest (530 + 4 new), `tsc --noEmit` clean, Vite production build clean, `py_compile` clean. 0 live calls.
Still open: multi-window Sectors history paging (flag documents instead), `--out` for other CLIs, lockfile, research-answer cap, scheduler/concurrent writers, browser QA (Chrome unavailable).

## 12. Closure-sprint status (2026-09-13, integration lead)
Three workstreams (backend / security / frontend) ran in isolated harness dirs (`closure-sprint/agent-{a-backend,b-security,c-frontend}`), integrated by the lead. No reset/clean/commit/push; user changes + untracked artifacts preserved.

Closed: Sectors multi-window paging (`_plan_windows`, per-window budget + isolation, `windows_*` diagnostics; cap flag now means partial failure only); `coverage_state` 6-way precedence (COMPLETE / PAGINATION_INCOMPLETE / WINDOW_CAPPED / combined / PARTIAL_SYMBOLS / PROVIDER_UNAVAILABLE); `complete` sentinel reported + forwarded by exporter (re-exported public snapshots carry 11+10 evidence rows; `complete=false` honestly marks pre-sentinel bundles); yfinance failed/empty sets end-to-end with 1 keyless live probe (BBCA.JK 5 rows, 0 credits) pinned as `tests/fixtures/yfinance_probe_bbca_2026-09-06_12.json` + replay test; all CLI `--out` paths contained (project root or tempdir else `--allow-outside-root`); `requirements.lock` (61 pins, sync-verified); writer threading + fcntl locks, torn-read tolerance, atomic ledger drain (fixes a proven flush-duplication race); research cap 1200 total incl. UNSOLICITED CONTEXT-ONLY banner end-to-end (client + enrich + display); SSRF numeric-IP refusal; paginate default cap 50; 1M-char payload caps; 4xx ledger entries; `replaceChildren()`; contradiction/invalidation rendered from export (placeholders only where absent).
Verification: 695/695 pytest (0 failures; remaining xfails are explicit gap markers), `tsc --noEmit` clean, Vite build clean, `py_compile` clean. Live: 1 yfinance call, 0 credits, 4 BLOCKED dry-runs; receipts secret-free. Browser: real headless-Chrome smoke, 8 screenshots, 0 console errors (agent-c-frontend/).
Release-gate matrix: 11/11 PASS (`closure-sprint/final-audit/GATES.json`). Remaining risks/deferred: Sectors/You/Tavily/Llama live behavior unverified (keys absent); multi-window success proven offline only; scheduler stays documented-single-writer; lockfile freeze-based (no hashes); on-disk bundles predate sentinel/coverage flags until rebuilt. No unsupported full-universe/YTD/benchmark/market-wide claim is exposed.
VERDICT: READY_WITH_GAPS.

## 13. Production-candidate pass (2026-09-13, principal-engineer pass)
Work log: `prod-pass/WORKLOG.md` (outside repo). All findings independently verified against the tree; prior reports treated as inputs (one overstatement caught: benchmark-diagnostics threading claimed but never landed — fixed forward).

Closed: suspension exclusion wired with explicit degraded states; within-tolerance window mixing disclosed (`max_observation_lag_days`, `tickers_lagging_gt2d`); dead leadership retry removed; forward_fill docstring corrected; signed-share semantics documented in model + methodology; Jakarta session classifier + `intraday_build` marking; COMPLETE sentinel moved pipeline-last (crash can no longer masquerade as finished); absolute-path leak purged from shipped exports (export-time sanitizer + filename-only audit); claim-permission matrix (`claim_gates.py`) + market-wide wording regression guard; golden hand-verified financial datasets; same-id race / torn-bundle / ledger-exactness / cache-corruption stress tests; live yfinance cross-check of snapshot returns (TLKM exact, BBCA 2e-6; absolute adjusted levels drift with vendor revisions while return ratios hold); BEI broker-summary path investigated (JS-driven, needs browser automation/auth — BLOCKED with reason); scheduler/lock semantics documented; `.python-version` pin (lockfile still freeze-based, sync-verified); new Methodology acquisition rows (suspension/session/alignment); 4 headless-Chrome smoke screenshots, 0 console errors.
Verification: 715/715 pytest, `tsc --noEmit` clean, Vite build clean. Live: 3 yfinance calls total (1 prior probe + 2 cross-check), 0 credits; keyed providers remain UNVERIFIED_LIVE (keys absent, 0 calls).
Remaining boundaries: keyed-provider live behavior; Sectors multi-window proven offline only; single-writer scheduler by design; old bundles predate new flags until rebuilt; freeze-based lockfile (no hashes); per-ticker foreign flow DATA GAP (IDX path needs automation/auth); market-wide/YTD claims stay gated.
VERDICT: READY_WITH_EXPLICIT_BOUNDARIES (offline development, demonstration, continued integration; not approved for authoritative market-wide claims).
