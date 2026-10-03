# Next improvement — Bundle rebuild + re-verify (offline)

Date: 2026-10-03. Context: 6 UI fixes landed (F1 Top-3 scale, F2 mobile nav,
F3 PublicHome overflow, F4 Overview/Ticker overflow, F5 foreign-flow gate,
F6 chart quality label). `npm run typecheck`, `npm run build`, and
`pytest -q` (729 passed) are green. Browser re-measurement and bundle
rebuild are still pending. Release signoff stays HOLD.

## Constraints (do not violate)

- No paid API calls: no Sectors live refresh, Tavily, You.com, LlamaCloud,
  or OpenAI refresh. Run everything offline with persisted sources.
- Do not hand-edit `complete=true`, coverage sentinels, or snapshot JSON
  to force green. `complete=false` means unverified bundle, not corrupt
  files — rebuild to clear it.
- Do not expand claims: snapshot is 2026-08-27 based (37 days old at last
  audit), 962 registry vs 500-row sample vs 265 features, all 11 sector
  diffusions `UNCONFIRMED`, comparability `INCOMPARABLE`. UI must keep
  provisional/sample labels.

## Steps

1. Baseline
   - `git status --short`, `git diff --check`
   - `.venv/bin/python -m pytest -q` (expect 729 passed, 2 deprecation warnings)
   - `npm run typecheck --prefix app/web`, `npm run build --prefix app/web`

2. Rebuild derived artifacts from available sources (offline, in order)
   - ` .venv/bin/python -m scripts.calculate_foreign_flow_sample --help` then run
     with persisted `--input` + security-master; confirm `signal_eligibility`
     shows `market_days_meets_threshold=true` (6 days), `company_rows=true`
     (60 rows), `mapped_pct=false` (65%), `signal_eligible=false`.
   - `.venv/bin/python -m scripts.build_taxonomy_views --snapshot-id snap_sectors_2026-08-27`
     (or `--all-snapshots` if doing a full rotation); confirm
     `concentration_top3` stays 0–100 (e.g. 100.0, 94.24), not 0–1.
   - `.venv/bin/python -m scripts.validate_data` — must be clean before export.
   - `.venv/bin/python -m scripts.export_snapshot_json --latest`
   - `.venv/bin/python -m scripts.build_snapshot_index` (default SECTORS_LIVE;
     use `--include-all` only if testing mixed providers).
   - Verify `app/web/public/snapshots/snap_sectors_2026-08-27.json` +
     `index.json` updated; check `complete`, `quality.status`,
     `foreign_flow_sample.signal_eligibility`, `taxonomy_views.*.concentration_top3`.

3. Frontend re-verify
   - `npm run typecheck --prefix app/web`, `npm run build --prefix app/web`
   - Serve `app/web/dist` (or `npm run dev`) and check with no provider keys:
     - Desktop 1440px: 9 primary nav links, no error boundary.
     - Tablet 768px + mobile 390px: hamburger (`aria-controls="mobile-nav"`)
       visible, opens full 9-link menu, keyboard + Esc works.
     - `document.documentElement.scrollWidth`: Home must equal viewport
       (was 1816px @390px); Overview workspace ≤390px (was 456px);
       ticker workspace ≤390px (was 862px, chart ~826px).
     - Themes: Coal 100 → `100%` (not `10000%`), EV/materials 94.24 → `94%`,
       null → `—`.
     - Overview → Foreign-flow gate: Market days ≥5 `Met`, mapped 65% `Review`,
       Company rows ≥30 `Met`, Regime `Yes`; header still `Review`/ineligible.
     - Ticker AMMN.JK: chart 61 points (21 on 1M) with badge `Partial coverage`
       or `Data gap`, never `Not available` when points exist; empty series
       still `Chart unavailable`.
   - Re-run `pytest -q`, record `state.json`/`routes.json`/screenshots outside
     the repo (same layout as `self-audit-59a4999/`).

4. Signoff gates (all must hold, otherwise HOLD remains)
   - `complete` verified by fresh rebuild, not manual edit.
   - Registry 962 vs sample 500 vs features 265 still distinguished in UI.
   - Diffusion stays `UNCONFIRMED` until a compatible prior exists.
   - No secret patterns in tracked files; `.env` stays untracked.

## Done means

- New snapshot bundle + index committed (or documented why not), UI checks
  above all pass, and audit notes updated. Only then revisit perf work
  (951 kB JS code-split) — not before.
