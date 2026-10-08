# 0810 Audit — 2026-10-08

Repo: `idx-leadership-diffusion` · audited HEAD `d30ae04` ("Loop hero animation, italicize landing headers, fix overview widget crash") · fix HEAD `555a27a` ("Audit round fixes: ticker-set round trip, disjoint deltas, contributor floor, epsilon alignment, copy sanitizer, dead-file removal") · branch `codex/final-diffusion-repair`.
Mode: offline only. Zero live Sectors calls, zero paid data requests. Active release unchanged: `rel-64026e36d49733009fec952086fc95a3121a86efbb196b1c68d00fd6317f33d2` (manifest SHA-256 `98e2c260c9afae07ce2b1cb5b5436cda8bbff9978a0239d809d909183ad36e4f`); no data assets were rebuilt or re-published.

## 1. Findings and fixes (all verified)

### Calculation fixes (Python)
1. **Persistence round trip (HIGH)** — `_snapshots_to_df` / `_row_to_group_snapshot` in `src/idx_leadership/pipeline.py` and the row reader/exporter in `scripts/build_market_snapshot.py` now persist and restore `breadth_eligible_tickers` / `breadth_outperforming_tickers` as JSON-encoded string columns; legacy rows restore as empty sets. Round-trip regression added (`test_breadth_ticker_sets_survive_pipeline_round_trip`). Released assets predate this field; the next rebuild carries it.
2. **Disjoint-universe rule (MEDIUM)** — `aggregation/groups.py` now returns `breadth_delta = None` when the paired cohort is empty and both sides are non-empty (no comparable names), matching `transitions.py`; legacy share subtraction removed. Covered by `test_disjoint_universes_yield_no_breadth_delta`.
3. **Five-contributor leadership floor (MEDIUM)** — `classify_leadership` is now gated on `len(lead_frame) >= 5` in `aggregation/groups.py`, mirroring `build_sectors_analysis.py:492`; no silent fallback for small cohorts. Two pre-existing tests were rebuilt above the floor (`test_rank_groups_assigns_ranks`, `test_leadership_classification_uses_primary_20d_excess_return`) and `test_leadership_requires_five_shared_contributors` pins the floor. `taxonomy/aggregation.py` carries a scope note (outputs unchanged) so the two paths are documented as intentionally different.
4. **Oracle epsilon alignment (MEDIUM)** — signed-concentration stability epsilon aligned to `1e-9` in `pipeline.py:410`, `build_market_snapshot.py`, and `verify_sectors_analysis_oracle.py` (matching `config/methodology.yaml`).
5. **Empty-cohort concentration (MEDIUM)** — an empty return cohort at the concentration horizon now stays undefined instead of falling back to all group tickers; a stale ticker excluded from group returns can no longer leak back in through the price frame.
6. **YTD-in-contract (MEDIUM)** — `rotation_replay.py` segment contract now excludes YTD contributors, so a YTD-only cohort change cannot split 20D/60D trail continuity. The fingerprint logic is extracted to `segment_contract()` and covered by `test_segment_contract_ignores_ytd_only_contributor_changes`.
7. **Low items** — horizon-column fallback for the concentration cohort (`groups.py`); finite-value guard in `verify_final_reading_oracle.py` `phase()`; unpaired-breadth scope note in `taxonomy/aggregation.py`; `publicCopy.ts` now also translates standalone `manifest` and `rollback`.

### Frontend fixes
8. **Error sanitization (MEDIUM)** — raw asset errors can no longer leak integrity/provider wording into visible copy: the classification logic moved from `AssetLoadState` into a shared `publicErrorText()` (`data/publicCopy.ts`), and `PublicHome.tsx`'s Dashboard-preview error now routes through it.
9. **PriceChart copy (HIGH)** — removed the banned "snapshot" wording from the disabled-period notes; the provider default `yfinance (cached)` is replaced with persisted-observations wording; the rebased OHLC labels changed from "(index)" to "(rebased)"; tooltip/table series names now state the rebasing (`Rebased close (start = 100)`, `IHSG (^JKSE, rebased)`).
10. **Dead-file removal (MEDIUM)** — deleted `pages/ChartDemo.tsx`, `pages/LeadershipMap.tsx`, `pages/TaxonomyMapPage.tsx`, `components/TaxonomyMap.tsx`, `components/RotationView.tsx`, `components/CustomCursor.tsx` (all zero-route/zero-import; several carried banned copy) and the stale `/chart-demo` redirect. Typecheck and production build pass after removal.
11. **Low/cosmetic** — DashboardPreview leader label is clamped inside the SVG viewBox (`x + 10` overflow); `groupHref` in PublicHome now threads the hook's `cadence`/`horizon` instead of hardcoding `daily`/`60d`; all standalone `rel="noreferrer"` anchors gained `noopener`; `DiaTextReveal`'s dead `return () => clearTimeout(t)` inside the observer callback is replaced with a real unmount cleanup; `TradingViewTechnicalAnalysis`'s load-probe `setTimeout` is tracked and cleared on unmount; the user-requested infinite hero float loop is kept and annotated in `index.css` (do not revert).

