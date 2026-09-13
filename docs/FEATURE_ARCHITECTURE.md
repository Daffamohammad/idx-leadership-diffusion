# FEATURE_ARCHITECTURE.md — Canonical Feature Boundary

**Status:** Product architecture synthesis for IDX Leadership Diffusion. Based on Agent 2 (`docs/architecture/agent-2-product.md`, `docs/architecture/agent-2-feature-matrix.json`) and cross-validated with Agent 1 (`docs/architecture/agent-1-runtime.md`) and Agent 3 (`docs/architecture/agent-3-data-control.md`).

**No live provider calls.** No `SECTORS_API_KEY` used. No `yfinance`, `You.com`, `Tavily`, `LlamaParse` live execution. All feature claims trace to repository files (`docs/`, `src/`, `app/`, `tests/`, `config/`).

**Date:** 2026-09-13.

---

## 1. Canonical feature hierarchy (resolved from all agents)

There is exactly **one canonical feature hierarchy**. It separates quantitative core (snapshot-backed, deterministic) from trust/audit core (always visible) from research context layer (sidecar-backed, never signal-forming) from deferred enrichment (requires source-specific contract + parity proof).

Source evidence: `docs/ARCHITECTURE.md` §2-3; `docs/PRODUCT_ARCHITECTURE_PLAN.md` §6; `docs/architecture/agent-2-product.md` §4 (`Feature hierarchy`); `docs/architecture/agent-2-feature-matrix.json` (14 feature rows with `acceptance`, `badges`, `data_contracts`, `modules`, `ui_routes`).

```text
IDX Leadership Diffusion (market-wide intelligence workspace)
├── 1. QUANTITATIVE CORE (MVP — snapshot-backed, deterministic, provider-independent)
│   ├── 1.1 Market Overview       («overview» / Streamlit Overview)
│   ├── 1.2 Leadership Map        («map» / Streamlit Leadership Map)
│   ├── 1.3 Diffusion & Breadth   («map» readiness / Overview + Map)
│   ├── 1.4 Concentration         («explorer», «groups» / tape + group detail)
│   ├── 1.5 Group / Sector Explorer («explorer», «groups» / Streamlit Group Explorer)
│   ├── 1.6 Ticker Analysis       («ticker/:ticker» / constituent table)
│   └── 1.7 What Changed          («what-changed» / shifts + contradictions + tape)
│
├── 2. TRUST & AUDIT CORE (MVP — always visible on every snapshot surface)
│   └── 2.1 Methodology & Data Quality («methodology» / Streamlit Methodology / Quality)
│
├── 3. RESEARCH CONTEXT LAYER (NEXT — sidecar-backed, never signal-forming)
│   ├── 3.1 Research Evidence     («overview» release/sample/events; «methodology» context grids;
│   │                           «explorer» confirmation grid / Streamlit gap rollup)
│   └── 3.2 Konglo / Themes static lenses («maps/konglo», «maps/themes», «themes» / NEXT)
│
└── 4. DEFERRED ENRICHMENT (requires source-specific contract + parity/coverage proof)
    ├── 4.1 Free-float / cap-weighted aggregation
    ├── 4.2 Per-ticker foreign-flow / broker-activity
    ├── 4.3 Fundamentals periodized + corporate actions
    ├── 4.4 Industry / sub-industry taxonomy drill-down
    ├── 4.5 Alert / scheduled-refresh service
    └── 4.6 Forward-return diagnostics
```

**Non-features (explicitly out of scope, never to be introduced by this architecture):**
- Chatbot / conversational assistant (`docs/ARCHITECTURE.md` §5).
- Stock-recommendation engine (no "buy/sell" outputs; `docs/KNOWN_GAPS.md`).
- Broker terminal (no order entry / execution / real-time trading).
- Portfolio optimizer / position-sizing engine.
- Macro dashboard (benchmark = IHSG only; no rates / FX / commodities / cross-country).
- Alerting / scheduled-refresh service (`docs/KNOWN_GAPS.md` low-priority gap).
- Forward-return prediction / backtest-performance marketing (`docs/ARCHITECTURE.md` §5).

