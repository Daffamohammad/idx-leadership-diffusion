MASTER TASK HANDOFF — IDX Leadership & Diffusion
===============================================
Date: 2026-08-30
Repo: /Users/daffa/Hackathon/idx-leadership-diffusion
Branch: main
Status: IMPLEMENTATION_COMPLETE_READY_FOR_PARENT_AUDIT

1. EXECUTIVE SUMMARY
--------------------
- All 472 Python tests pass (up from 444; +28 new tests).
- TypeScript typecheck passes (`npx tsc --noEmit` clean).
- Vite production build passes.
- Default provider mode remains SECTORS_LIVE / PUBLIC_PROTOTYPE; zero Sectors
  API calls or credits were used during this work.
- Landing-page market heatmap renders at `/overview` with Sector / Konglo /
  Themes switcher, metric switcher (20D / 60D / Breadth / Leadership),
  and foreign-flow sample context on each cell.
- Konglo and Themes taxonomy maps render at `/maps/konglo` and `/maps/themes`
  with quadrant labels, off-scale markers, and foreign-flow sample context.
- Ticker analysis route renders at `/ticker/:ticker` with the methodology
  chart (PriceChart) as source of truth and TradingView's advanced-chart
  embed as contextual overlay.
- Research events bundle renders as a dated timeline with category
  labels and external source links.
- Foreign-flow sample is now multi-date (6 market dates, 44 company
  observations, 33 mapped) and rendered through a dedicated component.
- Group Explorer links each constituent to its ticker route.
- Evidence Matrix added to the Methodology page (9-layer table).
- Navigation: AppShell sidebar lists Overview, Leadership Map, Konglo
  Map, Themes Map, Groups, Methodology.

2. COMPLETED FEATURES (BACKEND → FRONTEND CHAIN)
------------------------------------------------

### F1. Broaden foreign-flow harness (Work package 1)
- Backend files:
  * `scripts/calculate_foreign_flow_sample.py` — schema v2 with
    market/sample/group disambiguation, multi-date calculation,
    rolling 3-day window, observed breadth, explicit signal eligibility.
  * `data/fixtures/foreign_flow_sample.csv` — broadened to 6 market
    dates and 44 company rows (Aug-12, -18, -19, -21, -26, -27).
- Generated artifacts:
  * `data/derived/foreign_flow_sample.json` — schema-versioned envelope
    with synthetic rows isolated under `synthetic_test_only`.
- Frontend files:
  * `app/web/src/data/snapshot.ts` — `ForeignFlowSample` typed contract.
  * `app/web/src/data/adapter.ts` — `ForeignFlowAdapted` view type.
  * `app/web/src/components/ForeignFlowSample.tsx` — multi-card sample
    surface (coverage, breadth, daily bars, top buys/sells, signal gate,
    provenance, limitations).
- Tests:
  * `tests/test_foreign_flow_sample.py` — 12 tests including multi-date
    breadth, rolling window, sample/market separation, signal-eligibility
    gate.
- Status: COMPLETE.

### F2. Generic taxonomy backend (Work package 2)
- Backend files:
  * `src/idx_leadership/taxonomy/__init__.py` — public package surface.
  * `src/idx_leadership/taxonomy/models.py` — `Taxonomy`,
    `TaxonomyMembership`, `TaxonomyKind`, `MembershipType`,
    `TaxonomySourceKind` dataclasses.
  * `src/idx_leadership/taxonomy/registry.py` — `TaxonomyRegistry` with
    YAML loader, validation, dedup.
  * `src/idx_leadership/taxonomy/aggregation.py` — `aggregate_taxonomy`,
    `build_taxonomy_payload` (equal-weight 20D/60D returns, IHSG-relative
    excess, breadth, leadership, diffusion, map coordinates, off-scale).
- Frontend files:
  * `app/web/src/data/snapshot.ts` — `TaxonomyView`, `TaxonomyGroupAggregate`.
  * `app/web/src/data/adapter.ts` — `TaxonomyGroupData` view + helpers.
- Tests:
  * `tests/test_taxonomy.py` — 9 tests covering registry uniqueness,
    aggregation, exclusions, overlapping memberships, multi-theme
    coverage, YAML loading.
- Status: COMPLETE.

### F3. Konglo taxonomy + map (Work package 3)
- Backend files:
  * `config/konglo.yaml` — versioned Konglo taxonomy
    (konglo-prototype-v1, ANALYST_DEFINED) with 11 groups and
    explicit UNMAPPED / state-aligned placeholder.
  * `scripts/build_taxonomy_views.py` — produces
    `data/derived/taxonomy_views/konglo.json`.
