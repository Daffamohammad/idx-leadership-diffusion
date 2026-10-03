# VERIFY_NEXT — independent sequence for Codex

1. **Inspect the diff**
   - `git log --oneline -6`, `git show --stat HEAD`, `git diff ed6fd61..HEAD --check`.
   - Confirm the touched surface is limited to `app/web/src/{data/catalogFocus.ts,data/snapshot.ts,data/adapter.ts,components/{AppShell,PriceChart}.tsx,pages/{App,GroupExplorer,MarketOverview,MasterGroupTable,TaxonomyMapPage,ThemesExplorer}.tsx}` plus this results directory.

2. **Validate sources / formulas / schemas**
   - No live calls: only `/snapshots/*.json` + `/idx/*.json` fetches; no Sectors/search/parser execution. Independently confirm by loading each route with the network panel open, or by re-running the `offline-data` assertion (expect ~4 XHR/fetch total, all under `/snapshots/` or `/idx/`).
   - `data/rotation.ts` formulas unchanged (X = YTD excess vs IHSG; Y = 20D − 60D); diagnostic fallback still uses documented 20D/60D without phase assignment.
   - Top-3 0–100 (`top3Label`), flow 65% gates, `complete=false`, 962/500/496/265 denominators shown in context; null never rendered as 0 and never as `null`.
   - `relationship` is optional end-to-end and **absent in the bundle**; UI must render "Unresolved" and must not infer control/subsidiary/affiliate. Verify no code path defaults it.
   - Equal-weight group history stays in `buildTaxonomyGroupPriceSeries` (adapter); no index math in components.

3. **Run checks**
   - `npm run typecheck --prefix app/web`
   - `npm run build --prefix app/web` (expect the pre-existing >500 kB single-chunk warning; do not conceal it)
   - `git diff --check`
   - If Python/schema/exporter/calculation changes are ever added, run relevant tests first, then `.venv/bin/python -m pytest -q`. Do **not** report the 729 baseline as current without rerunning.

4. **Browser walkthrough** — follow `VISUAL_QC.md`
   - Serve the built app on a **free port** and verify you are on the right app first: `curl -s http://127.0.0.1:<port>/ | head -3`. Port `4173` on this machine is an unrelated application.
   - Viewports 1440×900, 1368×858, 1291×858, 768×1024, 390×844; light + dark.
   - Assert `documentElement.scrollWidth === clientWidth` and workspace `scrollWidth ≤ clientWidth`; non-zero chart/iframe bounds; **0 console errors**.
   - Interaction: catalog search + URL state, open detail, comparison select, disabled-period reason, **focus restore via both the back link and browser Back**, header search Enter/arrow/Escape, rail collapse → tooltip → expand, mobile menu.
   - Regression §7: Top-3 formatting, flow 65% Review + flags, AMMN 61/21, partial badge, TradingView mounted after 9s and fitting its container, local-profile storage/focus.

5. **Polish remaining PARTIALs** (in this order)
   - Theme/Konglo bounded primary-source metadata (definitions, inclusion/exclusion, membership type, version, dated relationship subtype) within the 5/package and 20/provider ceilings — this also fills the currently-empty `Relationship` column.
   - Dedicated treemap with parent–child grouping (heatmap + table remains the agreed interim).
   - SPA code-split for the 1,060.82 kB chunk (measure before optimizing).
   - Extended period gating beyond 2Y/5Y already covered by `periodDisabledReason`.

6. **Keep verdicts separate**
   - UI polish ≠ release readiness. The bundle is still `complete=false` with YTD unavailable, diffusion UNCONFIRMED/INCOMPARABLE for most groups, and foreign flow failing the 65% gate (`signal eligibility: Review`). No visual change moves that to DONE.

Loop: reproduce defect → minimum affected code → rerun relevant checks → update screenshots/matrix → explain before/after. Do not reply "fixed" without patch + evidence. Mark anything unverified as UNVERIFIED with reproduction steps.