---

## 2. Feature-to-module / UI mapping (canonical, evidence-backed)

Source: `docs/architecture/agent-2-product.md` §6 (`Feature-to-module / UI mapping`); `docs/architecture/agent-2-feature-matrix.json` (`modules`, `ui_routes`); `docs/ARCHITECTURE.md` §1 (layer responsibilities); `docs/DATA_CONTRACTS.md`.

| Feature | Phase | Backend modules | Snapshot / view-model reader | React route(s) | Streamlit tab | Data contracts (read only) | Writes |
|---|---|---|---|---|---|---|---|
| **Market Overview** | MVP | `pipeline.py`, `aggregation/groups.py` | `data_sources.py`, `view_models.build_dashboard_view` | `/overview`, `/what-changed` (hero) | Overview | `MF`, `QL`, `CV`, `GS`, `BR` (Market Read) | **None** (read-only) |
| **Leadership Map** | MVP | `signals/leadership.py`, `features/returns.py`, `relative_strength.py` | `app/web/src/data/adapter.ts`, `rotation.ts`, `mapGeometry.ts` | `/map` (`RotationView`) | Leadership Map | `SF` (excess 5/20/60d), `GS` (leadership_state, rank), `BO` | **None** |
| **Diffusion & Breadth** | MVP | `signals/diffusion.py`, `diffusion_v2.py`, `features/breadth.py` | `app/web/src/data/readiness.ts`, `adapter.ts` | `/map`, `/methodology` (readiness) | Overview + Map | `GS` (breadth_*), `diffusion_state_v2`, `CMP`, `QL` | **None** |
| **Concentration** | MVP | `features/concentration.py`, `concentration_v2.py` | `view_models._concentration_label`, `adapter.ts` | `/explorer`, `/what-changed` (tape) | Overview tape + Group Explorer | `GS` (nested `ConcentrationMetrics`: `absolute_move_v2`, HHI, signed share, top-1/3/5), `SF` (constituent returns) | **None** |
| **Group / Sector Explorer** | MVP | `evidence/builder.py`, `taxonomy/*` (`registry.py`, `models.py`, `aggregation.py`) | `snapshot_adapter.row_to_group_snapshot`, `view_models.GroupView` | `/explorer`, `/groups`, `/maps/konglo`, `/maps/themes`, `/themes` | Group Explorer | `GS`, `SF` + `SM` (constituent join), `EV`, `QL` / `CV` (denominators) | **None** |
| **Ticker Analysis** | MVP | `models/security_master.py`, `price_observation.py` | `adapter.ts` (`featureLookup`, `securityLookup`, `tickerPriceHistory`) | `/ticker/:ticker` | (constituent tables inside Group Explorer) | `SM`, `PO`, `SF` (ticker row), `BO`, `R-SIDE` (events / foreign-flow sample) | **None** |
| **What Changed** | MVP | `signals/transitions.py`, `change_digest.py` | `adapter.ts` (`materialChanges`, `breadthHistory`, `dataSources.trajectory`) | `/what-changed` | Overview (shifts + contradictions + tape) | `TE`, `CMP` (comparable prior), `GS` (current + previous), `change_digest.json` | **None** |
| **Methodology & Data Quality** | MVP | `data/quality.py`, `manifests.py`, `analytics/data_gaps.py` | `view_models.data_gap_rollup`, `quality_layers` | `/methodology` | Methodology / Quality | `MF`, `config/methodology.yaml` (`methodology-v3`), `QL`, `CV`, `DW` (data warnings), `EV.data_gaps`, `CMP` | **None** |
| **Research Evidence** | NEXT | `providers/you_client.py`, `tavily_client.py`, `llama_parse.py`, `idx_statistics.py`, `idx_discovery.py` (target: `research/` orchestrator) | `researchContext.ts`, `SnapshotProvider` (optional IDX loads) | `/overview` (release / sample / events sections), `/methodology` (context grids), `/explorer` (confirmation grid) | Sidebar gap rollup + brief Data Gaps | `R-SIDE` (today) → `R-DOC` + `R-CLAIM` (target); `EV.data_gaps`; IDX release tables (official release cards) | **Sidecar only** (never snapshot core) |
| **Konglo / Themes lenses** | NEXT (static lens only) | `taxonomy/*` (`aggregation.py`, `registry.py`) | `adapter.ts` (taxonomy lens), `mapLabels.ts` | `/maps/konglo`, `/maps/themes`, `/themes` | Group Explorer (taxonomy filter) | `GS` (reuses current snapshot); membership analyst-defined, badged `PROTOTYPE` | **None** |
| **Deferred enrichment** | DEFERRED | Source-specific contracts required; no module assigned | N/A | N/A | N/A | Each needs its own `SM`/`PO`/`SF`/`EV` contract + parity test | **None** |

