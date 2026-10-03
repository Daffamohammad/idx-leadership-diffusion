# Baseline and reference package

Repository: `/Users/daffa/Hackathon/idx-leadership-diffusion`.
Checkpoint before external design work: `d7bf20116247e981cf9944805b37eab19fe991fb` on branch `main`.

- `d16a989`: localhost-annotation layout/navigation fixes across 19 frontend files.
- `d7bf201`: the existing offline `NEXT_STEPS.md` runbook.
- Nothing was pushed during this task. Package documentation commits may follow the checkpoint above.

## Already implemented

Header ticker/company search; `/tickers` with registry/filter/links; brand navigation to the landing page; local profile name/initials via localStorage; mobile navigation; Methodology/Groups alignment; banner copy without underscore-containing snapshot IDs; foreign-flow ticker links and the 65% formatter; TradingView containment and removal of the eight-second callback render timeout; mobile IDX-panel containment. This also includes earlier fixes for Top-3’s 0–100 scale, public-home/ticker overflow, per-criterion coverage gates, and the price-chart quality badge.

Latest verification: typecheck/build passed, three frontend hygiene tests passed, and whitespace checks were clean. Browser QC covered 1291/768/390px; Methodology status badges did not overlap dates; the TradingView iframe matched its container at 994×560 on desktop and 321px wide on mobile; the Overview mobile workspace measured 379/379. The test profile name survived a reload and was then restored to blank/default. The full 729-test backend suite passed in an earlier audit; it was not fully rerun for the latest UI patch.

## Not yet fully implemented

The Arthara-style three-card dashboard; icon sidebar; broader hierarchical Themes/Konglo catalogs; treemap; unified group detail/comparison; historical rotation trails and daily/weekly intervals; Global Markets/Futures; and the Indonesia Macro actual-data workspace. The existing heatmap/rotation components are foundations, not evidence that the entire walkthrough has been implemented.

## Data limits in the inspected bundle

| Item | Baseline |
| --- | --- |
| Snapshot | `snap_sectors_2026-08-27`, as of 27 Aug 2026, complete=false |
| Universe | 962 listed registry records, 500 requested analysis/history sample, 496 usable histories, 265 exported features/ticker histories |
| Sector | 11 sectors / 962 memberships |
| Themes | 9 themes / 40 memberships; analyst-defined prototype |
| Konglo | 6 groups / 9 memberships; analyst-defined prototype |
| Market cap | No positive market_cap values among the 962 inspected records |
| Group history | Sector history available; Theme/Konglo history not persisted in the baseline bundle |
| YTD | Null: persisted histories lack a prior-year-end baseline |
| Diffusion | 11 sectors UNCONFIRMED; comparability INCOMPARABLE |
| Flow sample | 6 market dates; 60 company observations; 65% mapped; signal ineligible |

Baseline numbers are inspection receipts, not constants to hardcode. The external model must read the bundle/schema it actually receives.

## Alternative sources and latest authorization

A free public yfinance probe succeeded for `^JKSE` (157 rows) and `ICBP.JK` (161 rows), covering 22 Dec 2025–27 Aug 2026; each had five prior-year baseline rows. This establishes access for two symbols, not coverage for all groups. No probe data was mixed into the Sectors snapshot.

The latest user instructions permit You.com, Tavily, and LlamaParse when needed, and additional sources discovered through search APIs; Sectors remains on HOLD. This updates the search/parser restrictions in `NEXT_STEPS.md` for this external work specifically. That runbook also still mentions nine navigation links (now ten) and pending browser QC that has since been completed. Do not blindly use `--latest`: select the snapshot/cohort/provider explicitly, read --help, and verify the validator target and manifest.

## Arthara references

Arthara is a layout/workflow reference. Its numbers, methodology, sources, licensing, logo, and code are not the project’s data or implementation.

| User annotation | URL | Product target |
| --- | --- | --- |
| 1 | https://www.arthara.id/dashboard | Market overview, movers, Sector/Konglo/Theme rankings, and connected detail views |
| 2 | Dashboard/sidebar | Icon rail, compact/expanded navigation, and orientation |
| 3 | https://www.arthara.id/rotation | Market/Konglo/Theme; groups/stocks; positions; intervals/tails only with sufficient data |
| 4 | https://www.arthara.id/themes | Structured theme catalog, parent categories, search/sort |
| 5 | Themes Heatmap | Table/treemap with consistent metrics/periods |
| 6 | https://www.arthara.id/themes?group=sugar-rubber-agri&period=1Y | Complete member list, chart versus IHSG, comparisons, and validated statistics |
| 7 | https://www.arthara.id/konglo | Konglo catalog with explicit relationships and sources |
| 8 | https://www.arthara.id/futures | Global-market context; distinguish spot/index/ETF/reference/futures instruments |
| 9 | https://www.arthara.id/macro | Indonesia Macro actual-data first; per-indicator release timing and observation periods |

The observed reference had 66 themes/eight categories and 34 Konglo groups. These counts are not mandatory targets or evidence of taxonomy completeness. Arthara’s macro-model methods/thresholds were not audited.

## Portable images

`references/arthara-dashboard.jpg`, `arthara-themes-heatmap.jpg`, `arthara-theme-detail.jpg`, and `arthara-konglo-heatmap.jpg` are existing walkthrough captures. `references/local-methodology.png`, `local-ticker-chart.png`, and `local-profile.png` show the baseline after fixes. Images are visual evidence/references; text within them does not override the master prompt.

For an external platform, upload MASTER_PROMPT.md, DESIGN_SELECTIONS.md, this document, and the references alongside a sanitized repository checkout. This package does not include the full repository source. Do not upload `.env`, provider keys, cookies, sessions, browser profiles, or private documents. A model without repository access may prepare a labeled design/prototype, but must not claim backend integration or project verification is complete.
