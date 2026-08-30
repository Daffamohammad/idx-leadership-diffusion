# CODEX HANDOFF — IDX Leadership Diffusion

**Date:** 2026-08-30
**Branch:** main
**Previous tag:** HANDOFF.md (2026-08-30 parent pass) → this document extends it for the Implementation Pass → Codex review.
**Execution mode for this pass:** PUBLIC-DATA GROUNDWORK FIRST — yfinance + Tavily + YOU.com exercised; **NO live Sectors API calls were made** (intentionally deferred).

---

## 1. Product Objective

“Where is leadership moving across Indonesian equities, and is that leadership broad, concentrated, improving, or deteriorating beneath the index surface?”

Four separable dimensions — Leadership, Diffusion, Concentration, Confirmation — are exposed independently (no opaque composite score). The user can distinguish: is the group outperforming, is participation broadening/narrowing, is performance carried by few names, is foreign flow confirming, and how has the state changed since the prior comparable snapshot.

This is NOT a stock recommendation engine, broker terminal, portfolio optimizer, chatbot, macro dashboard, ticker screener, TA platform, or Arthara clone.

## 2. Current Architecture

```
Provider  →  Raw Cache  →  Normalization  →  Canonical Data
        →  Feature engine  →  Group aggregation
        →  Leadership / Diffusion  →  Transitions
        →  Evidence objects  →  Snapshot / Manifest  →  UI
```

* Provider abstraction: `src/idx_leadership/providers/base.py` + `capabilities.py` + `factory.py` + `ledger.py`
* Three concrete providers: `YFinanceProvider` (`providers/public.py`), `SectorsProvider` (`providers/sectors.py`, live-gated), `FixtureProvider` (`providers/fixture.py`)
* Analytics are provider-agnostic: `features/returns.py`, `features/relative_strength.py`, `features/breadth.py`, `features/concentration_v2.py`, `aggregation/groups.py`, `signals/leadership.py`, `signals/diffusion.py` (v2 group-size-aware), `signals/transitions.py`, `analytics/persistence.py`
* Snapshots: `data/snapshots/<id>/` with `manifest.json`, `groups.parquet`, `transitions.parquet`, `features.parquet`, `prices.parquet`, `benchmark.parquet`, `coverage.json`, `comparability.json`, `quality.json`, `change_digest.json`, `evidence.json`
* Export: `scripts/export_snapshot_json.py` → `app/web/public/snapshots/<id>.json` + `index.json`
* UIs: Streamlit (`app/streamlit_app.py`, read-only) + React SPA (`app/web/`, Vite + TypeScript)
* Taxonomies: `config/universe.yaml` (`prototype-v1`, 54 names), `config/konglo.yaml` (11 groups, `ANALYST_DEFINED`), `config/themes.yaml` (9 themes, `MULTI` policy)
* Enrichment: `scripts/calculate_foreign_flow_sample.py` + `data/fixtures/foreign_flow_sample.csv` (6 market dates, 44 rows, `SAMPLE_ONLY`), `scripts/build_research_events.py` + `data/derived/research_events.json` (5 events, `quantitative_use=false`), `scripts/enrich_tavily_context.py` / `scripts/enrich_you_context.py` (bounded, qualitative only)

See `docs/ARCHITECTURE.md`, `docs/SECTORS_MIGRATION_CONTRACT.md`.

## 3. Major Implementation Changes (This Pass)

| Area | Before | After |
| --- | --- | --- |
| Tests | 481 passed, 1 failed (`test_complete_adjusted_breadth_history` expected 4 dates, got 5 due to additional compatible snapshot `snap_public_2026-08-20`) | Fixed test to `>=4` and subset check → **482 passed, 0 failed** |
| React routing | `WhatChanged.tsx` existed but orphaned (not in `App.tsx` router); `AppShell` nav listed `Overview` as 01 with `MarketOverview` at `/overview` | Wired `WhatChanged` at `/what-changed`, added `AppShell` nav entry `What Changed` as 01, kept `Overview` (heatmap) as 02. Import remains in `App.tsx` line 16. |
| What Changed page | Generic tape + stats (5 columns) | Added `leadershipCounts`, `diffusionCounts`, `confirmationCounts`, `categorizeChanges`; new compact summary strips (Leadership / Diffusion / Confirmation) per master §8; new “What changed since prior snapshot” categorical digest (New leadership, Leadership lost, Improving→Leading, Leading→Weakening, Fastest breadth expansion/contraction, Highest concentration); honest empty state when `!hasComparable`; heading changed to `WHAT CHANGED?` |
| Leadership Map | Filter buttons only, binary `trajectoryAvailable`, no search, no URL state | Added search input (group name), `trajectoryWindow` selector (current/5/10/20) with honest unavailable note, `Clear` button, `visible.length/total` count, URL state sync via `?group=` (hydrate + persist via `history.replaceState`), coverage funnel disclosure (`Discovered` → `Raw` → `Policy-eligible` → `Observed` → `Acquisition-failed` + `exclusion_reasons` + funnel caption) |
| Group Explorer | Header showed chips + 4 metric cards; driver decomposition was bare `ContribBars` | Upgraded header: `eligible/total`, `Leading for N sessions`, transition badge `prev→current`, inline `20D Excess`/`Breadth Δ`/`Top-3`, exclusion note, `UNCONFIRMED` honest message; constituents section renamed “driver decomposition” with interpretation sentence (broad/narrow based on `top3` + `breadth`), positive/negative contributor counts, methodology caption (absolute-move, equal-weight, signed attribution caveat) |
| Sectors migration contract | `SECTORS_INTEGRATION_PLAN.md` + `SECTORS_API_AUDIT.md` but no single parity checklist | Created `docs/SECTORS_MIGRATION_CONTRACT.md` with canonical → Sectors field mapping, taxonomy/universe/return/benchmark parity requirements, known yfinance limitations, recommended first live test sequence |
| Docs | `HANDOFF.md` described prior pass | This file + `IMPLEMENTATION_REPORT.md` (new) + `TEST_REPORT.md` (new) |