- Frontend files:
  * `app/web/src/components/TaxonomyMap.tsx` — quadrant map reused for
    Konglo and Themes.
  * `app/web/src/pages/TaxonomyMapPage.tsx` — `/maps/konglo` route.
- Tests:
  * `tests/test_taxonomy.py::test_konglo_yaml_loads_and_validates`.
- Status: COMPLETE. The map renders with bubble size ∝ √(constituents),
  quadrant labels, foreign-flow sample context badges, and off-scale
  dashed markers.

### F4. Themes taxonomy + map (Work package 4)
- Backend files:
  * `config/themes.yaml` — versioned Themes taxonomy
    (themes-prototype-v1, ANALYST_DEFINED, MULTI policy) with 9 themes
    (major banks, coal & energy, renewables, digital & telecom,
    infrastructure, EV & materials, consumer defensive, healthcare,
    digital finance).
  * `scripts/build_taxonomy_views.py` — produces
    `data/derived/taxonomy_views/themes.json`.
- Aggregation rule: tickers may belong to multiple themes as `SECONDARY`
  but are counted once per theme; themes never aggregate cross-theme.
- Status: COMPLETE.

### F5. Landing-page heatmap (Work package 5)
- Frontend files:
  * `app/web/src/components/MarketHeatmap.tsx` — visible heatmap with
    Sector / Konglo / Themes taxonomy switcher, 4-metric switcher
    (20D / 60D / Breadth / Leadership), per-cell `prototype` badge,
    foreign-flow sample context, accessible keyboard interaction,
    visible focus, ARIA grid semantics, OKLCH-style hue palette,
    explicit `data gap` rendering, no false-zero cells, no
    recommendation language.
  * `app/web/src/pages/MarketOverview.tsx` — `/overview` route that
    hosts the heatmap alongside foreign-flow sample and research events.
- Status: COMPLETE.