## 2. Verification at fix HEAD `555a27a` (evidence: `docs/submission-release/final-audit-2026-10-08/`)

| Check | Evidence | Result |
| --- | --- | --- |
| Python suite | [python-checks.txt](docs/submission-release/final-audit-2026-10-08/python-checks.txt) | 939 passed (935 + 4 new regression tests), 2 pre-existing deprecation warnings |
| Frontend typecheck | [frontend-typecheck.txt](docs/submission-release/final-audit-2026-10-08/frontend-typecheck.txt) | clean |
| Frontend production build | [frontend-build.txt](docs/submission-release/final-audit-2026-10-08/frontend-build.txt) | success, 672 modules |
| Sectors oracle (leadership, map/descriptive cohorts, signed concentration) | [sectors-oracle.json](docs/submission-release/final-audit-2026-10-08/sectors-oracle.json) | PASS, 0 mismatches (5,148 member values, 858 sector aggregates, 286 diffusion states) |
| Final reading oracle (incl. `rotation_phase_ytd`) | [reading-oracle.json](docs/submission-release/final-audit-2026-10-08/reading-oracle.json) | PASS, 0 mismatches, 0 provider calls |
| Integer diffusion count oracle | [diffusion-count-oracle.txt](docs/submission-release/final-audit-2026-10-08/diffusion-count-oracle.txt) | 174 groups, 3,654 daily + 870 weekly, 0 mismatches |
| Clean-checkout reproduction (both analysis assets, credentials unset) | [clean-reproduction.json](docs/submission-release/final-audit-2026-10-08/clean-reproduction.json) | PASS, 0 provider calls, source commit recorded |
| Route smoke (fresh production build, local preview) | [route-smoke.txt](docs/submission-release/final-audit-2026-10-08/route-smoke.txt) | all 16 routes HTTP 200 |
| Production-bundle checks | frontend-build run | no banned visible copy; `manifest`/`rollback` now sanitize; no 403 widget URL in the bundle |

The market-breadth price oracle is retained from [final repair verification](docs/submission-release/final-repair-2026-10-08/market-breadth-oracle.json): its price-panel inputs and code are untouched by this round.

## 3. Open items (unchanged from the previous round; none introduced here)

1. **Fresh browser QA at the fix HEAD** — no browser is installed in this environment. Required: `/` (landing + footer + Dashboard preview), the TradingView widgets on `/overview` and `/heatmap`, banned-word scan, four viewports (1036×799, 1369×799, 1440×900, 390×844), console errors.
2. **Readiness receipt re-issue** — the current receipt is bound to the pre-fix source commit and still carries the stale `previous_*` pointer noted in the audit; re-issue it against the fix HEAD.
3. **Vercel launch** — remains `BLOCKED_MISSING_GITHUB_INTEGRATION` (`docs/submission-release/final-repair-2026-10-08/launch.json`); the user must connect the Vercel GitHub integration, then retry the authorized launch and verify fresh public loads.

## 4. Pre-commit verification

- Full diff reviewed before commit; no secrets or credentials introduced (grep over the staged diff found none; `.env` remains ignored and untracked).
- Commit `555a27a`: 28 files changed, +275 / −1,533 (6 dead files deleted). Evidence and this handoff are committed immediately after in a second commit so the evidence is generated byte-for-byte at the recorded fix HEAD.
- All oracle passes and the pytest run above were executed in the working checkout at `555a27a`; the clean reproduction includes the recorded `source_commit`.
- Remaining after this handoff: browser QA, readiness re-issue, Vercel — all external, zero-cost items.