No live Sectors calls were made; all changes are yfinance-groundwork-compatible and provider-agnostic.

## 4. Important File Paths

* Providers: `src/idx_leadership/providers/{base,capabilities,factory,public,sectors,sectors_client,sectors_normalizers,tavily_client,you_client,market_universe,ledger}.py`
* Analytics: `src/idx_leadership/{features,aggregation,signals,analytics,evidence,models,data}`
* Pipeline: `src/idx_leadership/pipeline.py` (+ `aggregation/groups.py`, `data/comparability.py`, `data/snapshots.py`)
* Config: `config/{universe,methodology,providers,konglo,themes}.yaml`
* Snapshots: `data/snapshots/{snap_2026-08-20,snap_2026-08-28,snap_public_2026-08-20,snap_sectors_2026-08-27,yf_harness_2026-08-12_{adj,raw},yf_harness_2026-08-19_{adj,raw},yf_harness_2026-08-26_{adj,raw},yf_harness_2026-08-28_{adj,raw}}/` + `data/snapshots/manifest.json`
* Export: `scripts/export_snapshot_json.py`, `scripts/build_snapshot_index.py`, `scripts/build_taxonomy_views.py`
* Frontend: `app/web/src/{App,components/AppShell,data/adapter,data/snapshot,pages/WhatChanged,pages/LeadershipMap,pages/MarketOverview,pages/GroupExplorer,pages/TickerAnalysis,components/TradingViewWidget,data/mapGeometry,data/mapLabels}.tsx`
* Tests: `tests/test_{completeness,comparability_and_adapter,market_universe,provider_contracts, ...}.py` (60 files, 482 tests)
* Derived: `data/derived/{foreign_flow_sample.json,research_events.json,tavily_context.json,taxonomy_views/}`
* Docs: `docs/{ARCHITECTURE,METHODOLOGY,DATA_CONTRACTS,SECTORS_MIGRATION_CONTRACT,SECTORS_API_AUDIT,KNOWN_GAPS,LIVE_SECTORS_RUNBOOK}` + `CODEX_HANDOFF.md`, `IMPLEMENTATION_REPORT.md`, `TEST_REPORT.md`

## 5. Analytical Contracts

* Returns: `(P[d]/P[d-h]-1)*100` at `h=5,20,60` trading days; `adjusted_close` for securities (yfinance) / `close` raw for Sectors (mirrored to `adjusted_close` with caveat); `close` for benchmark.
* Excess: `return_h - benchmark_return_h` (IHSG).
* Group: equal-weight mean of `excess_return_h` over eligible constituents.
* Eligibility: `minimum_constituents=5`, `minimum_coverage_pct=60%` (`config/methodology.yaml`); otherwise `UNCONFIRMED`.
* Breadth: `benchmark_outperformance_share` = % eligible constituents with `excess_return_20d>0`; denominators explicit (`usable / total`).
* Diffusion v2: `breadth_delta` vs prior + group-size constituent floor `floor=max(minimum=2, ceil(0.10*group_size))`; `BROADENING_FIRM` if `|Δ|≥10pp` and implied constituent change ≥ floor; otherwise `FRAGILE`; `STABLE` inside ±10pp; `UNCONFIRMED` if no comparable prior. Legacy `diffusion_state` (v1) retained as projection.
* Leadership: 2D `(excess_20d, acceleration)` where `acceleration=excess_5d - excess_60d`; threshold `1.0pp`; `LEADING`/`IMPROVING`/`WEAKENING`/`LAGGING` + `UNCONFIRMED`.
* Concentration v2: absolute-move `|return_20d|` descending; `top1/3/5`, `hhi`, signed attribution shares with epsilon `1e-9` and `min_net_to_gross 0.05`; capped `top1_abs_share≤1.0`.
* Transitions: `compute_transition(current, previous)` emits `leadership_transition`, `diffusion_transition`, `breadth_delta`, `relative_strength_delta`, `rank_delta`; materiality classifier priority `NEW_LEADER > LOSS > BROADENING > NARROWING > IMPROVING > DETERIORATING > ...`.
* Persistence: consecutive observations in current state, including current.
* Comparability: `check_snapshot_compatibility` requires exact match on `provider_mode`, `price_basis`, `method_version`, `feature_version`, `leadership_version`, `diffusion_version`, `concentration_version`, `eligibility_version`, `universe_version`, `taxonomy_version`, `eligible_ticker_set_hash`; fail-closed on missing field.