**Critical rules (binding on all feature implementations):**

- **No feature writes to snapshot core except the offline pipeline (`pipeline.build_snapshot`).** (`docs/ARCHITECTURE.md` §4; `docs/architecture/agent-2-product.md` §5; `docs/architecture/agent-1-runtime.md` §5).
- **No UI performs any provider import, credential read, network call, or `allow_live` flag check.** (`app/streamlit_app.py` docstring; `app/data_sources.py` docstring; `tests/test_ui_productization.py`)
- **Every surface shows `provider_mode` badge (`SECTORS LIVE`, `SECTORS FIXTURE`, `DEMO FIXTURE`, `PUBLIC PROTOTYPE`) with conservative hint (`_safe_mode_hint`: provider name alone never proves a live call).** (`app/streamlit_app.py` `_provider_pill`; `app/web/src/components/AppShell.tsx`)
- **Every feature page shows evidence/status badges:** `SNAPSHOT`, `OFFICIAL_RELEASE`, `SAMPLE`, `PROTOTYPE`, `CONTEXT`. (`app/web/src/components/EvidenceModel.tsx`; `docs/HYBRID_PRODUCT_MODEL.md` §6 lanes)
- **Every missing/unsupported state is labeled explicitly:** `READY`, `READY_WITH_GAPS`, `PARTIAL`, `STALE`, `FAILED`, `DATA_GAP`, `UNAVAILABLE`, `UNCONFIRMED`. (`app/web/src/components/StatusChips.tsx`; `docs/ARCHITECTURE.md` §4 design principle 1)

---

## 3. Feature states (empty / loading / stale / partial / data-gap)

Source: `docs/architecture/agent-2-product.md` §2 (current vs target); `docs/ARCHITECTURE.md` §5; `docs/DATA_CONTRACTS.md`; `tests/test_ui_story_mode.py`, `tests/test_e2e_demo.py`.

Every feature must handle the following states deterministically (no silent fallback to neutral numbers):