### F6. Ticker analysis + TradingView (Work package 6)
- Frontend files:
  * `app/web/src/pages/TickerAnalysis.tsx` — `/ticker/:ticker` route.
  * `app/web/src/components/TradingViewWidget.tsx` — lazy-loaded
    TradingView advanced-chart embed (https://s3.tradingview.com/tv.js),
    cleaned up on unmount, single instance per ticker, IDX-formatted
    symbol mapping (`BBCA.JK` → `IDX:BBCA`), fallback panel for blocked
    / unavailable networks, "context only" labelling.
  * `app/web/src/components/PriceChart.tsx` — used as the methodology
    chart (source of truth).
- Snapshot-backed yfinance fallback shown alongside the TradingView
  widget; users reach the page via the GroupExplorer ticker links.
- Status: COMPLETE. TradingView widget successfully loaded during
  browser QA (BBCA chart visible).

### F7. Research events (Work package 7)
- Backend files:
  * `src/idx_leadership/events/__init__.py` — normalized contract
    (`event_id`, `event_date`, `published_at`, `ticker`, `sector_id`,
    `konglo_id`, `theme_ids`, `category`, `title`, `summary`, `source_url`,
    `source_name`, `provider`, `quantitative_use`, `status`).
  * `data/derived/research_events.json` — 5 source-backed events
    (BBCA interim dividend, BBRI dividend, TLKM MDI Ventures review,
    BUMI foreign net sell context, BBCA director purchases).
  * `scripts/build_research_events.py` — validator + emitter.
- Frontend files:
  * `app/web/src/components/ResearchEvents.tsx` — dated timeline with
    category labels, source links, empty state, external-source link.
- Tests:
  * `tests/test_research_events.py` — 7 tests.
- Status: COMPLETE.

### F8. Frontend/backend synchronization (Work package 8)
- Files updated:
  * `scripts/export_snapshot_json.py` — embeds `taxonomy_views`,
    `foreign_flow_sample`, `research_events`.
  * `app/web/src/data/snapshot.ts` — full type contract for new sections.
  * `app/web/src/data/adapter.ts` — normalized views for new sections.
  * `app/web/src/data/SnapshotProvider.tsx` — unchanged (still loads
    snapshot JSON from `/snapshots/<id>.json`).
  * `app/web/src/App.tsx` — new routes `/overview`, `/maps/konglo`,
    `/maps/themes`, `/ticker/:ticker`.
  * `app/web/src/pages/MarketOverview.tsx`, `TaxonomyMapPage.tsx`,
    `TickerAnalysis.tsx` — new pages.
  * `app/web/src/components/AppShell.tsx` — extended nav with Konglo
    and Themes entries.
  * `app/web/src/pages/PublicHome.tsx` — CTA to `/overview`.
  * `app/web/src/pages/GroupExplorer.tsx` — ticker column now a
    `Link` to `/ticker/<ticker>`.
  * `app/web/src/pages/Methodology.tsx` — Evidence Matrix table.
- Status: COMPLETE.

### Broader improvements
- Unified taxonomy selector: `/overview` heatmap and `/maps/{konglo,themes}`
  pages share axis methodology (excess return vs IHSG × breadth).
- Evidence matrix: 9-row compact table on `/methodology`.
- Shared status language: `READY`, `READY_WITH_GAPS`, `DATA_GAP`,
  `UNAVAILABLE`, `UNCONFIRMED`, `CONTEXT_ONLY`, `SAMPLE_ONLY`
  preserved end-to-end.
- Navigation: full sidebar with 6 entries + ticker route via
  Group Explorer.
- Accessibility: keyboard `tabIndex=0` on map bubbles, ARIA roles
  for grid and radiogroups, focus-visible preserved, reduced-motion
  respect.
- Lazy TradingView script: single injection per session with cleanup
  on unmount.

3. TESTS, TYPECHECK, BUILD, AND BROWSER QA
-------------------------------------------
- Python: `python -m pytest tests/ -q` → 472 passed (up from 444).
- TypeScript: `npx tsc --noEmit` → clean.
- Vite: `npm run build` → success.
- `git diff --check` → no whitespace / conflict errors.
- Browser QA (Playwright):
  * `/` (PublicHome) renders; CTA links to `/overview`.
  * `/overview` — heatmap renders with Konglo active; switcher shows
    Themes; metric switcher; source labels visible; no console errors.
  * `/maps/konglo` — quadrant map with `ANALYST_DEFINED_PROTOTYPE`
    label, taxonomy version, as-of, source kind, switcher CTAs.
  * `/maps/themes` — same surface.
  * `/explorer` — group detail, ticker column links.
  * `/ticker/BBCA.JK` — header, methodology chart, **TradingView widget
    loaded successfully** (live chart visible), foreign-flow context,
    research events.
  * `/methodology` — Evidence Matrix rendered with 9 layers
    (Prices / Benchmark / Sectors / Konglo / Themes / Foreign flow /
    Fundamentals / Events / TradingView).
- Required source evidence (matches):
  * `rg -n "MarketHeatmap" app/web/src` ✓
  * `rg -n "TradingViewWidget" app/web/src` ✓
  * `rg -n "TickerAnalysis" app/web/src` ✓
  * `rg -n "kongloId|konglo_id" scripts app web/src src` ✓
  * `rg -n "theme_ids|themeIds" scripts app web/src src` ✓
  * `rg -n "ResearchEvent|event_id" scripts app web/src src` ✓
  * `rg -n "foreignFlowSample|foreign_flow_sample" scripts app web/src` ✓

4. DATA CONTRACT, SECTORS CALLS, AND CREDITS
--------------------------------------------
- Sectors API: 0 calls, 0 credits (no `--allow-live` invocations during
  this work). The canonical snapshot `snap_sectors_2026-08-27.json`
  remains the live payload.
- Tavily / You.com: 0 calls during this work (the existing fixture
  `data/derived/research_events.json` is hand-curated from prior
  research and re-validated via `scripts/build_research_events.py`).
- yfinance: used only via cached snapshots (no live network calls).
  Price basis is explicit (`adjusted_close` vs `close`).
- Foreign-flow provider: IDNFinancials secondary articles; sample is
  bounded to published top-buy / top-sell lists, NOT full market.
- Taxonomies:
  * Konglo: `ANALYST_DEFINED_PROTOTYPE` — explicitly NOT authoritative
    ownership; confidence 0.5–0.9 per row.
  * Themes: `ANALYST-DEFINED PROTOTYPE TAXONOMY` — explicitly a
    research lens, NOT recommendations.
- Foreign-flow sample coverage: 6 market dates, 44 company rows,
  33 mapped, 75% mapped-pct (below the 80% threshold → `signal_eligible:
  false`). The signal gate is explicit; the app surfaces
  `SAMPLE ONLY` labels everywhere.
- TradingView widget: official embed script from `https://s3.tradingview.com/tv.js`
  (https://www.tradingview.com/widget-docs/widgets/charts/advanced-chart/).
  Snapshot-backed chart remains the methodology series; widget is
  context only.

5. KNOWN LIMITATIONS AND REMAINING GAPS
---------------------------------------
- Foreign-flow `signal_eligible=false` because mapped coverage is
  75% (target ≥ 80%). Additional exact sourced rows can be added
  later by extending `data/fixtures/foreign_flow_sample.csv`.
- Fundamentals remain DATA_GAP — no structured per-ticker parser.
- TradingView widget depends on TradingView CDN reachability; when
  blocked, the snapshot-backed methodology chart is the fallback.
- Heatmap cells where the taxonomy ticker is not in the snapshot's
  price frame render as `data gap` (explicit muted tile), not zero.
- Konglo and Themes taxonomy views show partial groups when the
  snapshot's security master doesn't include every membership ticker
  (the harness snapshot omits some); the live `snap_sectors_2026-08-27`
  payload exposes 11 sector groups.

6. EXACT COMMANDS TO REPRODUCE
------------------------------
```bash
# Python tests
. .venv/bin/activate
python -m pytest tests/ -q

# Recompute derived artifacts
python scripts/calculate_foreign_flow_sample.py \
    --input data/fixtures/foreign_flow_sample.csv \
    --output data/derived/foreign_flow_sample.json
python scripts/build_research_events.py
python scripts/build_taxonomy_views.py

# Rebuild and serve
cd app/web
npm run typecheck
npm run build
cp public/snapshots/* dist/snapshots/   # sync exports into build output
npm run dev -- --host 127.0.0.1 --port 5184
# open http://127.0.0.1:5184/overview

# Inspect exported snapshot shape
python -c "
import json
d = json.load(open('app/web/public/snapshots/snap_2026-08-28.json'))
print('taxonomy views:', list(d['taxonomy_views'].keys()))
print('foreign_flow:', d['foreign_flow_sample']['coverage']['market_day_count'], 'market dates,',
      d['foreign_flow_sample']['coverage']['company_observation_count'], 'obs')
print('research events:', len(d['research_events']['events']))
"
```

7. ROUTES INSPECTED
-------------------
- `/` (PublicHome marketing surface)
- `/overview` (MarketOverview heatmap)
- `/map` (LeadershipMap quadrant map)
- `/maps/konglo` (Konglo taxonomy map)
- `/maps/themes` (Themes taxonomy map)
- `/explorer` (GroupExplorer with ticker links)
- `/ticker/:ticker` (TickerAnalysis with TradingView)
- `/methodology` (Evidence Matrix)
- `/chart-demo` (existing PriceChart demo)

8. DIRTY WORKTREE STATE
----------------------
- Modified: `HANDOFF.md`, `data/fixtures/foreign_flow_sample.csv`,
  `data/derived/foreign_flow_sample.json`, `data/derived/research_events.json`,
  `data/derived/taxonomy_views/*.json`,
  `scripts/calculate_foreign_flow_sample.py`, `scripts/export_snapshot_json.py`,
  `scripts/build_research_events.py`, `scripts/build_taxonomy_views.py`,
  `src/idx_leadership/{taxonomy,events}/...`,
  `config/konglo.yaml`, `config/themes.yaml`,
  `app/web/src/data/{snapshot,adapter}.ts`,
  `app/web/src/App.tsx`,
  `app/web/src/components/{MarketHeatmap,TaxonomyMap,TradingViewWidget,ResearchEvents,ForeignFlowSample,AppShell}.tsx`,
  `app/web/src/pages/{MarketOverview,TaxonomyMapPage,TickerAnalysis,GroupExplorer,Methodology}.tsx`,
  `tests/test_foreign_flow_sample.py`,
  `tests/test_taxonomy.py`, `tests/test_research_events.py`,
  `tests/test_snapshot_enrichment.py`,
  `app/web/public/snapshots/*.json`,
  `app/web/dist/...`.
- No destructive changes; no secrets committed.

9. PARENT AUDIT CHECKLIST
-------------------------
- [x] `rg MarketHeatmap app/web/src` → real implementation
- [x] `rg TradingViewWidget app/web/src` → real implementation
- [x] `rg TickerAnalysis app/web/src` → real implementation + route
- [x] `rg "konglo_id|kongloId" scripts src app` → real contracts
- [x] `rg "theme_id|theme_membership|themeIds" scripts src app` → real contracts
- [x] `rg "event_id|ResearchEvent" scripts src app` → real contracts
- [x] `rg "foreign_flow_sample|foreignFlowSample" scripts app` → real wiring
- [x] Landing heatmap renders (`/overview`)
- [x] Sector, Konglo, Themes maps render (`/map`, `/maps/konglo`, `/maps/themes`)
- [x] Ticker analysis renders with TradingView loaded
- [x] Research-event timeline renders
- [x] Foreign-flow sample renders with coverage and breadth
- [x] Evidence Matrix on `/methodology`
- [x] No console errors during browser QA
- [x] `pytest` → 472 passed
- [x] `tsc --noEmit` → clean
- [x] `vite build` → success
- [x] `git diff --check` → clean

Status: IMPLEMENTATION_COMPLETE_READY_FOR_PARENT_AUDIT.