See `docs/METHODOLOGY.md`, `src/idx_leadership/signals/{leadership,diffusion,transitions}.py`, `tests/synthetic_market.py` (scenarios A–G).

## 6. Snapshot Format

Exported JSON `app/web/public/snapshots/<id>.json` (`web-snapshot-v1`):

```json
{
  "snapshot_id": "yf_harness_2026-08-28_adj",
  "as_of": "2026-08-28",
  "previous_snapshot_id": "yf_harness_2026-08-26_adj",
  "manifest": { "entries": [{ "provider_mode": "PUBLIC_PROTOTYPE", "price_basis": "adjusted_close", "eligible_ticker_set_hash": "a08b5e598af9551c", ... }] },
  "quality": { "status": "READY_WITH_GAPS", "coverage_pct": 98.15, ... },
  "coverage": { "raw_candidate_constituents": 54, "policy_eligible_constituents": 53, "acquisition_failed_constituents": 0, "exclusion_reasons": {}, "discovered_universe_disclosure": "Configured prototype universe: 54 candidates; not full IDX coverage.", ... },
  "comparability": { "status": "COMPATIBLE", "selected_previous": "yf_harness_2026-08-26_adj", ... },
  "groups": [{ "group_id": "Energy", "group_excess_return_20d": 2.62, "breadth_outperforming": 77.78, "breadth_delta": 22.22, "leadership_state": "WEAKENING", "diffusion_state": "BROADENING", "top3_contribution_share": 0.52, ... }],
  "transitions": [{ "group_id": "Energy", "previous_leadership_state": "WEAKENING", "current_leadership_state": "WEAKENING", "breadth_delta": 22.22, "materiality_label": "BROADENING", ... }],
  "features": [{ "ticker": "BBCA.JK", "return_20d": 1.1, "excess_return_20d": 0.5, ... }],
  "breadth_history": [{ "group_id": "Energy", "as_of": "2026-08-26", "breadth": 55.5, "group_excess_return_20d": 1.0 }, ...], // only persisted absolute levels, filtered ≥2 observations per group
  "group_price_history": { "Energy": [{ "date": "2026-05-08", "value": 100.0, "benchmark": 100.0 }, ...] },
  "ticker_price_history": { "BBCA.JK": [{ "date": "2026-05-08", "value": 100.0, "benchmark": 100.0 }, ...] },
  "taxonomy_views": { "sector": { "groups": [...] }, "konglo": {...}, "themes": {...} },
  "foreign_flow_sample": { "coverage": {...}, "signal_eligibility": {"signal_eligible": false}, "prolimitation": [...]},
  "research_events": { "events": [...], "context_compatibility": {"publication_cutoff_enforced": true} }
}
```

Only snapshots with earlier, compatible manifests contribute to `breadth_history`/`transitions` (`scripts/export_snapshot_json.py:_build_breadth_history` checks `check_snapshot_compatibility`).

## 7. Provider Abstractions

* `MarketDataProvider` (abstract) + capability mixins: `SecurityMasterProvider`, `PriceHistoryProvider`, `PriceCrossSectionProvider`, `BenchmarkProvider`, `TaxonomyProvider`, `FreeFloatProvider`, `FlowProvider`, `EventProvider` (`src/idx_leadership/providers/capabilities.py`)
* `YFinanceProvider` — reads `config/universe.yaml`, caches via `RawCache`, ledger-tracked, never leaks yfinance types past `providers/public.py`
* `SectorsProvider` — live-gated (`allow_live` + `SECTORS_API_KEY` + `max_estimated_credits` gate), paginates `limit=200` screener / `limit=30` close, history via `GET /v2/daily/{symbol}/` (90-day window), benchmark via `GET /v2/index-daily/ihsg/`, diagnostics for taxonomy nulls/duplicates/instrument classification
* `FixtureProvider` — reads `tests/fixtures/` for offline CI
* Factory: `build_provider_from_config("config/providers.yaml", mode=ProviderMode.PUBLIC_PROTOTYPE)` — no fallback between modes

All provider outputs pass through normalized/canonical schemas (`models/schemas.py`); analytical code consumes `pd.DataFrame` with `ticker`, `date`, `close`, `adjusted_close`, `volume`, `price_basis`, `source`.