| State pattern | What it means | Required UI behavior | Evidence source |
|---|---|---|---|
| **Loading** (`"Loading snapshot…"`) | Snapshot file missing or index mismatch | Show spinner; no number placeholder; no fabricated previous state | `SnapshotProvider.tsx` (`loading` state); `streamlit_app.py` (`_cached_view`) |
| **Empty / Not comparable** (`"NO COMPARABLE HISTORY"` / `INCOMPARABLE`) | Comparable history (`_load_compatible_history`) rejected due to future-dated snapshot, contract mismatch (`snap_as_of >= current`), or missing previous manifest | Suppress fabricated previous states and material-shift claims; show empty-state card with `EmptyState` component | `adapter.ts` (`normalizeDataStatus` maps unknown → `UNAVAILABLE`); `tests/test_comparability_and_adapter.py` |
| **Partial / `READY_WITH_GAPS`** | Data exists but gaps remain (e.g., diffusion classification missing due to no comparable prior; foreign-flow sample partial) | Show numbers with `READY_WITH_GAPS` chip; enumerate causes explicitly (`buildDiffusionReadiness` in `readiness.ts`) | `StatusChips.tsx`; `readiness.ts`; `view_models.py` (`data_gap_rollup`) |
| **Data Gap (`DATA_GAP` / `UNAVAILABLE`)** | Required data missing for feature calculation (e.g., fundamental confirmation not available; Sectors live not connected; no eligible denominator) | Show `DATA_GAP` or `UNAVAILABLE` label; no imputation; no neutral value (0 or neutral never substituted) | `analytics/data_gaps.py` (`build_data_gaps`); `intelligence/contract.py` (7 frozen gap categories); `models/enums.py` (`DataGapStatus`) |
| **Stale (`STALE`)** | Price/history data older than `as_of_tolerance_days`; benchmark or security observation stale | Show `STALE` chip; never suppress; never recalculate with stale input | `data/quality.py` (`STALE` assessment); `analytics/persistence.py` |
| **Failed (`FAILED`)** | Provider error / acquisition failure; no fallback to other provider | Show `FAILED` chip; do not fall back silently to `fixture` or `public`; `factory.py` raises on mode conflict | `tests/test_429_blocked_path.py`; `provider/factory.py` (`build_provider_from_config` raises on conflict) |
| **Contradiction / Invalidation** | Deterministic contradiction rules triggered (`analytics/contradictions.py`) or screen-invalidation conditions met (`analytics/invalidation.py`) | Show contradiction/invalidation block (Streamlit) or placeholder (React — `agent-1-runtime.md` §2 gap); never suppress for presentation | `evidence/builder.py` (`build_group_evidence` emits contradiction rows + invalidation); `tests/test_brief_contract.py` |

---

## 4. Acceptance criteria per core feature (canonical)

Source: `docs/architecture/agent-2-product.md` §5 (acceptance criteria embedded per feature); `docs/architecture/agent-2-feature-matrix.json` (each feature row has `acceptance` array).

### 4.1 MVP quantitative core

**Market Overview**
- [x] Header shows `as_of`, `provider_mode`, snapshot id, `SNAPSHOT` badge (`EvidenceBadge`).
- [x] Heatmap renders persisted groups only (`available_sources` reads `snapshots/index.json`); eligible/total coverage shown.
- [x] Official release (`OFFICIAL_RELEASE`), foreign-flow sample (`SAMPLE`), research events (`CONTEXT`) each carry their own lane badge.
- [x] Empty snapshot renders recovery command with no fallback numbers (`EmptyState`).
- [x] Methodology & Data Quality visible at bottom; `provider_mode` pill visible.

**Leadership Map**
- [x] Cross-sectional `RotationView` (`mapGeometry.ts`, `mapLabels.ts`) renders only groups with `RS` state not `UNCONFIRMED`.
- [x] `provider_mode` pill + snapshot error state (`RouteErrorElement` in `App.tsx`) visible.
- [x] No recommendation label (`docs/ARCHITECTURE.md` non-goals).

**Diffusion & Breadth**
- [x] Diffusion state (`STABLE` / `BROADENING` / `NARROWING` / `FIRM` / `FRAGILE`) rendered with `READY_WITH_GAPS` or `DATA_GAP` explanation.
- [x] Readiness explainer (`readiness.ts`) shows enumerated causes (no comparable prior = `DATA_GAP`).
- [x] No shared score with Leadership or Concentration (`docs/ARCHITECTURE.md` dimension separation).

**Concentration**
- [x] `absolute_move_v2` (top-1/3/5 capped at 1.0) + signed share + HHI shown separately (not merged into single score).
- [x] `UNCONFIRMED` default preserved (unknown enum → `UNCONFIRMED` in `snapshot_adapter.py`).

**Group / Sector Explorer**
- [x] Taxonomy lens (`Sector` / `Industry`) shows disabled explanation when Industry absent (`AppShell.tsx` taxonomy toggle).
- [x] Constituent table (`constituent_table` in `adapter.ts`) shows `excess_5d`, `excess_20d`, `excess_60d` with `SNAPSHOT` provenance.
- [x] Evidence contract (`EV`) visible: contradictions + invalidation + data gap rollup.

