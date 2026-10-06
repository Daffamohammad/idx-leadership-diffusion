# Submission annotation resolution

This checklist maps the supplied browser comments to the submission release UI. Desktop flows and mobile interactions were exercised against the locally served immutable release. A 390 px Chromium pass checked every submission route for loading failures, horizontal overflow, and rejected public status labels.

## Project and Arthara annotations

| Annotation | Resolution in the submission release | Evidence / verification |
|---|---|---|
| Methodology should expand in place | Methodology material is grouped in collapsed native disclosure panels. | `app/web/src/pages/Methodology.tsx`; desktop disclosure opened; keyboard path is covered by native `<details>` semantics. |
| Add navigation sub-groups | Sidebar uses Research, Map, Catalog, and Guide groups. | `app/web/src/components/AppShell.tsx`; desktop groups verified; 390 px route smoke passed. |
| Konglo map alignment | Konglo links resolve into the unified responsive rotation map; inspector follows the selected point. | `/maps/konglo` redirects to `/map?taxonomy=KONGLO&mode=groups`. |
| Themes map alignment and dense plot concern | The legacy dense scatter route redirects to the unified group map. IDXIC classification groups are displayed as a searchable catalog and a limited top-12 map. | `/maps/themes`, `/chart-demo`, and `/map?taxonomy=THEMES&mode=groups`. |
| Foreign flow should cover YTD | The selected release retains the complete verified official IDX daily series. Sectors' recorded YTD response omits four dates after a targeted check, so the page shows its complete Q3 series and keeps the exact YTD omissions inside Sources. | Foreign-flow page and `/recorded-sample`; see `SOURCE_AND_RECONCILIATION_EVIDENCE.md`. |
| What Changed repeats gaps instead of explaining results | The page leads with three short measured readings and the fixed-cohort historical replay; the comparison has five stated dates and an explicit current-membership basis. | `/what-changed`; `historical_comparison.json` in the selected package. |
| Arthara lists 34 Konglo groups | The release contains 32 documented Konglo groups with dated source relationships. Group counts follow local evidence; the displayed count is not made to match a third-party catalog. | Konglo source register and immutable catalog family; detail pages retain smaller groups. |
| Arthara lists 66 themes | The release keeps 102 IDXIC subindustries as classification detail. Curated themes are not represented as official IDXIC labels. | Themes catalog label “IDXIC Subindustries”; dated IDXIC capture and hierarchy included in package evidence. |
| Rotation chart is hard to read | Group map plots the selected taxonomy's endpoints and dated trails on padded axes, with separate colors, no point-number labels, 11 sectors, search, legend, table, and one inspector. | `/map`; desktop selection, legend, table, basket series, and group detail were exercised; 390 px route has no horizontal overflow. |
| Foreign flow differs (-108.7T vs -83T) | Official IDX remains the default YTD series. Sectors is labeled as its own IHSG endpoint; its full Q3 daily series is compared on the exact 64 shared dates. The partial YTD sum is not compared with full-period IDX YTD. | `SOURCE_AND_RECONCILIATION_EVIDENCE.md` and the Sources disclosure on `/recorded-sample`. |
| “Prototype” appears on the sector map | Submission-facing evidence labels describe observed release or documented classification; the UI does not use “Prototype” as a public status. | Overview, methodology, map, and What Changed. |
| “Unconfirmed” on What Changed | The submission displays the calculated weekly matched-cohort comparison. Leadership, diffusion, concentration, confirmation, and rotation remain separate measures. | `/what-changed`; the comparison's five weekly observations and hashes. |
| Text needs more space / pointer readability | The market read is reduced to three bullets. The selected group's complete name, path, and metrics are in a responsive inspector. | Desktop and 390 px mobile checks confirm the inspector follows the plot and fits the page width. |
| Add Market Breadth and an “At a glance” summary | Overview now includes official advancing/unchanged/declining counts, net advances, A/D ratio, advancing share, directional traded-value shares, Stock Summary activity, official turnover context, foreign-flow context and a fixed-cohort net-advances chart. | `/overview`; searchable linked constituent lists open from direction counts, and source/coverage details are expandable. |
| Overview widgets and technical analysis | The overview pairs the selected release's official close and history with the TradingView chart and technical-analysis link. If the third-party summary script does not load, the page keeps the direct link without an error-status card. | `/overview`; active desktop preview shows the local release metrics and breadth independently of the third-party widget. |
| Market Breadth: new highs and lows | Strict adjusted-close breaks are available for 5D, 20D and 60D with horizon-specific eligible denominators and searchable ticker links. | `/overview`; the 52-week tab is withheld because the validated price panel starts 15 Dec 2025. |
| Rotation map should be centred and visibly change by group/date | The map uses symmetric zero-centred domains, a dated weekly/daily replay, previous/next and play/pause controls, and four-interval trails. Selecting a group keeps the other displayed groups visible and updates the inspector/table to the same date. | `/map`; 21 dated daily observations from 4 Sep through 2 Oct 2026. |
| Konglo/theme constituents need more context | The inspector links each member to stock detail and shows captured relationship labels, source dates and supporting source links where available. | `/map?taxonomy=KONGLO`; source membership and relationship hashes are recorded in the release asset. |