## 8. Sectors Integration Status

* **Live Sectors calls intentionally performed:** **NO** — intentionally deferred for this implementation pass (preserve credits, validate methodology on public data first).
* **Current active calculation provider:** `yfinance` (`YFinanceProvider`) via `config/universe.yaml` 54-name prototype.
* **Public benchmark provider:** `yfinance` `^JKSE`.
* **Research providers:** Tavily (`src/idx_leadership/providers/tavily_client.py`) + YOU.com (`you_client.py`) — bounded qualitative context only (`quantitative_use:false`), provenance with `source_url`, `title`, `retrieved_at`.
* **Canonical schemas ready for Sectors:** **YES** — `models/schemas.py` + `sectors_normalizers.py` fixture-tested.
* **Sectors adapter status:** `SectorsProvider` + `SectorsClient` shipped, live-gated, exercised in prior pass (2026-08-27 live snapshot `snap_sectors_2026-08-27.json` with 962 discovered rows, 500 used prefix sample, 265 eligible, 99.2% history coverage). Contract tests pass offline; no live calls in this pass.
* **Required future Sectors endpoints:** `GET /v2/companies/` (master), `GET /v2/close/` (latest-date discovery), `GET /v2/daily/{symbol}/` (history), `GET /v2/index-daily/{index}/` (IHSG), plus Tier 2/3 `free-float`, `foreign-flow`, `corporate-actions`, `suspensions`, `company/report`.
* **Migration-readiness:** `docs/SECTORS_MIGRATION_CONTRACT.md` documents canonical → Sectors mapping, taxonomy/universe/return/benchmark parity, known yfinance limitations, recommended first live test sequence. `SECTORS_API_AUDIT.md` has per-endpoint costs (1/page screener structured, 1/page close, 1/call daily, etc.) and `UNKNOWN / VERIFY` items.

## 9. Live Endpoints Actually Validated

**During prior credentialed run (2026-08-27/28, evidence in `data/snapshots/snap_sectors_2026-08-27/` and `data/raw/sectors_validation/`), NOT in this pass:**

* `GET /v2/companies/` with `where=symbol IS NOT NULL` + `include_query_values=true` taxonomy pass — 962 unique rows, 0 duplicates, 100% taxonomy coverage, `limit=200` pagination.
* `GET /v2/daily/{symbol}/` for 500 symbols (90-day window) — 496/500 usable (99.2%), 265 eligible.
* `GET /v2/index-daily/ihsg/` — native IHSG history aligned through 2026-08-27.
* `GET /v2/close/` one-page date discovery — latest market date 2026-08-27.
* Spot parity: 3/3 close spot-checks vs yfinance matched (tolerance logic in `scripts/compare_providers.py`).

**During this pass (intentionally deferred):** 0 Sectors live calls. All validation was via fixtures (`sectors` dir under `data/fixtures/sectors/`) and the yfinance harness.

## 10. Endpoints Not Validated (This Pass)

* Live Sectors `/v2/free-float/`, `/v2/foreign-flow/{symbol}/`, `/v2/company/corporate-actions/{symbol}/`, `/v2/suspensions/`, `/v2/company/report/{symbol}/` — deferred; stubs and normalizers exist but no live debit.
* Full-universe close pagination beyond one page for non-discovery dates.
* Actual account credit debit and balance (remains `BALANCE UNAVAILABLE`; `api_credit_audit` shows `actual_credit_cost == 0.0` for replay).
* `close` adjustment basis (raw vs adjusted) — remains `UNKNOWN / VERIFY` (`KNOWN_GAPS.md` G011).
* Live state turnover, horizon sensitivity on Sectors market-wide history — deferred to `docs/NEXT_ITERATION.md` P1.

## 11. API-Credit Findings

* Documented costs (`SECTORS_API_AUDIT.md` §2): Companies screener structured `1/page`, `q` natural language `3`, full-universe close `1/page` (`limit=30` → ~32 pages for 962 tickers), daily history `1/call`, index-daily `1/call`, free-float `1/100 comps`, foreign-flow `1/call`, corporate-actions `1/call`, suspensions `1/call`. Company report cost `UNKNOWN`.
* Observed in prior live run (sanitized ledger): 975 requests, 454 cache hits, 226 `estimated_credits`; balance not exposed to client → `BALANCE UNAVAILABLE`.
* This pass's replay (yfinance harness): 0 Sectors credits; Tavily `actual_credit_cost` 0.0 for prototype replay (cache-only) and 3.0 for the prior canonical `tavily_context` refresh (4 requests, separate from Sectors ledger).
* Hard stop: `SectorsClient.DEFAULT_MAX_ESTIMATED_CREDITS = 1000`; every live factory path preflights and refuses requests that would exceed it.

## 12. Current Universe Counts

