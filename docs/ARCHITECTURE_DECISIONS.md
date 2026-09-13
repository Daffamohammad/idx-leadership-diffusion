# ARCHITECTURE_DECISIONS.md — IDX Leadership Diffusion

**Status:** Synthesis of Agent 1 (runtime), Agent 2 (product), Agent 3 (data/control). No live Sectors API, no `SECTORS_API_KEY` use, no network calls performed. All claims trace to repository files read locally (`docs/`, `src/`, `app/`, `tests/`, `config/`, `data/`).

**Date:** 2026-09-13. **Repo:** `/Users/daffa/Hackathon/idx-leadership-diffusion`.

**Guardrails preserved:**
- Four dimensions remain separate: Leadership, Diffusion, Concentration, Confirmation (`docs/ARCHITECTURE.md`, `docs/METHODOLOGY.md`, `docs/PRODUCT_ARCHITECTURE_PLAN.md`).
- `quantitative_use=false` is the default for every research claim (`docs/architecture/agent-3-data-control.md` §14; `docs/architecture/agent-3-contracts.json` contracts.claim).
- No chatbot, recommender, broker terminal, portfolio optimizer, macro dashboard, or unrelated feature expansion (`docs/KNOWN_GAPS.md`, `docs/ARCHITECTURE.md`).
- Missing or unsupported data remains explicitly marked `DATA GAP`, `UNCONFIRMED`, or `CONTEXT ONLY`.
- You.com, Tavily, LlamaIndex, LlamaParse, yfinance are not evidence of a completed live integration.

---

## 1. Canonical architecture (resolved from all three agents)

The repository implements (and targets) a **seven-plane, single-process, synchronous, file-based architecture** (`docs/ARCHITECTURE.md` §2; `docs/architecture/agent-1-runtime.md` §3; `docs/architecture/agent-2-product.md` §2). Planes are separated by dependency direction and data-flow firewalls.