**Ticker Analysis**
- [x] `PriceChart` (`PriceChart.tsx`) declared source of truth; `TradingViewWidget` declared `CONTEXT ONLY` with blocked/unavailable fallback.
- [x] `TickerAnalysis` page (`TickerAnalysis.tsx`) shows `EvidenceBadge` `SNAPSHOT` in header.
- [x] Research events (`CONTEXT ONLY`) and foreign-flow sample (`SAMPLE`) shown but never promoted.

**What Changed**
- [x] `MaterialShiftView` (`adapter.ts`) shows `hasComparable` branching: `"What changed"` vs `"Current snapshot"` titles.
- [x] Empty state cards (`EmptyState.tsx`) for `NO TIME SERIES`, `NO CONSTITUENTS`, `NO FOREIGN FLOW`.
- [x] `MiniMap`, `ShiftFeed`, leadership tape, under-the-surface grid present with `SNAPSHOT` / `CONTEXT` badges.

**Methodology & Data Quality**
- [x] Evidence model (`EvidenceModel.tsx`) shows 5 lanes (`SNAPSHOT`, `OFFICIAL_RELEASE`, `SAMPLE`, `PROTOTYPE`, `CONTEXT`) with descriptions.
- [x] `StatusChips` (`StatusChips.tsx`) shows `READY` / `READY_WITH_GAPS` / `PARTIAL` / `STALE` / `FAILED` / `DATA_GAP` / `UNAVAILABLE`.
- [x] Methodology definitions (`docs/METHODOLOGY.md` `methodology-v3`), analytical definitions, provenance, evidence matrix (10 layers × status/source/coverage/quantitative/signal-eligible).
- [x] `Universe Coverage` (`CV`) and `Live Warnings` visible; `provider_mode` pill visible.

### 4.2 NEXT / deferred

**Research Evidence** (NEXT — not implemented as promotion-capable)
- [x] Context display exists (`ResearchEvidencePanel` in `GroupExplorer.tsx`; `researchContext.ts` normalizes with `quantitative_use: false`).
- [ ] Typed claim envelope (`R-CLAIM`) not implemented (`agent-2-product.md` §2; `agent-3-contracts.json`).
- [ ] Generic parser adapter (`B3`) not fully implemented (`llama_parse.py` exists; broader adapter target-state only; `agent-1-runtime.md` §1b).
- [ ] Promotion gate (Phase F / G) not implemented (`agent-3-data-control.md` §15 Phase F/G).
- [ ] Sidecar (`tavily_context.json`, `you_context.json`, `research_events`) exists; never feeds feature engine.

**Konglo / Themes** (NEXT — static lens only)
- [x] Taxonomy membership defined (`taxonomy/registry.py`, `taxon` registry); `taxonomy/aggregation.py` aggregates by lens.
- [x] Route exists (`/maps/konglo`, `/maps/themes`, `/themes`); `TaxonomyMapPage` (`TaxonomyMapPage.tsx`) renders.
- [x] Membership analyst-defined; badged `PROTOTYPE` (`AppShell.tsx` taxonomy toggle explanation for `Industry` disabled).

**Deferred enrichment** (DEFERRED — no feature surface allocated)
- No module assigned; no route; no acceptance criteria. Each requires its own contract (`SM`/`PO`/`SF`/`EV`) + parity test (`docs/ARCHITECTURE.md` §6 deferred; `agent-2-product.md` §4 deferred list).

---

## 5. Boundary between quantitative output and research context (canonical, binding)

Source: `docs/ARCHITECTURE.md` §2 (layer separation); `docs/ARCHITECTURE.md` §3 (`Key invariant`); `docs/ARCHITECTURE.md` §5 (allowed / forbidden dependency directions); `docs/PRODUCT_ARCHITECTURE_PLAN.md` §4 (`Primary / Secondary / Forbidden`); `docs/architecture/agent-1-runtime.md` §5 (`Forbidden dependencies`); `docs/architecture/agent-3-data-control.md` §7 (`Routing lanes`); `docs/architecture/agent-2-product.md` §2 (`Target state`)

### 5.1 Quantitative plane rules