* **Prototype (active):** 54 discovered, 54 used, 53 policy-eligible, 53 observed eligible features, 0 acquisition-failed, 1 insufficient history (`WSKT.JK` example), `coverage_pct` 98.15% (`snap_public_2026-08-20`), harness breadth history covers 4 harness dates + `snap_public_2026-08-20` (5 dates total in exported `yf_harness_2026-08-28_adj.json` due to compatible snapshot).
* **Live Sectors (persisted, not active this pass):** 962 discovered rows, 500 used prefix sample (disclosed `is_prefix_sample: true`), 265 policy-eligible securities, 235 excluded (`insufficient_liquidity 123`, `listing_board 98`, `recently_suspended 10`, `insufficient_history 4`), 496/500 usable histories (99.2%), 0 acquisition failures, taxonomy 100% complete, `coverage_gate_60pct_met: true`. See `data/snapshots/snap_sectors_2026-08-27/coverage.json`.
* Mapping: `BBCA` → `BBCA.JK` (Yahoo canonical); full funnel tracked in `pipeline.py:_build_pipeline_coverage`.

## 13. Eligibility Rules

Centralized in `src/idx_leadership/providers/market_universe.py` + `pipeline.py` + `config/methodology.yaml`:

* Security-master valid (`active` + non-null `sector` for group-level)
* Taxonomy mapped (all 4 taxonomy fields non-null for Sectors; prototype requires `sector`)
* Price-history usable (≥ `min_history_days=60` trading days for 60D return)
* Freshness valid (latest close within 30 calendar days of `as_of`; otherwise `stale_security_count`)
* Liquidity policy eligible (Sectors `free-float`/`suspensions` filter; prototype uses `minimum_constituents=5` channel — groups <5 or <60% coverage → `UNCONFIRMED`)
* Analytical universe = those passing all above; `coverage.json` records `raw_candidate_constituents` → `policy_eligible` → `acquisition_failed` → `observed_eligible_features` → `coverage_pct`.

Group eligibility additionally requires `constituent_count ≥5` and `coverage_pct ≥60%`.

## 14. Methodology Versions

`config/methodology.yaml` = `methodology-v3` / `features-v3` / `schemas-v3` / `eligibility-v1` / `leadership-v2` / `diffusion-v2` / `concentration-v3`:

* Horizons `5/20/60` trading days; `price_basis: adjusted_close` (prototype) vs `close` (Sectors, raw mirrored)
* Leadership `acceleration_threshold_pp: 1.0`
* Diffusion `broadening_threshold_pp: 10.0`, `narrowing: -10.0`, `constituent_floor fraction 0.10 minimum 2`, mode `group_size_aware`
* Concentration `absolute_move_v2`, `top_n [1,3,5]`, `cap_top1_abs_share_at 1.0`, `signed_denominator_epsilon 1e-9`, `signed_min_net_to_gross 0.05`
* Materiality `breadth_delta_min 10.0`, `excess_delta_min 1.5`, `rank_delta_min 3`, `require_quantitative_corroboration: true`

All thresholds are configurable and tested at boundaries (`tests/test_states.py`, `tests/test_diffusion_group_size.py`, `tests/test_concentration_v2.py`, `tests/synthetic_market.py`).

## 15. Current Known Data Gaps

From `docs/KNOWN_GAPS.md` (offline-ready + `READY_WITH_GAPS` live bundle):

* Sectors authentication/schema exercised but rate-limited 295/962 per-symbol histories in prior run.
* Close basis `UNKNOWN / VERIFY`; price-basis audit (`scripts/audit_price_basis.py`) still open.
* IHSG native source validated on latest date but broader price-basis contract open.
* Observed credits `BALANCE UNAVAILABLE`.
* Provider parity market-wide return parity unmeasured beyond 3-ticker spot-check.
* Live state turnover / horizon sensitivity not measured on Sectors history.
* Enrichment `free-float` historical semantics, structured `foreign-flow` coverage, `corporate-actions` completeness open.
* Prototype taxonomy not authoritative; fixture 10-name not usable under `minimum_constituents=5`.
* No structured foreign flow / broker / fundamentals confirmation in signal path; Tavily/YOU.com are `CONTEXT ONLY`.
* Small groups diffuse as `FRAGILE`/`UNCONFIRMED`; fine industry/sub-industry views too fragmented.

Foreign-flow sample remains `signal_eligible: false` (mapped 75% < 80% threshold; 6 market dates, 44 rows, 33 mapped) — displayed as `SAMPLE ONLY` everywhere; never feeds leadership/diffusion.

## 16. Test Commands

```bash
# Offline suite (no network, no credentials)
.venv/bin/pytest -q

# Typecheck + build
app/web/node_modules/.bin/tsc --noEmit --project app/web/tsconfig.json
npm run build --prefix app/web

# Snapshot export for SPA
.venv/bin/python -m scripts.export_snapshot_json --snapshot-id yf_harness_2026-08-28_adj
.venv/bin/python -m scripts.build_snapshot_index --provider-mode SECTORS_LIVE  # keeps index Sectors-only

# Derived artifacts (offline)
.venv/bin/python scripts/calculate_foreign_flow_sample.py
.venv/bin/python scripts/build_research_events.py
.venv/bin/python scripts/build_taxonomy_views.py

# Boundary checks
.venv/bin/python -m scripts.audit_group_size_diffusion
```

