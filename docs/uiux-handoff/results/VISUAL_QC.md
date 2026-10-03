# VISUAL_QC — status UNVERIFIED in this environment

No Chromium/Playwright was available (`which chromium` empty; `import playwright` missing),
so console errors, screenshots, and geometry measurements were not captured here.
Build and typecheck pass; CSS guards against page-level overflow. A real browser run
is required before claiming visual acceptance.

## Reproduction

1. `npm run dev --prefix app/web` (or serve `app/web/dist` after `npm run build --prefix app/web`).
2. Open routes: `/overview`, `/map?taxonomy=SECTOR`, `/map?taxonomy=KONGLO&mode=stocks`,
   `/groups?taxonomy=THEMES&view=heatmap`, `/explorer?taxonomy=SECTOR&group=<id>`,
   `/ticker/<TICKER>`, `/methodology`.
3. Viewports: 1440×900, 1368×858, 768×1024, 390×844, 1291×858. Themes: light + dark.
4. Checks per MASTER_PROMPT §7:
   - `document.documentElement.scrollWidth === document.documentElement.clientWidth`.
   - Workspace `scrollWidth <= clientWidth`; tables/charts use labeled local scroll only.
   - No `overflow-x:hidden` hiding controls/data (repo uses `overflow-x:clip` on root only).
   - Rail icon names/tooltips, active routes, mobile menu, Home, search Enter/arrow/Escape,
     no-results, local-profile persistence, keyboard/Escape/focus restoration, modal resize.
   - Three desktop cards + mobile stack; timeframe/source/eligible counts; mover/group links;
     no intraday, index-point attribution, or current-market claims for old data.
   - Catalog search/sort; unique member counts; table/heatmap agreement; cross-membership note;
     empty/null states with —.
   - Detail member links incl. missing histories; common benchmark dates; eligible periods;
     close/deep-link/query state (`/groups?taxonomy=`, `/map?taxonomy=&q=&mode=`,
     `/explorer?taxonomy=&group=`).
   - Rotation primary-axis formulas preserved; diagnostic mode honest; plot/table/distribution
     counts match (`Plotted X of Y`); tails/intervals gated with reasons.
   - Regression: Top-3 100/94.24/null → 100%/94%/—; flow 65% Review + flags; TradingView
     mounted beyond old timeout and fits container; profile storage/focus.
   - Polish: real light/dark tokens (no global inversion); keyboard/focus/touch ≥44px mobile;
     tabular right-aligned numbers; reduced-motion respected; loading/error/empty states.

## Screenshots (to capture)

- `overview-1440-light.png`, `overview-390-light.png`, `overview-1440-dark.png`
- `rotation-1440.png` (`/map?taxonomy=SECTOR`), `rotation-stocks-1440.png` (`&mode=stocks`)
- `catalog-heatmap-1440.png` (`/groups?taxonomy=THEMES&view=heatmap`)
- `detail-1440.png` (`/explorer?taxonomy=THEMES&group=<id>`)
- Record route, viewport, commit, theme, document/workspace widths, chart/iframe bounds.

Screenshots alone do not establish a live feed or passing behavior in every state.