## BandarMetrics references

| Reference | Applied resolution |
|---|---|
| Market Movers under IDX statistics | `/movers` is built from the official IDX Stock Summary and includes all seven 25-row rankings, filters, company/price fields, and share/IDR units. |
| Clean rotation chart | The unified `/map` uses four weekly intervals, responsive plot sizing, adaptive padded domains, a point inspector, and a readable legend. |
| Clear messages | What Changed uses a three-item market read and measured weekly-shift list. |
| Comparison view | Sector baskets are computed from the fixed contributors and displayed against IHSG with a dashed benchmark and a source/basis note. |

## Walkthrough checklist

- [x] Desktop: grouped navigation, Movers BLTZ search and board filter, and methodology disclosures.
- [x] Desktop: sector rotation point, legend, and table selection; Konglo search; IDXIC activity search; all three taxonomies render on the unified chart.
- [x] Desktop: 11-sector basket chart, dashed IHSG, selected basket series, and release-member list.
- [x] Desktop: official IDX YTD (−82.55351T), Q3 series, daily values, and source links.
- [x] Mobile at 390 × 844: ten routes loaded without horizontal overflow; menu, plot selection, below-plot inspector, member disclosure, mover search, foreign-flow source disclosure, methodology accordion, and refresh were exercised.
- [x] Release selection is hash-bound and page-pinned; automated publication/switch tests cover stale tabs and refresh onto the selected release.
- [x] Browser route navigation did not make paid Sectors calls; the persistent request ledger hash remained unchanged.
- [x] Submitted routes inspected contain no visible “Prototype”, “Unconfirmed”, or “Not Found” status copy.
- [x] Visible text sweep across What Changed, Movers, Recorded Sample, Foreign Flow, Ownership, sector/Konglo/theme maps, catalogs, methodology, ticker detail and heatmap found no “Prototype”, “Unconfirmed”, “Not Found”, or pending-state messages.
- [x] Recorded Sample shows the matched 64-session Q3 comparison and lists the four Sectors YTD omissions only after opening Sources.
- [x] Overview breadth counts, turnover/volume units, directional value denominator, official foreign-flow context and the available 5D/20D/60D highs/lows show their separate source scopes.
- [x] Rotation replay synchronizes chart endpoints, legend, table and inspector for weekly and daily dates; selecting one group does not hide the others on the map.
- [x] Konglo and curated-theme membership evidence is available in the inspector, with group membership counts kept separate from signal eligibility.
- [x] Mobile group table selection and keyboard activation of a native methodology disclosure.
- [x] Recorded walkthrough: 3:24 silent captioned local browser capture with an MP4 and WebVTT caption sidecar.