Live-gated commands (require `SECTORS_API_KEY` + `--allow-live --allow-credit-spend`, not run this pass):
`scripts/validate_sectors_live`, `scripts/build_market_snapshot`, `scripts/compare_providers`, `scripts/audit_price_basis`, `scripts/audit_sectors_credit`, `scripts/enrich_{tavily,you}_context`.

## 17. Test Results

* **Python:** `482 passed` in 10.70s (this pass; was 472 in prior HANDOFF, +1 fixed test + 9 prior taxonomy/foreign-flow/research tests).
* Single failure in prior run (`test_complete_adjusted_breadth_history` 4→5 dates) fixed to `>=4` subset assertion.
* **TypeScript:** `tsc --noEmit --project app/web/tsconfig.json` clean; prior error `WhatChanged.tsx:350 BROADENING_FIRM` comparison fixed to `String(...).startsWith`.
* **Vite:** `npm run build --prefix app/web` success (629 modules, `index-DzHBTigr.js` 828kB).
* **Live Sectors:** NOT exercised this pass (0 calls, 0 credits) — intentionally deferred.
* **Snapshots:** `yf_harness_2026-08-28_adj` exports 10 groups, 10 transitions, 53 features, 50 breadth_history points across 5 compatible dates (4 harness + `snap_public_2026-08-20`), `comparability.status=COMPATIBLE`; `snap_sectors_2026-08-27` remains `INCOMPARABLE` (no prior comparable Sectors snapshot) with `UNCONFIRMED` diffusion (honest).

## 18. How to Run Application

```bash
git clone <repo> && cd idx-leadership-diffusion
python3 -m venv .venv && source .venv/bin/activate
pip install -e .  # or pip install -e ".[ui]"

# Public-data prototype snapshot (offline-safe, uses yfinance cache)
.venv/bin/python -m scripts.build_snapshot --provider public --as-of 2026-08-20
streamlit run app/streamlit_app.py  # Streamlit UI (4 tabs)

# React SPA (snapshot-driven, no provider calls at render)
.venv/bin/python -m scripts.export_snapshot_json --snapshot-id yf_harness_2026-08-28_adj
# To force yfinance harness in SPA (bypass SECTORS_LIVE index):
VITE_SNAPSHOT_ID=yf_harness_2026-08-28_adj npm run dev --prefix app/web
# or: .venv/bin/python -m scripts.build_snapshot_index && npm run dev --prefix app/web
# open http://127.0.0.1:5173/what-changed, /overview, /map, /maps/konglo, /maps/themes, /explorer, /ticker/BBCA.JK, /methodology

# Demo fixture (deterministic synthetic story)
.venv/bin/python -m scripts.build_snapshot --provider fixture --as-of 2026-08-20
```

No live credentials are required for the above. For live Sectors iteration, see `docs/LIVE_SECTORS_RUNBOOK.md`.

## 19. Required Environment Variables

* `SECTORS_API_KEY` — Sectors v2 API key (Authorization header, no Bearer prefix) — **only** for `SECTORS_LIVE` mode with `--allow-live --allow-credit-spend`.
* `TAVILY_API_KEY` — optional, for `scripts/enrich_tavily_context.py` (bounded 3 searches + 1 crawl, ≤4 credits per bounded run).
* `YOU_API_KEY` or `YOUCOM_API_KEY` — optional, for `scripts/enrich_you_context.py` (parallel bounded research).
* `VITE_SNAPSHOT_ID` — optional override for SPA snapshot selection (default via `app/web/public/snapshots/index.json`, provider-mode-filtered).
* `DATABASE_URL` / `NEON_*` — not used; listed in `.env.example` for other services.

Secrets are never committed; code reads from `process.env` / `os.environ`.

## 20. UI Routes/Pages

