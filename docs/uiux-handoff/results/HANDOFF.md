# HANDOFF — UI/UX and Arthara workflow implementation

Base revision: `2c81894` (`feat(ui): unify group detail and catalog navigation with verified browser QC`), whose parents are `ed6fd61` → `df33d75`.
Result revision: the local commit containing this work package (no push, no force-push, no amend of others' history).
Bundle: `snap_sectors_2026-08-27`, as of 27 Aug 2026, `complete=false`.
Mode: offline only. Zero live Sectors calls. Search/parser ceilings untouched (0 You.com, 0 Tavily, 0 LlamaParse this package).

## Changed files — this revision (P2 defects + WCAG contrast audit)

- `app/web/src/index.css` — new theme tokens: `--tint-warn/-flag/-note/-ok/-danger/-cream/-alert`, `--alert-line`, `--alert-ink`, `--on-accent`, `--quad-improving/-leading/-lagging/-weakening`, and `--link` (referenced by 14 call sites but **never defined**, so it silently resolved to `unset`); light status colours darkened for 4.5:1 on white (`--color-leading #43607e`, `--color-improving #2c776d`, `--color-warning #856626`, `--color-weakening #8f4b49`).
- `app/web/src/components/RotationView.tsx` — **P2-4**: diagnostic-mode visibility toggles (`diagnosticKeys` / `plottedRows` / per-key checkbox, "Toggle Not available"); quadrant fills → `var(--quad-*)`; bubble counts → `var(--on-accent)`; row labels get a `paint-order: stroke` halo; copy fix — "11 plotteds / totals" → "11 of 11 groups plotted" and "11 of 11 groups", noun now mode-aware (`ticker`/`group`).
- `app/web/src/pages/MasterGroupTable.tsx` — **P2-2**: sector catalogue search now also matches constituent ticker and name, so `?taxonomy=SECTOR&filter=BBCA` returns the *Financials* row instead of an empty table.
- `app/web/src/pages/GroupExplorer.tsx` — **P2-3**: sector chart period is read from and written back to `?period=` (`setSectorPeriod` deletes the param for `ALL`), wired through `initialRange`/`onRangeChange`.
- `app/web/src/components/AppShell.tsx` — **P2-1**: workspace separator `var(--line)` → `var(--muted)`; tooltip `color:#fff` → `var(--bg)`; status dot `#178477` retained (graphical, ≥3:1).
- `app/web/src/components/MarketHeatmap.tsx` — `colorFor` restored to a fixed, theme-independent data palette (a tokenize pass had collapsed IMPROVING and WEAKENING into one token); tile text now uses a computed `inkOn()` that picks the max-contrast near-black vs white, guaranteeing ≥4.58:1 on every cell.
- `app/web/src/components/TaxonomyMap.tsx` — plot `<rect>` `#ffffff` → `var(--surface)`; quadrant annotations de-opacified and `#178477` → `var(--up)`; bubble counts → `var(--on-accent)`; hover tooltip fixed to `#121619` / `#ffffff` / `#b8bdc0` (a dark tooltip must not follow the theme); `colorFor` `#178477` → `var(--up)`.
- `app/web/src/pages/WhatChanged.tsx` — scatter quadrant fills `#fafaf8`/`#f6f8f8`/`#f9f7f5` → `var(--surface-subtle)`/`var(--tint-note)`/`var(--tint-cream)`; `#778089` labels → `var(--muted)`; `#178477` status text → `var(--up)`; `#f26a3d` arrows → `var(--accent-ink)`; `#16191c` rules → `var(--ink)`.
- `app/web/src/pages/PublicHome.tsx` — hardcoded dark panels keep **fixed** on-dark colours (they are dark in both themes); accent-as-text `#f26a3d`/`#178477` → `var(--accent-ink)`/`var(--up)`; narrow-leadership dot highlight `var(--link)` → `#7fb0d8` (it sits on `#121619` in *light* mode too).
- `app/web/src/components/{SnapshotNotices,OfficialMarketContext,IDXStatisticsRelease,IDXDailyStatistics,ForeignFlowSample,PriceChart,ThemesExplorer}.tsx` — remaining hardcoded tint / status / surface literals converted to tokens; `NET_BUY` colour helper now returns `var(--up)` so it clears 4.5:1 as text in both themes.

## Changed files (prior work package, base `2c81894`)

- `app/web/src/data/catalogFocus.ts` (new) — session-scoped catalog↔detail handoff: `rememberCatalogFocus` / `peek` / `take` / `clear`, `rememberCatalogUrl`, `catalogHref`. Single owner of the `catalog-url` and `catalog-focus` session keys, shared by the catalog and the detail view so the back path is the same in both directions.
- `app/web/src/pages/GroupExplorer.tsx` — unified detail/comparison surface for both the sector detail path and the taxonomy detail path: catalog back link (`CatalogBackLink`), shareable `?group=`/`?compare=`/`?period=` URL state, coverage-notes block, `MembershipTable` (search + sort by ticker/membership/confidence/source date, `Relationship` column that renders **"Unresolved"** when the snapshot carries no subtype), `LeadersLaggards` (YTD-excess primary, 20D fallback, top-5/bottom-5, states which period was used), price chart with period tabs, `ComparisonPanel` + `ComparableGroup` (shared `?compare=` table, no derived cross-group diffs), and membership-evidence / relationship-provenance notes. Local `rememberCatalogFocus`/`catalogHref` moved to `data/catalogFocus.ts`.
- `app/web/src/pages/MasterGroupTable.tsx` — uses `rememberCatalogUrl`/`peekCatalogFocus`/`clearCatalogFocus`; writes `catalog-focus` on every catalog row click (taxonomy `Open →`, sector group name) and on heatmap drill-down so **browser Back** restores focus, not only the in-app back link; `data-group-id` anchors; `Browse catalog →` header links (`/konglo`, `/themes`).
- `app/web/src/components/PriceChart.tsx` — `ChartRange` widened to `1M|3M|6M|1Y|YTD|2Y|5Y|ALL`; exported `CHART_PERIODS` and `periodDisabledReason()` (reason text names the 90-day snapshot history and repeats the Sectors API hold); every period rendered as a tab with `aria-disabled` + `title` reason; unavailable-requested-period notice banner; optional `initialRange` / `onRangeChange` props (backwards compatible; existing callers untouched).
- `app/web/src/pages/ThemesExplorer.tsx` — rewritten as the dual Themes/Konglo catalog: path is canonical (`/themes`, `/konglo`), `?taxonomy=`/`?group=`/`?filter=` accepted as legacy input, group-name/code/**ticker** search across memberships, semantic `<Link>` rows with `aria-current`, catalog summary panel (20D/60D excess, Breadth, Δ Breadth, concentration, leadership/diffusion/data chips, coverage, membership breakdown, membership evidence, definition/version block, foreign-flow sample), `Open full detail →` / `Rotation →` / `Table · heatmap ↗` / `Map view ↗` links, responsive `themes-browser-grid` / `themes-detail-metrics` classes.
- `app/web/src/App.tsx` — route `{ path: "/konglo", Component: ThemesExplorer }`.
- `app/web/src/components/AppShell.tsx` — nav entry `Konglo Catalog` (`MixIcon`) so the rail has an 11th distinct destination with its own active state.
- `app/web/src/pages/TaxonomyMapPage.tsx` — header links to the catalog and to rotation (the `Switch to …` link alone left one side unreachable).
- `app/web/src/data/snapshot.ts` — optional `relationship` / `relationship_as_of` / `relationship_source` on `TaxonomyMembershipData` (schema-optional; absent today).
- `app/web/src/data/adapter.ts` — passes the optional relationship fields through unchanged.
- `app/web/src/pages/MarketOverview.tsx` — copy fix: "YTD is null in this bundle" → "YTD is **not available** in this bundle" (no raw `null` in user-facing prose).

## Requirement matrix

| Requirement | Status | Evidence |
| --- | --- | --- |
| **P2-1** dark mode is readable, header does not go white | DONE | Regression `dark-mode-header-contrast`: `dark=true`, `headerBg=rgb(26,32,38)`, `whiteHeader=false`, home link **13.94:1**, separator **6.48:1** |
| **P2-2** sector catalogue ticker search returns a row | DONE | Regression `sector-ticker-search`: `?taxonomy=SECTOR&filter=BBCA` → 1 row `["Financials"]` |
| **P2-3** sector chart period is shareable and restored from the URL | DONE | Regression `sector-period-url`: `?period=1M` restores 1M; click 3M → `?taxonomy=SECTOR&group=Energy&period=3M` + selected `3M`; click ALL → `period` removed |
| **P2-4** rotation diagnostic mode lets the reader hide the unavailable series | DONE | Regression `rotation-diagnostic-visibility`: 1 checkbox `Toggle Not available`, circles 11 → 0 → 11 |
| WCAG contrast across light **and** dark, desktop **and** mobile | DONE | `contrast.js`: **0 findings over 19 routes × 2 themes × 2 viewports = 76 audits** (started at 4,100) |
| Shell: icon rail, collapsed tooltips, expanded labels, brand home, search Enter/arrow/Escape, no-results, detail routes, dedup names, Escape/focus/scroll-lock, all destinations reachable | DONE | AppShell rail; QC `rail-expanded-labels` (11 links / 11 labels), `rail-tooltip` (collapsed → "Leadership Map"), `rail-collapse` (60 → 208px), `mobile-nav` (11 links, 1 menu control); `header-search` (combobox, 8 options, Escape closes list and keeps focus) |
| Overview: 3 cards 44/28/28, tablet reflow, mobile stack, concise timestamps + expandable provenance, single stale badge | DONE | MarketOverview; QC `stale-badge-and-provenance` (partial-coverage + `<details>` + "Data as of" + no "Today") |
| Movers use valid return/excess, stated period, eligible count; no index-point attribution | DONE | 20D excess vs IHSG + "265 eligible sector constituents · not index-point attribution" |
| Rankings use existing metrics, selector, drill-down; breadth is not advancers/decliners | DONE | `rankKind` selector + note |
| Overview/Market/Flow/Structure tabs with actual content; research separate; no portfolio/auth/alerts/payments | DONE | QC `flow-65-review-gate`: Flow panel renders 4/4 criteria, `signal eligibility: Review`, `Met` + `Review` flags and a mapped-coverage % |
| Ticker chart snapshot-backed multi-point; TradingView separate; autosize; no 8s timeout; honest failures | DONE (preserved) | QC `tradingview-mounted-and-fits`: still mounted after **9s**, iframe 1082×560 inside parent 1082×560 |
| Catalog table/heatmap switch; parent category + name/code; group/ticker search; member sorting; unique vs eligible; rotation link; URL state | DONE | QC `catalog-search` (`filter=coal` → 1 row) + `catalog-url` (`/groups?taxonomy=THEMES&filter=coal`) |
| Themes metadata via bounded research; secondary membership searchable | PARTIAL | Secondary membership is searchable by ticker through memberships; full theme definitions/exclusion criteria/version metadata need bounded primary-source research (0 search/parser runs this cycle, ceilings 5/package, 20/provider) |
| Konglo catalog consistent with Themes; relationship/source/type/date; unsourced stays unresolved | PARTIAL | `Relationship` column is present in both detail paths and renders **"Unresolved"** when the snapshot has no subtype (verified: the bundle carries no relationship field anywhere); new filing research not run this cycle |
| Treemap via Recharts/SVG; legend, tooltip/detail clicks, table alternative; metric agreement; member-count sizing labeled; neutral — | PARTIAL | Heatmap + table agreement present and gated; dedicated parent–child treemap not built (heatmap remains the agreed interim) |
| **Group detail**: name/code, complete membership table + chips, search/sort, relationship/source/type/date, eligible/total, price chart vs benchmark, leaders/laggards, comparison selector, coverage notes; every ticker opens `/ticker/:ticker` incl. missing histories; shareable group/period URLs; close returns + restores focus | DONE | QC `detail-open` (KONGLO_ASTRA → `h1 "Astra / Jardine ecosystem"`), `comparison` (6 options, 76 metric rows, `compare` in URL), `focus-restore` (`<A data-group-id=KONGLO_ASTRA>`), regression `keyboard-detail-and-focus` (Enter → Back restores `THEME_INFRASTRUCTURE`), `period-disabled-reason` (5 disabled tabs with reason) |
| Reuse `GroupExplorer`/`PriceChart`; no second detail view | DONE | Single detail component for sector + taxonomy paths; `PriceChart` reused |
| Pipeline history policy; equal-weight MVP; no browser-built indices | DONE | `taxonomyGroupPriceHistory` built by `buildTaxonomyGroupPriceSeries` in the adapter (equal-weight mean of persisted ticker histories); nothing computed in the browser |
| Periods gated with explanations; no interpolation | DONE | `periodDisabledReason()` per tab + banner; all ranges still point at persisted snapshot prices only |
| Metrics require common dates/minimum observations; excess is percentage points | DONE (preserved) | Existing `rotation.ts` / adapter formulas untouched |
| Unified rotation tabs + URLs; table, counts, groups/stocks, search, toggles, hover/focus, zoom/reset/fullscreen, detail nav; counts equal plotted | DONE (preserved) | RotationView |
| Intervals/tails change real dated series; consistent versions; no fake trails | DONE (honest gating) | Disabled with explanations; formulas unchanged |
| Macro + Global conditional MVPs or typed contract + receipts | DONE (contract) | `macroContract` + `globalMarketsContract`; no nav additions |
| Design system: selective Radix; Radix Icons single family; General Sans + Geist Mono; logo preserved; references as refs | DONE | 2 Radix packages; verified icon exports; Fontshare import + license note |
| No Sectors calls; ledger/ceilings; cached originals; coherent schemas; no fabricated metrics | DONE | QC `offline-data`: 4 XHR/fetch total across 13 routes, **all under `/snapshots/` or `/idx/`**; 0 unexpected external hosts |

## Design decisions / dependencies / licenses

- `@radix-ui/react-icons` + `@radix-ui/react-tooltip`: official Radix packages, MIT, named imports, tree-shaken. Rationale: rail tooltips and a single icon family per `DESIGN_SELECTIONS`.
- General Sans: Fontshare **Closed Source** (not SIL OFL); CDN import for this iteration. Retain the downloaded family license before self-hosting a WOFF2 subset. Geist Mono + system fallbacks retained.
- No Motion, no Base UI/React Aria, no Lucide/Tabler, no Next.js, no backend or chart-stack replacement.
- Dark mode uses real tokens; charts/iframes are no longer inverted.
- Relationship subtype is **never inferred**. Absent evidence renders "Unresolved" — job titles and similar names are not treated as legal control.

## Commands / results / warnings

- `npm run typecheck --prefix app/web` — clean (`tsc -b --noEmit`, no output).
- `npm run build --prefix app/web` — green in ~595ms (deterministic across repeated runs). `dist/index.html` 0.81 kB; CSS `index-*.css` 30.32 kB (gzip 7.59 kB); JS `index-*.js` **1,066.99 kB** (gzip 302.65 kB); map 4,935.27 kB. The pre-existing single-chunk (>500 kB) warning is **retained, not concealed**.
- `git diff --check` — clean.
- Backend/pytest **not** rerun (no Python/schema/exporter/calculation changes). The 729-test baseline from the earlier audit is **not** reported as current.
- Browser QC (Playwright driving installed Google Chrome, temp harness outside the repo): **77 PASS / 1 INFO / 0 FAIL**, **0 console or page errors**.
  - Geometry: 13 routes × 5 viewports (1440×900, 1368×858, 1291×858, 768×1024, 390×844) = **65/65 PASS**; `documentElement.scrollWidth === clientWidth` and workspace `scrollWidth === clientWidth` on every route; zero-sized charts 0.
  - Interaction: 12 PASS + 1 INFO (dark-theme token swap confirmed, body background `rgb(18, 22, 25)`).
  - Regression: **13/13 PASS** — `no-broken-value-tokens`, `ammn-61-21` (ALL=61, 1M=21), `tradingview-mounted-and-fits`, `stale-badge-and-provenance`, `flow-65-review-gate`, `top3-formatting`, `local-profile`, `keyboard-detail-and-focus`, `sector-ticker-search`, `sector-period-url`, `rotation-diagnostic-visibility`, `dark-mode-header-contrast`, `no-page-errors`.
- **WCAG contrast audit — 0 findings.** Scope widened to 19 routes × light/dark × 1440×900/390×844 = **76 audits**, `{"total":0,"byTheme":{"light":0,"dark":0},"unique":0}`.
  - The audit models SVG `fill` as the text colour with the smallest containing SVG shape as the background, honours `paint-order: stroke` halos (the outline colour becomes the effective background), applies the 3.0 large-text threshold, exempts `disabled`/`aria-disabled`, and resolves `background-clip: text` by reading the **last gradient stop** (the sweep ends `animation-fill-mode: forwards` at `background-position: 100%`, so that is the colour readers land on).
  - Trajectory this round: 4,100 → 272 → 76 → 8 → **0**.
  - `--link` was referenced at 14 call sites and **never declared**; it resolved to `unset`, which meant SVG `fill` silently fell back to black. Declaring it (`#1849a9` light / `#7fb0d8` dark) was both a correctness fix and the last dark-mode contrast failure.
- 92 screenshots written to the harness `shots/` directory (geometry set, detail/catalog set, `fresh-*` theme pairs, `qc-*` contrast pair set, plus regression evidence: `dark-header-overview-1440x900.png`, `rotation-diagnostic-toggles-1440x900.png`, `profile-dialog-1440x900.png`, `ticker-AMMN-1440x900-after-9s.png`). Stale `dark-contrast-*.png` captures from failing passes were **deleted** so no outdated evidence remains.

## Known issues

1. Treemap parent–child view not built; heatmap + accessible table remains the interim (PARTIAL above).
2. Theme/Konglo bounded filing research not run — no new You.com/Tavily/LlamaParse calls this cycle (ceilings 5/package, 20/provider, 2/10/20 parser pages unused).
3. Snapshot carries no relationship subtype for any membership, so every `Relationship` cell is "Unresolved" until the taxonomy enrichment lands; the UI is ready to display it when present.
4. SPA bundle remains a single chunk (1,066.99 kB); code-split candidate from the earlier audit is still open. This round added ~24 kB of source.
5. Theme/Konglo definition, exclusion-criteria, and version metadata still come from the taxonomy config rather than bounded primary-source research.
6. The homepage headline `DiaTextReveal` sweeps through `#a8afb2`/`#f26a3d`/`#438b82` for ~1.5s before settling on `endColor`. The audit measures the **resting** stop (high contrast); the transient mid-sweep frames of a decorative reveal are below 3.0 on white. Recorded as accepted, not silently dropped — if a strict frame-by-frame audit is required, the sweep stops must be darkened.

## UI vs release verdicts

- **UI polish:** the four user-confirmed P2 defects are **fixed and browser-verified**, and the WCAG contrast audit reports **0 findings across 76 audits** (light + dark, desktop + mobile, 19 routes). Core P1–P3 acceptance remains verified across all five required viewports (65/65 geometry, 12/12 interaction, 13/13 regression, 0 console errors). Remaining PARTIALs are treemap and Theme/Konglo source research, not UI mechanics.
- **Release readiness: HOLD.** The bundle stays `complete=false`, YTD has no prior-year baseline, diffusion stays UNCONFIRMED/INCOMPARABLE for most groups, and foreign flow fails the 65% gate (`signal eligibility: Review`). Visual work does not change any data gate.