```
PLANE A — QUANTITATIVE MARKET-DATA (provider-independent core)
  A1 Providers        → A2 Normalize   → A3 Canonical Models  → A4 Features
  (yfinance / Sectors / Fixture)  (canonical columns, units) (Pydantic schemas)
  Source evidence: `src/idx_leadership/providers/*.py`, `pipeline.py`

PLANE B — RESEARCH DISCOVERY / DOCUMENT INGESTION (never writes features)
  B1 Discovery (You.com) → B2 Retrieval (Tavily, bounded) → B3 Doc Adapter (LlamaParse, planned)
  Source evidence: `providers/you_client.py`, `tavily_client.py`, `llama_parse.py`

PLANE C — DETERMINISTIC ANALYTICS (pure, provider-independent)
  C1 Aggregation (groups, rank)  C2 Signals: Leadership | Diffusion | Concentration
  C3 Transitions + change digest   C4 Persistence / sensitivity / turnover
  Source evidence: `aggregation/groups.py`, `signals/*.py`, `analytics/*.py`

PLANE D — EVIDENCE / PROVENANCE (sidecars, never snapshot-core mutations)
  D1 Evidence Builder (`evidence/builder.py`) → D2 Frozen contracts (`intelligence/contract.py`)
  Source evidence: `evidence/builder.py`, `models/evidence.py`, `docs/DATA_CONTRACTS.md`

PLANE E — SNAPSHOT GENERATION (atomic, versioned, replayable)
  E1 Orchestrator (`pipeline.py`) → E2 Snapshot Store (`data/snapshots/*.json`, parquet+csv, manifest)
  Source evidence: `data/snapshots.py`, `pipeline.py`, `scripts/build_snapshot.py`

PLANE F — READ-ONLY PRODUCT SURFACES (no provider import, no network, no credential read)
  F1 Streamlit (`app/streamlit_app.py`)  F2 React SPA (`app/web/src/`)
  Source evidence: `app/streamlit_app.py`, `app/web/src/App.tsx`, `data_sources.py`, `view_models.py`

PLANE G — CACHE / LEDGER / BUDGET / FAIL-CLOSED (wraps every provider touchpoint)
  G1 RawCache (`RawCache`, TTL)  G2 RequestLedger (`providers/ledger.py`, append-only)
  G3 Budget / Preflight (`factory.py`, `test_live_preflight.py`)  G4 Fail-closed gates
  Source evidence: `providers/ledger.py`, `providers/factory.py`, `data/__init__.py`, `tests/test_429_blocked_path.py`
```

**Key invariant (load-bearing):** The only permitted path from Plane B into quantitative state is the B3 IDX-official reducer (`llama_parse.py`) emitting a **validated market-level payload** (`quantitative_use=true`, scope `DAILY_STATISTICS_TARGET_METRICS`) — and even that payload is market-level context (IHSG close, net foreign Today/YTD, market PER/PBV), never a per-group leadership/diffusion/concentration input (`docs/PRODUCT_ARCHITECTURE_PLAN.md` §4; `docs/architecture/agent-3-data-control.md` §7; `docs/architecture/agent-1-runtime.md` §6).

---

## 2. Conflict resolution (agent disagreements resolved)

| Topic | Agent 1 (runtime) | Agent 2 (product) | Agent 3 (data/control) | Resolution |
|---|---|---|---|---|
| **Dimension separation** | Four dimensions independent; no shared score (`agent-1-runtime.md` §1c) | Confirmed in feature hierarchy (Leadership / Diffusion / Concentration / Confirmation separate) (`agent-2-product.md` §4) | `quantitative_use=false` default; promotion gate requires exact entity + period + unit + denominator (`agent-3-data-control.md` §14) | **Preserved.** Confirmation stays empty by construction (`evidence/builder.py`). No promotion without full gate. |
| **Sectors role** | Live HTTP opt-in; fixture replay exists; live-only after `allow_live` + key + credit ceiling (`agent-1-runtime.md` §1b) | Not a feature change; market-wide source intended (`agent-2-product.md` §3) | `sectors_live` primary for quantitative only after auth, coverage, price basis, parity, credit economics verified (`agent-3-data-control.md` §8) | **Resolved:** `SECTORS_LIVE` remains target but is **not** claimed complete. All quantitative outputs must declare `provider_mode` (`PUBLIC_PROTOTYPE` / `SECTORS_FIXTURE` / `SECTORS_LIVE` / `DEMO_FIXTURE`) explicitly (`docs/ARCHITECTURE.md` §4). |
| **Research evidence promotion** | B3 reducer only; full parse kept as audit sidecar (`agent-1-runtime.md` §7) | Research Evidence is NEXT; typed claim + promotion gate not implemented (`agent-2-product.md` §4) | `quantitative_use=false` by default; only exact-match + reconciliation + schema version bump promotes (`agent-3-data-control.md` §14) | **Resolved:** Research Evidence stays **NEXT-phase**. Sidecar files (`tavily_context.json`, `you_context.json`, `research_events`) exist but never feed feature engine. |
| **Snapshot write authority** | Atomic `tmp + rename`; per-file; manifest + version (`agent-1-runtime.md` §3, §6) | Read-only surfaces only; no UI writes (`agent-2-product.md` §6) | Snapshot contract carries `provider_mode`, `as_of`, `method_version` (`agent-3-contracts.json`) | **Preserved.** Only `pipeline.build_snapshot()` writes; UIs read persisted artifacts only. |
| **Cache / ledger unification** | Per-provider (`provider/*.py`) with separate roots (`agent-1-runtime.md` §4) | Not feature-specific | Cross-provider contract is target-state (`agent-3-data-control.md` §20) | **Resolved:** Partial implementation acknowledged (`test_live_preflight.py`, `test_429_blocked_path.py`). Unified cross-provider budget contract remains **UNCONFIRMED / DATA GAP**. |
| **React vs Streamlit asymmetry** | Streamlit renders contradiction + invalidation + confirmation; React shows placeholder (`agent-1-runtime.md` §2, §6) | Confirmed (`agent-2-product.md` §2); SPA `GroupExplorer` shows "NO CONTRADICTION RECORDS / invalidation not emitted" | Not a data-contract issue | **Preserved as gap.** Web snapshot export (`scripts/export_snapshot_json.py`) does not yet emit contradiction/invalidation records. Not a feature regression, but a known surface gap. |

---

## 3. Provider responsibility matrix (canonical)

Source: `docs/ARCHITECTURE.md` §1; `docs/PRODUCT_ARCHITECTURE_PLAN.md` §4; `docs/architecture/agent-3-data-control.md` §7; `docs/architecture/agent-1-runtime.md` §1b.

| Work | Primary | Secondary / Fallback | Forbidden behavior |
|---|---|---|---|
| Daily price + benchmark | `sectors_live` (post-auth/parity only) | `yfinance` (replayable support); `fixture` (offline regression) | Never use search result text as a price value |
| Discovery (broad recall) | `You.com` (`search_context`) | `Tavily` (selective cross-check) | Never run both providers for the same query by default |
| Targeted search / crawl | `Tavily` (`search`/`extract`/`crawl`, bounded depth ≤5, breadth ≤20, external off by default) | `You` contents (if needed) | Crawl without explicit limit; never inject crawl output into metrics |
| Official IDX PDF parsing | `LlamaParse` adapter (`run_llama_parse`, bounded pages, dual upload/spend gates) | Fixture/offline parser for regression | Send full document without page budget; remap values silently |
| Document retrieval / retrieval over staged docs | `LlamaIndex` (planned adapter; retrieval only, `quantitative_use=false` preserved) | Not applicable | Never treat retrieved chunks as numeric inputs |
| Synthesis / research answers | `You.com` research (explicit request only) | None | Never treat an answer-model output as a number or confirmation metric |

---

## 4. Data-contract boundary (canonical)

Source: `docs/architecture/agent-3-contracts.json` (validated JSON); `docs/ARCHITECTURE.md` §5; `docs/DATA_CONTRACTS.md`; `docs/METHODOLOGY.md` (methodology-v3 / features-v3).

### 4.1 Required contracts (implemented / partial / target)

| Contract | File / Path | Status | Evidence |
|---|---|---|---|
| Raw request envelope | `docs/PRODUCT_ARCHITECTURE_PLAN.md` §5.1; `provider/ledger.py` (`RequestLedger`) | Partial | Per-provider ledger exists; unified cross-provider envelope is target-state (`agent-3-data-control.md` §20). |
| Research document envelope | `docs/PRODUCT_ARCHITECTURE_PLAN.md` §5.2 | Target (not implemented) | `document_id`, `canonical_url`, `content_hash`, `parser_version`, `extraction_status` designed but no generic interface (`agent-2-product.md` §2; `agent-3-contracts.json`). |
| Typed claim envelope (`R-CLAIM`) | `docs/PRODUCT_ARCHITECTURE_PLAN.md` §5.3; `agent-3-contracts.json` (`contracts.claim`) | Target (not implemented) | Required fields (`entity_id`, `claim_type`, `value/unit/currency`, `period_start/end`, `published_at/retrieved_at`, `content_hash`, `reconciliation_status`, `quantitative_use`) defined; no implementation found in `src/`. |
| Snapshot contract (`MF`) | `data/snapshots/*.json` (`manifest.json`); `models/manifest.py` | Implemented | `provider_mode`, `as_of`, `version` (`snapshot-v2`), `method_version` (`methodology-v3`), `feature_version` (`features-v3`), `price_basis` (`adjusted_close==close` for Sectors with corp-action audit pending). |
| Evidence contract (`EV`) | `evidence/builder.py`; `models/evidence.py`; `intelligence/contract.py` | Implemented (partial) | `GroupEvidence` builds with `confirmation=ConfirmationEvidence()` (empty by construction); `brief-v1` and `intelligence-v1` frozen. Typed claim promotion gate not implemented (`agent-2-product.md` §2). |
| Feature contracts (`SF`, `GS`, `TE`) | `models/security_feature_snapshot.py`, `group_snapshot.py`, `transition_event.py` | Implemented | `feature_version=features-v3`; `group_snapshot` carries nested `ConcentrationMetrics`. |
| Quality / Coverage (`QL`, `CV`) | `data/quality.py`, `data/manifests.py` | Implemented | Quality assessments deterministic per provider mode (`public` / `fixture` / `sectors_fixture`); live modes not yet covered. |

### 4.2 Promotion rule (explicit, binding)

A research claim may become quantitative input **only** after all of the following conditions pass (`docs/PRODUCT_ARCHITECTURE_PLAN.md` §5.3; `docs/architecture/agent-3-data-control.md` §14; `docs/architecture/agent-3-contracts.json` contracts.claim):

1. **Exact entity match** — ticker/group/source alias resolved.
2. **Period validation** — `period_start` / `period_end` unambiguous and within data window.
3. **Unit validation** — value, unit, currency verified (not inferred from layout).
4. **Denominator validation** — denominator available (e.g., eligible constituent count, benchmark denominator).
5. **Source provenance** — `source_url`, `content_hash`, `retrieved_at`, `parser_version` preserved.
6. **Completeness checks** — `completeness_denominator` present and reconciled.
7. **Reconciliation validation** — deterministic reconciliation (e.g., `close - previous = change`; `change / previous = pct`) passes; any layout change must fail loudly (not remap silently, per `agent-3-data-control.md` §7).
8. **Schema / method version bump** — promotion requires a new schema/methodology version (`methodology-v3` → `v4`) and regression tests.

If any condition fails: result stays `CONTEXT_ONLY`, `DATA_GAP`, or `UNCONFIRMED`. Never promoted silently.

Default for all research records: `quantitative_use = false`. No exception without explicit promotion gate execution (`agent-3-contracts.json` contracts.claim.quantitative_use_default).

---

## 5. Implementation phases (canonical, resolved)

Source: `docs/architecture/agent-3-data-control.md` §15; `docs/PRODUCT_ARCHITECTURE_PLAN.md` §8; `docs/ARCHITECTURE.md` §8.

| Phase | Name | What is required | Evidence / Gate | Status |
|---|---|---|---|---|
| **A** | Freeze (current) | No new provider surface; architecture + feature boundary frozen. | `docs/ARCHITECTURE.md`, `docs/PRODUCT_ARCHITECTURE_PLAN.md`, agent artifacts (this synthesis). | **Done.** |
| **B** | Offline contracts + fixtures | Add promotion-gate unit tests; fixture `You`/`Tavily` (search/extract/crawl/retry/cache); fixture `LlamaParse` (PDF multi-page, missing page, unreconciled value); entity-resolution fixtures. | `tests/test_research_context.py`, `tests/test_llama_parse.py` exist; additional fixtures needed (`agent-3-data-control.md` §15). | **Partial.** |
| **C** | Fixture parity | Extend `data/fixtures/sectors/` routes; maintain `FixtureProvider` as deterministic regression path. | `tests/test_parity_public_sectors.py` exists; full fixture parity not confirmed (`agent-3-data-control.md` §15). | **In progress.** |
| **D** | Bounded live pilot (explicit approval only) | Single-date, single-provider (`sectors_live` or `You`/`Tavily`), with run manifest, budget reserve, raw response + parsed artifact + ledger + quality report preserved. | `tests/test_live_preflight.py`, `tests/test_429_blocked_path.py`, `test_provider_modes_and_readiness.py` cover gates; no live execution evidence (`agent-1-runtime.md` §17; `agent-3-data-control.md` §22). | **Not started.** Requires explicit approval and budget reserve. |
| **E** | Quantitative core parity | `yfinance` replay remains regression; Sectors live only after auth + full-universe pagination + price basis + benchmark + taxonomy + parity + credit economics proven. | `tests/test_provider_contracts.py`, `tests/test_parity_public_sectors.py`, `tests/test_comparability_and_adapter.py` provide regression walls; Sectors live not verified (`docs/SECTORS_MIGRATION_READINESS.md` acknowledges gaps). | **Not started.** |
| **F** | Research ingestion (NEXT) | Generic parser adapter; typed claim normalization; promotion-gate integration; evidence sidecar on `Methodology` / `Group Explorer`. | `llama_parse.py` adapter exists; typed claim envelope (`agent-2-product.md` §2) not implemented; promotion gate (`agent-3-data-control.md` §14) not implemented. | **Target-state only.** No live integration claimed. |
| **G** | Promotion to confirmation | Only fully-gated claims can be considered confirmation input; new schema/methodology version required; regression tests pass. | Not applicable — depends on Phase F. | **Not started.** |

---

## 6. Explicit `DATA GAP` / `UNCONFIRMED` / `CONTEXT ONLY` list (canonical)

Source: `docs/KNOWN_GAPS.md`; `docs/SECTORS_BLOCKERS.md`; `docs/SECTORS_MIGRATION_READINESS.md`; `docs/ARCHITECTURE.md`; `docs/architecture/agent-1-runtime.md` §14; `docs/architecture/agent-2-product.md` §2; `docs/architecture/agent-3-data-control.md` §19.

### Confirmed gaps (explicit, not hidden)

| Category | What is missing / unverified | Impact | Evidence path |
|---|---|---|---|
| `DATA GAP` — Sectors live auth / coverage | `SectorsProvider` live HTTP requires `SECTORS_API_KEY`; live call not verified in repo; coverage, pagination, price basis, taxonomy parity not load-tested against full IDX universe. | Quantitative core depends on fixture/yfinance for regression; `provider_mode` must declare `PUBLIC_PROTOTYPE` / `SECTORS_FIXTURE` unless live verified. | `docs/SECTORS_BLOCKERS.md`, `docs/SECTORS_MIGRATION_READINESS.md`, `docs/SECTORS_CREDIT_AUDIT.md`, `tests/test_provider_contracts.py` (fixture-only). |
| `DATA GAP` — Sectors price basis | Raw vs adjusted price ambiguity (Sectors `close` vs `adjusted_close`); corp-action audit (`audit_price_basis.py`) exists but full reconciliation not completed. | `price_basis` plumbing exists (`pipeline.py` `resolve_effective_price_basis`); live reconciliation unverified. | `docs/SECTORS_PRICE_BASIS.md`, `docs/METHODOLOGY.md`. |
| `DATA GAP` — Cross-provider budget contract | Per-provider ledgers (`provider/ledger.py`) exist; unified request envelope, budget preflight (`allow_credit_spend`), reserve vs actual reconciliation, retry cap accounting not fully integrated. | Budget economics observable per call but not reconciled against account-level credit; live pilot requires manual reserve. | `docs/ARCHITECTURE.md` §4 (design principles); `docs/PRODUCT_ARCHITECTURE_PLAN.md` §7; `agent-3-data-control.md` §20 (`post_request_accounting`). |
| `UNCONFIRMED` — Typed claim envelope (`R-CLAIM`) | `document_id`, `entity_id`, `claim_type`, `value/unit`, `period_start/end`, `reconciliation_status`, `quantitative_use` designed (`agent-3-contracts.json`) but no implementation found in `src/`. | Research Evidence (NEXT) cannot be promoted; all research payloads remain `quantitative_use=false` and sidecar-only. | `agent-2-product.md` §2; `agent-3-contracts.json`; `docs/DATA_CONTRACTS.md`. |
| `UNCONFIRMED` — Generic parser adapter (`B3`) | `LlamaParse` adapter (`llama_parse.py`) exists with bounded PDF parsing (`normalize_daily_statistics_markdown`, `run_llama_parse`); generic interface over `LlamaIndex`/`LlamaParse` for arbitrary official documents not implemented. | Only IDX Daily Statistics PDF adapter exists; broader official release parsing requires adapter extension. | `docs/ARCHITECTURE.md` §5 (lifecycle); `agent-1-runtime.md` §1b (`llama_parse.py` role). |
| `UNCONFIRMED` — LlamaIndex adapter | `LlamaIndex` retrieval adapter is a planned constraint (`agent-3-contracts.json` `routing.llamaindex_constraint`); no `llama_index` module found in `src/`. | Document retrieval over staged docs not available; retrieval must be performed through fixture/manual paths. | `agent-3-contracts.json`; `agent-1-runtime.md` §1b. |
| `CONTEXT ONLY` — Foreign-flow / broker / fundamental confirmation | Per-ticker foreign flow, broker activity, periodized fundamentals, corporate actions deferred (`agent-2-product.md` §4; `PRODUCT_ARCHITECTURE_PLAN.md` §6 deferred enrichment). | `Ticker Analysis` page (`TickerAnalysis.tsx`) shows these lanes with `CONTEXT ONLY` / `SAMPLE` badges; no metric writes. | `docs/ARCHITECTURE.md` §4; `agent-2-product.md` §4. |
| `CONTEXT ONLY` — Industry / sub-industry taxonomy | `taxonomy/registry.py` supports sector/konglo/themes; industry/sub-industry not implemented (`agent-2-product.md` §4 deferred). | Taxonomy toggle (`Sector/Industry`) disabled in `AppShell.tsx` with explanation when `Industry` absent. | `app/web/src/components/AppShell.tsx`; `docs/TAXONOMY_AUDIT.md`. |
| `CONTEXT ONLY` — Alert / scheduled refresh service | No background scheduler or alerting mechanism (`docs/KNOWN_GAPS.md` low-priority; `agent-2-product.md` non-goal #6). | No automated refresh; snapshot build is CLI-driven (`scripts/build_snapshot.py`). | `docs/KNOWN_GAPS.md`; `docs/ARCHITECTURE.md` §4 (threading & async). |
| `DATA GAP` — SPA contradiction / invalidation records | Streamlit (`view_models.py`) renders contradictions and invalidation; React SPA shows placeholder ("NO CONTRADICTION RECORDS / invalidation not emitted by the current web snapshot") (`agent-1-runtime.md` §2; `agent-2-product.md` §2). | `export_snapshot_json.py` does not emit contradiction/invalidation records; `GroupExplorer` (`GroupExplorer.tsx`) shows empty-state cards. | `agent-1-runtime.md` §2 (§6); `agent-2-product.md` §2 (§2 current vs target). |
| `DATA GAP` — Background scheduler / concurrent writers | Implementation is single-threaded, synchronous (`docs/ARCHITECTURE.md` §4); no concurrent writer, no service, no async workers (`agent-1-runtime.md` §2). | Concurrent snapshot writes unsupported; refresh must be serialized manually. | `docs/ARCHITECTURE.md` §4; `agent-1-runtime.md` §9. |
| `UNCONFIRMED` — Sectors live full-universe pagination | `sectors_client.py` paginated; `test_sectors_client.py` tests pagination; live full-universe pagination not verified against live endpoint. | Coverage gate (`60%`) relies on provider-specific pagination behavior; unverified for live Sectors. | `tests/test_sectors_client.py`; `docs/SECTORS_MIGRATION_READINESS.md`. |

### Confirmed non-gaps (explicit confirmation of no live call)

- **No Sectors API call performed during this architecture sprint.** Confirmed by agent reports (`agent-1-runtime.md` §17; `agent-2-product.md` §1; `agent-3-data-control.md` §22) and this synthesis file creation process (no `SECTORS_API_KEY` read, no `http.client` or `urllib` call, no `yfinance` live fetch). The only network-adjacent references are the bounded client interfaces (`you_client.py`, `tavily_client.py`, `llama_parse.py`, `public.py`) with `allow_live=False` defaults.
- **No `yfinance` live fetch performed.** `public.py` (`YFinanceProvider`) has retry logic but was not executed live; replay fixtures (`fixture.py`, `tests/fixtures/`) and harness (`yfinance_harness.py`) are the only exercised paths.
- **No credit spend observed.** Per-provider ledgers exist but show zero actual credit consumption for the run window covered by repository artifacts; `docs/SECTORS_CREDIT_AUDIT.md` documents the observability gap (reserve vs debit vs actual balance unavailable client-side).

---

## 7. Files created / modified by this synthesis

Created (only by this synthesis):
- `docs/ARCHITECTURE_DECISIONS.md` (this file)
- `docs/ARCHITECTURE_BASELINE.md` (see separate synthesis file)
- `docs/FEATURE_ARCHITECTURE.md` (see separate synthesis file)

Not modified:
- `docs/ARCHITECTURE.md`, `docs/PRODUCT_ARCHITECTURE_PLAN.md`, `docs/DATA_CONTRACTS.md`, `docs/METHODOLOGY.md`, `docs/KNOWN_GAPS.md`
- All `src/`, `app/`, `tests/`, `scripts/`, `config/`, `data/` files
- All `docs/architecture/agent-*-` artifacts (preserved as evidence source)

---

## 8. Verification (offline only)

- JSON contracts validated: `docs/architecture/agent-3-contracts.json` (Python `json.load` passes); `docs/architecture/agent-1-runtime.json` (21 nodes, 31 edges); `docs/architecture/agent-2-feature-matrix.json` (14 feature rows with contracts, modules, UI routes, status).
- No source file was edited; `git status` would show only the three new synthesis files.
- All evidence claims reference concrete paths (`docs/ARCHITECTURE.md`, `docs/PRODUCT_ARCHITECTURE_PLAN.md`, `src/idx_leadership/pipeline.py`, `tests/test_...`, `app/web/src/App.tsx`, etc.).

## 9. Reconciliation addendum (2026-09-13)
Adopt 7-plane + 14-row + named-gate canon. 8-plane/12-gate/16-feature counts rejected as counting artifacts. 21-node vs 8-component diagrams are scope variants. Stray repo-local `agent-a-runtime/` untouched; isolated harness outputs are evidence only.