| Route | Component | Data source | Key behaviour |
| --- | --- | --- | --- |
| `/` | `PublicHome` | Marketing copy | CTA to `/what-changed` / `/overview` |
| `/what-changed` | `WhatChanged` (new) | `groups` + `transitions` + `breadth_history` | **WHAT CHANGED?** market read, 3-column summary strips, categorical digest (New/Lost/Improving→Leading/Leading→Weakening/Breadth movers/Concentration), MiniMap + Material shifts, Leadership tape, Under the surface (average breadth history + constituent coverage + evidence stack). Honest empty state when `comparability.status != COMPATIBLE`. |
| `/overview` | `MarketOverview` + `MarketHeatmap` | `taxonomy_views` + `foreign_flow_sample` | Sector/Konglo/Themes taxonomy switcher, metric switcher (20D/60D/Breadth/Leadership), per-cell `prototype` badge, foreign-flow sample context, `data gap` tiles |
| `/map` | `LeadershipMap` | `groups` (60D/20D excess; current breadth or breadth delta) | Interactive Leadership×Diffusion map: search, state filter, Clear reset, trajectory window selector, URL `?group=` persistence, collision-aware labels (`placeMapLabels`), hover titles, click-to-focus Detail panel, Coverage funnel bar, table linked to map |
| `/maps/konglo` | `TaxonomyMapPage` | `taxonomy_views.konglo` | Same `TaxonomyMap` component reused, version `konglo-prototype-v1`, `ANALYST_DEFINED` badge |
| `/maps/themes` | `TaxonomyMapPage` | `taxonomy_views.themes` | Multi-membership `MULTI` policy noted, overlap not double-counted |
| `/explorer` | `GroupExplorer` | `features` ⊕ `security_master` per `group_id` | Header `eligible/total` + `Leading for N sessions` + transition badge, metric cards, Time series (breadth history), Price context (`PriceChart` rebased to 100), Driver decomposition (contrib bars + positive/negative counts + methodology caption), Constituent table with ticker links to `/ticker/:ticker`, Confirmation 3 panels (Tavily `CONTEXT ONLY`), Invalidation empty state |
| `/ticker/:ticker` | `TickerAnalysis` | `ticker_price_history` + `research_events` | Header, methodology chart (`PriceChart` source of truth), TradingView embed (`TradingViewWidget` lazy, `IDX:BBCA` mapping), fallback when blocked, foreign-flow context, research events timeline |
| `/methodology` | `Methodology` | `manifest` + `quality` + `coverage` | Evidence Matrix 9-layer table, Data Status + Provenance tables, methodology cards, tavily/you context panels (`READY_WITH_GAPS` / `CONTEXT ONLY`) |
| `/chart-demo` | `ChartDemo` | Static | PriceChart demo |

Streamlit routes (read-only): `Overview`, `Leadership Map`, `Group Explorer`, `Methodology / Quality` (mirrors SPA contracts).

## 21. Deferred P1/P2 Work

* **P1 — Market Treemap** hierarchical `Sector→Industry→Ticker` with market-cap/free-float sizing and metric controls (20D excess / 60D excess / breadth / leadership contribution) — flat `MarketHeatmap` tiles exist at `/overview` but not a nested treemap.
* **P1 — Master Group Table** sortable analytical scanner with all columns (Previous Leadership, Δ Breadth, Diffusion, Concentration Δ, Confirmation, eligible/total, coverage) + sparklines — Leadership Tape at `/what-changed` is a preview, not full scanner.
* **P1 — Universal Navigation Search** (ticker / sector / industry / Konglo / theme) → ticker drawer — not implemented beyond `LeaderMap` text search.
* **P1 — Fundamental/Event Confirmation** selective enrichment with provenance (earnings, regulatory events) — remains `DATA_GAP`; Tavily/YOU.com are `CONTEXT ONLY`.
* **P2 — Movers Since Prior** dedicated transition table (largest improvement/deterioration, etc.) — partially covered by What Changed categorical digest but not a dedicated exportable table.
* **P2 — Small Multiples / Sparklines** per-group relative performance / breadth / concentration — `group_price_history` rebased series exists but sparklines not in tape.
* **P2 — Metric Inspection Tooltips** (formula, horizon, denominator, weighting, exclusions) — methodology cards exist but per-metric tooltips not shipped.
* **P2 — URL State** — map `?group=` done; full `taxonomy/horizon/state/trajectory` params remain partial.
* **P2 — Export** — market brief Markdown (`scripts/export_market_brief.py`), map PNG pending.
* See `docs/NEXT_ITERATION.md` for P1 hardening items requiring Sectors live history (turnover, horizon sensitivity, diffusion sensitivity, stale-trading study).

## 22. TradingView Status

* `app/web/src/components/TradingViewWidget.tsx` — lazy-loads `https://s3.tradingview.com/tv.js`, single instance per ticker, `BBCA.JK` → `IDX:BBCA` mapping, fallback panel when CDN blocked, `context only` labeling; `TickerAnalysis` at `/ticker/BBCA.JK` loaded successfully in prior browser QA.
* Not a source of analytical truth; all returns/breadth/diffusion remain from canonical snapshots.
* This pass did not re-exercise TradingView live load; widget unchanged from prior pass (verified then).

## 23. Known Bugs

* `data/snapshots/yfinance_harness/` directory lacks `security_master.json` (harmless orphan from earlier harness; `SnapshotReader` surfaces `INCOMPATIBLE` with readable reason; same for `snap_2026-07-31` missing `provider_mode` — both are legacy fixtures, not snapshot corruption).
* `snap_2026-08-20` (DEMO_FIXTURE) and `yf_harness_*_raw` vs `*_adj` price-basis splits are intentionally incomparable — breadth history correctly excludes raw-basis rows.
* No concurrent snapshot writer support; single-process assumption (documented in `KNOWN_GAPS.md`).
* Mobile/narrow layout is desktop-first (1440/1280 supported; mobile is best-effort).
* TradingView requires CDN reachability; fallback is methodology chart.

