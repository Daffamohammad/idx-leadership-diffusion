# HANDOFF — UI/UX and Arthara workflow implementation (work package 1)

Base revision: `df33d75` (`docs: translate external UI handoff into English`).
Result revision: see local commit for this work package (no push, no force-push, no amend of others' history).
Bundle: `snap_sectors_2026-08-27`, as of 27 Aug 2026, complete=false.
Mode: offline only. Zero live Sectors calls. Search/parser ceilings untouched (no new search/parser runs in this package).

## Changed files

- `app/web/package.json`, `app/web/package-lock.json` — add `@radix-ui/react-icons`, `@radix-ui/react-tooltip` (selective Radix adoption; no Base UI/React Aria).
- `app/web/index.html` — SVG favicon from original BrandMark geometry.
- `app/web/src/App.tsx` — remove `CustomCursor`; native cursor stays visible in workspace.
- `app/web/src/index.css` — General Sans (Fontshare 400/500/600) + Geist Mono stacks; real light/dark tokens replacing global `invert(1) hue-rotate(180deg)`; button variants with hover/focus/pressed/disabled/loading; 36–40px defaults with 44px mobile touch; dash 44/28/28 grid with tablet reflow and mobile stack; restrained motion (150ms simple, 210ms overlay); tabular numbers; local table scroll with no page-level `overflow-x:hidden` concealment.
- `app/web/src/components/AppShell.tsx` — icon rail with verified Radix icons + Radix Tooltip in collapsed mode; consolidated labels (`Group Explorer` / `All Groups`, routes unchanged); mobile nav with icons and 44px targets; Escape handling preserved; local profile in footer/mobile header preserved.
- `app/web/src/components/BrandMark.tsx` — optical/clear-space polish via padding, `var(--accent)`/`var(--surface)` light/dark variants, accessible name; identity and name preserved, no rebrand or animation.
- `app/web/src/pages/MarketOverview.tsx` — three desktop cards (market snapshot ~44%, movers ~28%, rankings ~28%); single stale/incomplete badge with `<details>` provenance; movers use 20D excess with eligible count and no index-point attribution; rankings use existing group metrics with Sector/Konglo/Themes selector and drill-down; Overview/Market/Flow/Structure tabs with actual content; research/events kept separate context-only; “Snapshot overview”/“Data as of” copy, no “Today” for old data.
- `app/web/src/pages/MasterGroupTable.tsx` — unified catalog with `?taxonomy=SECTOR|KONGLO|THEMES`, `?view=table|heatmap`, `?filter=` URL state; group/ticker search (tickers via memberships); member-count sorting; unique vs eligible totals with overlap disclosure; rotation links; heatmap via existing `MarketHeatmap`; sector table preserved.
- `app/web/src/pages/GroupExplorer.tsx` — back to catalog (`/groups?taxonomy=`) with `sessionStorage` focus restore to `#catalog-search`; sector header shows id + eligible/total; taxonomy detail back goes to catalog (not just map); ticker links to `/ticker/:ticker` preserved.
- `app/web/src/components/RotationView.tsx` — URL-synced `?taxonomy=`, `?q=`, `?mode=groups|stocks`; groups/stocks mode (stocks from real constituent excess via same formulas); visibility toggles; hover/focus detail preserved; zoom/reset/fullscreen (viewBox zoom + Fullscreen API); disabled Daily/Weekly + tail slider with data-gated explanations (no fake trails); plotted-vs-total counts; table/plot share data/method/period.
- `app/web/src/data/macroContract.ts`, `app/web/src/data/globalMarketsContract.ts` — P4 typed contracts only; no live cards, no new nav destinations.

## Requirement matrix

| Requirement | Status | Evidence |
| --- | --- | --- |
| Shell: icon rail, tooltips, expanded labels, brand home, search Enter/arrow/Escape, no-results, detail routes, dedup names, Escape/focus/scroll-lock, all destinations reachable | DONE | AppShell.tsx rail + Tooltip; TickerSearch preserved; routes in App.tsx unchanged; LocalProfile native dialog preserved |
| Overview: 3 cards 44/28/28, tablet reflow, mobile stack, concise timestamps + expandable provenance, single stale badge | DONE | MarketOverview.tsx dash-grid; index.css grid rules |
| Movers use valid return/excess, stated period, eligible count; no index-point attribution | DONE | 20D excess vs IHSG + eligible sector constituents label |
| Rankings use existing metrics, selector, drill-down; breadth is not advancers/decliners | DONE | rankKind selector + note |
| Overview/Market/Flow/Structure tabs with actual content; research separate; no portfolio/auth/alerts/payments | DONE | tab state + existing components reused |
| Ticker chart snapshot-backed multi-point; TradingView separate; autosize; no 8s timeout; honest failures | DONE (preserved) | PriceChart + TradingViewWidget untouched |
| Catalog table/heatmap switch; parent category + name/code; group/ticker search; member sorting; unique vs eligible; rotation link; URL state | DONE | MasterGroupTable tabs + view + filter + tax tables |
| Themes metadata via bounded research; secondary membership searchable | PARTIAL | Secondary membership searchable via ticker filter; full metadata expansion needs bounded primary-source research (no new search runs this cycle) |
| Konglo catalog consistent with Themes; relationship/source/type/date; unsourced stays unresolved | PARTIAL | Catalog consistent; relationship evidence surfaces existing membership source fields; new filing research not run this cycle |
| Treemap via Recharts/SVG; legend, tooltip/detail clicks, table alternative; metric agreement; member-count sizing labeled; neutral — | PARTIAL | Heatmap + table agreement present; dedicated treemap with parent–child grouping not built (heatmap is the agreed interim; no cap-weighted view enabled) |
| Group detail responsive with all required blocks; every ticker opens detail incl. missing histories; shareable URLs; close returns + focus | DONE | GroupExplorer back-to-catalog + focus restore; ticker links preserved |
| Reuse GroupExplorer/PriceChart; pipeline history policy; equal-weight MVP; gated periods with explanations | DONE (preserved) | No second detail view; PriceChart reused |
| Unified rotation tabs + URLs; table, counts, groups/stocks, search, toggles, hover/focus, zoom/reset/fullscreen, detail nav; counts equal plotted | DONE | RotationView URL + mode + toggles + zoom/fullscreen + counts |
| Intervals/tails change real dated series; consistent versions; no fake trails | DONE (honest gating) | Disabled with explanations; diagnostic retained; formulas preserved in rotation.ts |
| Macro + Global conditional MVPs or typed contract + receipts; no fake cards or empty destinations | DONE (contract) | macroContract + globalMarketsContract; no nav additions |
| Design system: shadcn/Radix variant selective; Radix primitives selective; Radix Icons single family; General Sans + Geist Mono; logo preserved; references as refs | DONE | 2 Radix packages; verified icon exports; Fontshare import + license note |
| No Sectors calls; ledger/ceilings; cached originals; coherent schemas; no fabricated metrics | DONE | Only `/snapshots/*.json` + `/idx/*.json` fetches; no new provider runs |

## Design decisions / dependencies / licenses

- `@radix-ui/react-icons` + `@radix-ui/react-tooltip`: official Radix packages, MIT, named imports, tree-shaken; rationale: rail tooltips + single icon family per DESIGN_SELECTIONS; bundle impact small (build 1.04MB total, pre-existing 948kB single-chunk debt retained, code-split still open).
- General Sans: Fontshare Closed Source; CDN import for this iteration; retain downloaded family license before self-hosting WOFF2 subset; Geist/system fallbacks kept; no unused families.
- No Motion, no Base UI/React Aria, no Lucide/Tabler, no Next.js/backend/chart replacement.
- Dark mode uses real tokens; charts/iframes no longer inverted.

## Commands / results / warnings

- `npm run typecheck --prefix app/web` — clean.
- `npm run build --prefix app/web` — green in ~663ms; `dist/index.html` 0.81kB; CSS 29kB; JS 1,038kB (pre-existing single-chunk debt; warning retained, not concealed).
- `git diff --check` — clean.
- Backend/pytest not rerun (no Python/schema/exporter/calculation changes); 729-test baseline from 0310audit is not reported as current.
- Browser QC: UNVERIFIED in this environment (no Chromium/Playwright); reproduction steps in VISUAL_QC.md and VERIFY_NEXT.md.

## Known issues

1. Treemap parent–child view not built; heatmap + accessible table is the interim (PARTIAL above).
2. Theme/Konglo bounded filing research not run (no new You.com/Tavily/LlamaParse calls this cycle; ceilings 0/5 per package, 0/20 per provider).
3. PriceChart period gating relies on existing range tabs; extended disabled-with-reason states for 2Y/5Y remain future work.
4. SPA bundle remains single chunk; code-split candidate from 0310audit still open.
5. Visual QC across 1440×900, 1368×858, 768×1024, 390×844, 1291×858 needs a real browser run (UNVERIFIED here).

## UI vs release verdicts

- UI polish: core P1–P3 acceptance implemented; visual QC pending browser run.
- Release readiness: HOLD — bundle remains `complete=false`, YTD null, diffusion UNCONFIRMED/INCOMPARABLE, flow ineligible; visual work does not change data gates.