- **Allowed inputs:** Canonical price observations (`PO`), benchmark observations (`BO`), security master (`SM`), security features (`SF`), group snapshots (`GS`), transition events (`TE`), manifest (`MF`), quality (`QL`), coverage (`CV`).
- **Allowed providers (market-data):** `YFinanceProvider` (`public.py`), `SectorsProvider` (`sectors*.py`) — only after `allow_live` + auth + budget reserve + full-universe pagination + price-basis verification + taxonomy parity + credit economics (`agent-3-data-control.md` §15 Phase D / E); `FixtureProvider` (`fixture.py`) for regression.
- **Forbidden inputs:** Any web-context text (`tavily_context.json`, `you_context.json`, `research_events`, parsed PDF content, official release text) — unless it has passed the typed-claim promotion gate (`quantitative_use=true`, exact entity, period, unit, denominator, reconciliation verified) (`agent-3-data-control.md` §14). No exception.
- **Forbidden dependency:** `features|aggregation|signals|analytics|evidence|intelligence` → `providers.you_client|tavily_client|llama_parse` or any network module (`agent-1-runtime.md` §5 forbidden list item 1 and 2).

### 5.2 Research plane rules

- **Allowed sources:** `YouClient` (`you_client.py`, `search_context`); `TavilyClient` (`tavily_client.py`, `search`/`extract`/`crawl` bounded); `LlamaParse` adapter (`llama_parse.py`, `normalize_daily_statistics_markdown`, bounded `target_pages`, dual upload/spend gates).
- **Allowed outputs:** `tavily_context.json` (`WEB_CONTEXT`, `quantitative_use=false`); `you_context.json` (`WEB_CONTEXT`, `quantitative_use=false`); `research_events` sidecars; `idx_daily_statistics` market-level cards (`quantitative_use=true` allowed **only** for `DAILY_STATISTICS_TARGET_METRICS` after full reconciliation — `agent-1-runtime.md` §7; `agent-3-data-control.md` §7).
- **Allowed promotion (only through B3 IDX-official reducer):** `LlamaParse` adapter emits validated `DAILY_STATISTICS_TARGET_METRICS` payload (`IHSG close`, `net foreign Today/YTD` with `units` and `period_start/end`, `market PER/PBV` with reconciliation) — this is market-level context only, never per-group or per-ticker metric input. Full parse kept as audit sidecar (`agent-1-runtime.md` §7; `agent-3-data-control.md` §7).
- **Forbidden promotion:** Any research claim that does not pass all 8 promotion conditions (entity, period, unit, denominator, provenance, completeness, reconciliation, schema version bump) stays `CONTEXT ONLY`, `DATA_GAP`, or `UNCONFIRMED`.

### 5.3 UI boundary enforcement

- **React (`AppShell.tsx`):** Provider-mode pill (`SECTORS LIVE` / `SECTORS FIXTURE` / `DEMO FIXTURE` / `PUBLIC PROTOTYPE`); quality-status dot (`READY` / `READY_WITH_GAPS` / `STALE` / etc.); taxonomy toggle disabled with explanation; snapshot-error and snapshot-loading states (`RouteErrorElement`); `EvidenceBadge` kinds fixed (`SNAPSHOT`, `OFFICIAL_RELEASE`, `SAMPLE`, `PROTOTYPE`, `CONTEXT`).
- **Streamlit (`streamlit_app.py`):** Same badges + `DEMO FIXTURE` warning banner; contradiction block; screen-invalidation block; per-layer status grid; frozen-category data-gap rollup; brief download (`render_market_brief` frozen `BRIEF_SECTIONS`).

---

## 6. Phased feature rollout (canonical)

Source: `docs/ARCHITECTURE_DECISIONS.md` §5 (phased table); `docs/ARCHITECTURE.md` §8; `docs/PRODUCT_ARCHITECTURE_PLAN.md` §8 (Phase gates A–F); `docs/architecture/agent-3-data-control.md` §15.