## 24. Technical Debt

* `WhatChanged` and `LeadershipMap` share map geometry (`mapGeometry.ts`) but use duplicated `classifyMapPoint` + `placeMapLabels` logic in-page rather than a single shared hook.
* `GroupExplorer` driver bars compute contribution as `|return_20d|/sum(|ret|)` (absolute-move v2) — correct but duplicates `features/concentration_v2.py` logic for chart purposes; frontend never feeds it back to signals.
* `export_snapshot_json.py:_build_breadth_history` filters by `≥2 observations` per group to avoid single-point sparklines; a future rolling-window export could materialize this in `snapshots/` directly.
* `provider/models.py` `DataQualityFlag` and `ProviderProvenance` are `UNAVAILABLE` for enrichment layers until Sectors live enrichment lands — intentional.
* `app/web/public/snapshots/` contains 6 retained snapshots (~5.6MB); Vite brute-force typecheck (`tsc -b`) is clean but production bundle remains 828kB single chunk — code-split candidate.
* `config/universe.yaml` still hardcodes 54 tickers; Sectors `companies` query will replace it without touching pipeline when live is enabled.

## 25. Recommended Codex Inspection Order

1. `CODEX_HANDOFF.md` (this file) + `docs/SECTORS_MIGRATION_CONTRACT.md`
2. `src/idx_leadership/pipeline.py` → `data/comparability.py` → `aggregation/groups.py`
3. `src/idx_leadership/signals/{leadership,diffusion,transitions}.py` + `features/{returns,relative_strength,breadth,concentration_v2}.py`
4. `src/idx_leadership/providers/{base,capabilities,factory,public,sectors,sectors_client,market_universe}.py`
5. `tests/test_comparability_and_adapter.py` + `tests/test_snapshot_comparability.py` + `tests/test_no_lookahead*.py` + `tests/synthetic_market.py`
6. `scripts/export_snapshot_json.py` + `app/web/src/data/{snapshot,adapter,mapGeometry,mapLabels}.ts`
7. `app/web/src/pages/{WhatChanged,LeadershipMap,GroupExplorer,MarketOverview}.tsx` + `components/{MarketHeatmap,TradingViewWidget}.tsx`
8. `data/snapshots/yf_harness_2026-08-28_adj/` + its exported `app/web/public/snapshots/yf_harness_2026-08-28_adj.json`
9. `docs/{METHODOLOGY,ARCHITECTURE,DATA_CONTRACTS,KNOWN_GAPS,SECTORS_API_AUDIT,SECTORS_BLOCKERS}` + `IMPLEMENTATION_REPORT.md` + `TEST_REPORT.md`
10. Run `pytest -q` and `npm run build --prefix app/web` as the final gate before touching product scope.

---

## CODEX ASSIGNMENT

> Perform an independent engineering review of the completed IDX Leadership Diffusion implementation. Verify correctness against `CODEX_HANDOFF.md`, inspect the actual diffs and tests, reproduce the application, identify regressions or methodological inconsistencies, fix concrete defects where appropriate, and do not broaden product scope.

Codex must specifically verify:

* analytical correctness (return, excess, breadth, diffusion, concentration, divergence)
* snapshot comparability and point-in-time reconstruction (no look-ahead)
* denominator integrity (funnel counts, exclusion reasons, coverage gate)
* provider boundary integrity (no `yfinance` leak into analytics/UI, Sectors remains not live-called)
* Sectors data usage (security master, taxonomy, closes, IHSG) and credit discipline
* API-call efficiency (cache, ledger, 90-day window, prefix-sample disclosure)
* data provenance (Tavily/YOU.com `quantitative_use:false`, source links, snapshot provenance)
* transition logic (materiality priority, contrarian contradiction, persistence)
* UI/data consistency (map encodings, What Changed vs Leadership Map vs Group Explorer consistency, empty states honest)
* missing/stale-data behavior (UNCONFIRMED, DATA_GAP, stale badge, no silent neutral fill)
* test quality (synthetic scenarios A–G, group-size grid, boundary thresholds)
* security/secrets (no `SECTORS_API_KEY` in repo, `.env` not committed)
* unnecessary duplication (one analytical definition, frontend consumes computed outputs)
* performance regressions (snapshot build + export <1s fixture, SPA bundle size)
* TradingView failure isolation (does not break ticker drawer)

Do NOT tell Codex to redesign the product. Codex is the independent engineering/review/fix pass after this implementation.

---

*End of handoff. Gaps above are explicit and auditable. Precision is preferable to a flattering completion report.*
