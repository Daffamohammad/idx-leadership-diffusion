# Release refresh implementation status

Updated 5 October 2026 (Asia/Jakarta).

The ordered implementation plan and audit evidence are preserved in this directory. Phases 1–5 are implemented and locally verified. A real October 2, 2026 release was assembled from the hash-pinned source plan and activated in the local static app. No remote deployment was performed.

## Implemented

- Added the strict five-family release manifest validator, immutable package publisher, atomic active-pointer switch, stale-writer check, and verified rollback. The legacy standalone market and rotation publication paths refuse publication.
- Pinned the frontend snapshot, market, ownership, foreign-flow, rotation, and optional IDX context reads to one selected manifest. Requests and cached results are keyed by release ID and asset hash.
- Added `scripts.refresh_release` for explicit-session offline candidate staging and reporting, plus append-only acquisition capture and structural universe/taxonomy versions.
- Added bounded date-range support for release-pinned IDX context assets and verified the Konglo capture-availability boundary without backdating it.
- Preserved formulas, confirmation thresholds, redactions, and **Sectors HOLD**. The 25.5 MB snapshot download remains separate performance work.

## Real candidate and local activation

- Located the three ownership source workbooks in Downloads and confirmed each SHA-256 against `docs/market-expansion-handoff/SOURCE_MANIFEST.json`. Recorded immutable acquisition copies and actual import verification times in `data/research/acquisitions/`.
- Staged the explicit `2026-10-02` session from 104 hash-pinned evidence files. All six offline stages succeeded and the strict candidate validator passed.
- Activated release `rel-06805460211501b6ec4298f24920d96b474ae39bd88b0594210ff6d71dbcf1a9` locally. `app/web/public/releases/active.json` binds its manifest SHA-256 to `39291169644f5c114c329d9f16554310e035fea0f57fd01108caa42e089b3b2a`.
- Snapshot, ownership, and foreign-flow family bytes match the served source assets. Market and rotation changed only their binding to the freshly validated panel report. The candidate and replay did not alter historical evidence.

## Verification

- Full Python suite in the working checkout: **860 passed**, 2 existing deprecation warnings. A source-only clean copy also passed **857 tests** before the final three invalid-family cases were added; it used a newly created Python 3.14 environment, installed pinned `requirements.lock` dependencies plus the declared `official` and `dev` extras, and omitted `.env`, raw data, caches, and ignored snapshots.
- Fresh frontend lockfile install: `npm ci` installed **111 packages** with no reported vulnerabilities. Typecheck and production build passed; existing Vite configuration and chunk-size advisories remain.
- Focused release publication suite: **21 passed**, including failure injection, verified rollback, stale validation, cross-session hashes, competing publishers, and missing, empty, or wrong-schema family assets. Invalid candidates leave the active pointer and package unchanged. A delayed frontend asset request also passed while the active pointer changed; it stayed on the originally selected release.
- Local browser checks passed at desktop **1440×900** and mobile **390×844**. Overview, stock heatmap, ownership, foreign flow, and rotation routes loaded from the October 2 package. The Konglo history controls remain disabled with **0 of 22** groups having dated trails.
- A browser release-switch probe loaded a second strictly manifest-validated test package, kept its already-open page on that package after the pointer reverted, and loaded the restored package on a new page. The probe package was test-only and is not in the served source tree.

## Serving boundary

The active pointer and immutable release are verified in the local static root. This does not establish atomicity for a remote host or CDN. Any later deployment must upload and verify immutable files before switching the platform’s pointer using its supported mechanism.

## Submission release and recorded Sectors sample

The October 2 base release above has been superseded locally by submission release `rel-a8b40a6b563bb0c6aa0eb2e6a3a4ff1c40d82c7af6055d62f6ab211725666cca`. Its manifest SHA-256 is `9d6ec3f0271b198ac9d18d2745fd22b5927b337c18fdc2ca45d363ebae6e8b11`; it is the release selected by `app/web/public/releases/active.json`.

- The submission bundle includes a five-date, 752-stock matched-cohort replay, dated group histories and computed Q3 sector baskets. The replay is labeled as using current membership; it does not claim historical membership evidence.
- The local Sectors sample freezes 66 common stocks across 11 sectors and completed at 433 reserved requests / estimated credits under the persistent 450 ceiling. The full foreign-flow Q3 window has 64 matched sessions. Official IDX remains the YTD default; Sectors Q3 remains separately labeled with its full-period difference. Four omitted Sectors YTD sessions stay listed in the Sources disclosure without imputation.
- Working-tree Python verification: **866 passed** (two pre-existing deprecation warnings). The web app was independently installed in a new temporary folder with `npm ci`, then typechecked and built successfully (670 transformed modules). The frontend bundle-size and Vite config advisories remain.
- Desktop route and interaction QA covered the market read, movers, sector/Konglo/IDXIC maps, source disclosures, catalogs, heatmap, and methodology. A 390 × 844 Chromium layout pass covered ten key routes with no horizontal overflow, loading state, or rejected submission status text.
- The final recorded walkthrough is a **3:24 silent, captioned MP4** with a WebVTT sidecar in `docs/submission-release/media/`. Desktop and 390 × 844 mobile interaction checks passed, including selection, disclosures, search, and refresh. No remote hosting or external submission was performed.
- Browser route changes leave the persistent Sectors request ledger unchanged; the recorded sample stays on **Sectors HOLD** for new live data acquisition.

## Submission preparation status · 7 October 2026

The sections above are dated records of the 5 October and 6 October releases.
For the 8 October submission, the active repository state is described by
`docs/submission-release/README.md` and the dated receipts in that directory.

- The active immutable release is `rel-fad218940fcc7e2492d97613681175b6cb2b2e38d387254737fafc0cadfa09dc` (manifest SHA-256 `2defade3acf1688eb96e0e40d577189f390eafd03fea69a1175ce5e07aa1f11c`); rollback is `rel-246dd63fa62c1321143334c799f116e686a7602141a94a97aa3cc41d54b0d708` (manifest SHA-256 `f2d2a3866ec002e5a9a7f1a7ec4e3bc1b8d4b15f431aaa52af7efccf3471759b`). Both immutable packages are included with the repository state.
- `/sectors` is the primary workflow. Its 66-stock sample validates against the original frozen selection-market bytes; native Sectors IHSG and stock closes drive analysis. Missing readings stay missing, mechanical-action windows are excluded, and aggregate signals retain the five-contributor floor.
- The native IHSG YTD baseline is 30 December 2025. Twenty-three stock closes match that session. The empty WBSA result and 43 total gaps remain explicit; 42 constituent YTD windows with mechanical actions are excluded. Sector aggregates remain below the confirmation floor.
- The original 433-reservation sample recording remains unchanged. The successor YTD recording totals 461 requests / estimated credits of the 500 ceiling, with one initial host-resolution failure preserved and 39 retry slots remaining. The validated receipt authorizes no further paid calls.
- Verification passed: **896 Python tests**, frontend typecheck and production build, exact offline analysis rebuild, independent arithmetic and integer-diffusion oracle (5,148 member readings, 858 sector aggregates, 286 diffusion states/cohorts; zero mismatches), budget restart/concurrency/pre-attempt-501 tests, and desktop/mobile browser review. The build retains the existing Vite configuration and large-chunk advisories.
- Repository sign-off is recorded in `docs/submission-release/signoff-2026-10-07.json`. The public one-minute teaser, accessible judging video up to three minutes, problem statement, track/team details, and prescribed social post remain to be completed before the 8 October 23:59 WIB submission deadline.