| Phase | Feature set delivered | Evidence required | Gate condition | Status |
|---|---|---|---|---|
| **A** (Freeze) | Architecture + feature boundary frozen; all core features defined; no new provider surface. | `docs/ARCHITECTURE.md`; agent artifacts (this synthesis); `docs/ARCHITECTURE_DECISIONS.md`. | All features have input, output, provenance, status-data contract. | **Done** |
| **B** (Offline contracts) | Promotion-gate tests; `You`/`Tavily` fixtures; `LlamaParse` fixtures; entity-resolution fixtures. | `tests/test_research_context.py` (exists); `tests/test_llama_parse.py` (exists); additional fixtures needed (`agent-3-data-control.md` §15). | `quantitative_use=false` tested; parser/reducer tested without network. | **Partial** |
| **C** (Fixture parity) | Full `FixtureProvider` regression path; `SectorsFixture` parity for all quantitative core. | `tests/test_parity_public_sectors.py` (exists); `tests/test_comparability_and_adapter.py` (exists); `tests/test_pipeline.py` (exists). | Feature engine provider-independent verified. | **In progress** |
| **D** (Bounded live pilot — explicit approval only) | Single-date, single-provider (`Sectors` live or `You`/`Tavily` bounded) with full manifest. | `tests/test_live_preflight.py` (exists); `tests/test_429_blocked_path.py` (exists); `tests/test_provider_modes_and_readiness.py` (exists). | Request count, actual cost (if observable), response shape, provenance, coverage reconciled; `DATA GAP` labeled explicitly. | **Not started** (requires approval) |
| **E** (Quantitative core parity) | `yfinance` replay regression; `Sectors` live only after full verification. | `tests/test_provider_contracts.py` (exists); `tests/test_parity_public_sectors.py` (exists); `tests/test_e2e_demo.py` (exists). | Snapshot rebuildable from manifest; `provider_mode` visible in UI. | **Not started** (Sectors live unverified) |
| **F** (Research ingestion — NEXT) | General parser adapter; typed claim (`R-CLAIM`); promotion gate (`agent-3-data-control.md` §14). | `llama_parse.py` adapter exists; typed claim envelope (`agent-3-contracts.json`) not implemented; promotion gate not implemented. | Every excerpt traceable to URL, hash, page/section, `retrieved_at`, parser version, quality status. | **Target-state only** |
| **G** (Promotion to confirmation) | Only fully-gated claims considered for confirmation input; new schema/methodology version required. | Not applicable (depends on Phase F). | Regression tests pass; `ConfirmationEvidence` fields populated only through gate. | **Not started** |

---

## 7. Verification (offline, no source modification)

- No `SECTORS_API_KEY` read, exported, or used (`agent-3-data-control.md` §22; `agent-1-runtime.md` §17; `agent-2-product.md` §1).
- No source file edited (`docs/ARCHITECTURE.md`, `docs/ARCHITECTURE_DECISIONS.md`, `docs/FEATURE_ARCHITECTURE.md` are the only new files; `docs/ARCHITECTURE_BASELINE.md` also new — see separate synthesis file).
- JSON contracts validated (`python3 -m json.tool`): `docs/architecture/agent-3-contracts.json`, `docs/architecture/agent-1-runtime.json`, `docs/architecture/agent-2-feature-matrix.json`.
- All evidence claims reference concrete repository paths (`docs/ARCHITECTURE.md`, `docs/PRODUCT_ARCHITECTURE_PLAN.md`, `docs/DATA_CONTRACTS.md`, `docs/METHODOLOGY.md`, `docs/KNOWN_GAPS.md`, `docs/HYBRID_PRODUCT_MODEL.md`, `docs/ARCHITECTURE.md` §4, `docs/SECTORS_BLOCKERS.md`, `docs/SECTORS_MIGRATION_READINESS.md`, `docs/SECTORS_CREDIT_AUDIT.md`, `src/idx_leadership/pipeline.py`, `tests/test_...`, `app/web/src/App.tsx`, etc.).

## 8. Reconciliation addendum (2026-09-13)
14 rows = 9 core (8 MVP + Research Evidence NEXT) + 5 deferred bundles; do not split bundles when counting. 12 routes cover all 9 core features; deferred rows correctly have no routes.
