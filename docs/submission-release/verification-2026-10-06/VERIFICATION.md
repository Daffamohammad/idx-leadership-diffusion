# Independent remediation verification — 6 October 2026

**Verdict: staged remediation PASS; activation/publication PENDING.**

This review reproduced the claimed browser interactions and checked the staged package and raw price calculations. It added only these verification artifacts; application and candidate files were not edited.

## Release identity and isolation

- Candidate: `rel-514f199a7d88a377ccf623f647e9196bcbbaea3d750b81b550affeefe93520f2`.
- Candidate manifest SHA-256: `cea9e4a7e17f8a21dc3ad22c351c994ff9ece80297c32a0a47e361306e1c153a`.
- `validate_manifest_file` PASS: all 11 package assets and 124 source-evidence records validate.
- Zero shared file inodes with every sibling candidate directory.
- Active release: `rel-48500fc94300469fed51247a129a900cfbe9c541e2d679f7a55ef558212941e7`.
- Active-pointer SHA-256 remains `dceac8c5c9516ea398b08265243d3d1b89e0aa208a4d809c34e9ab04dfefe6f4`.
- Sectors request-ledger SHA-256 remains `3cf1733c752b6e44bc2fd97e6d94b68b5220f7a725c6b5d0f6f39f89c8d590ac`. No Sectors live, preflight, connectivity, credit, or validation calls were made in this review.

## Display and taxonomy switching

The current `SubmissionRotationMap.tsx` SHA-256 is `8d45262cc13e4fb9c1a551bb13864a15e5667a519c973431296914c0f8faae22`. The inspector Diffusion cell uses `DiffusionReading`; `UNCONFIRMED` renders an em dash with aria-label `No comparable diffusion reading`. The leadership inspector, history, and table use `LeadershipReading`.

Browser checks ran against the existing local preview at `http://127.0.0.1:4174` and its active release:

- Hartono / Dwimuria holdings: one contributor; leadership and diffusion show em dashes in the inspector; the table and all five weekly history leadership entries show em dashes; zero raw `UNCONFIRMED` occurrences in page DOM text.
- Healthcare on 4 September: 36 contributors / 41 members; diffusion shows the accessible em dash; zero raw `UNCONFIRMED` occurrences in page DOM text.
- All four taxonomy buttons produce matching URL, selected-button, and plot taxonomy. The query is preserved and the selected-group parameter is cleared.
- The click handler contains one `setParams(next, { replace: true })` call. Runtime URL-write counts were not instrumented; the resulting URL and state were verified directly.
- No captured browser error or warning logs during these interactions.

Screenshots: `hartono-independent.jpg`, `healthcare-first-date-inspector.jpg`. Interaction results: `browser-checks.json`.

## Diffusion and underlying calculations

- Independent integer oracle: 160 groups, 3,360 daily observations, 800 weekly observations, zero state/legacy-label/weekly-transition mismatches.
- Independently reconstructed from raw adjusted-price and benchmark CSVs: all four replay excess-return horizons and breadth counts across 4,160 observations; zero mismatches.
- Daily and weekly breadth-change counts independently compared with their preceding same-cadence observation: zero mismatches.
- Market weekly returns independently reconciled to the pinned panel: 963 rows checked, 920 observed returns, zero mismatches; missing returns remain missing.

Detailed results: `independent-calculations.json`.

## September history, 52 weeks, and vintage lineage

- Current September-derived panel: validation and receipt PASS; 262 benchmark sessions from 1 September 2025 through 2 October 2026.
- FASW quarantine is retained and disclosed. The original acquisition vintage's FAIL validation and FAIL receipt remain preserved.
- Independent market-breadth oracle PASS; exact ticker lists match for 5D, 20D, 60D, and 52W.
- 52-calendar-week cutoff: 3 October 2025. Prior window: 238 sessions, 3 October 2025 through 1 October 2026; selected session excluded.
- 819 eligible of 829 traded; ten incomplete-window exclusions: BACH, EMMI, JECX, JELI, PJHB, PRDL, RANS, RLCO, SUPA, WBSA. All ten have first observed prices after the window starts.
- Strict 52W breaks: 11 highs and 32 lows; ticker sets match independently, with ties excluded.
- The selected-date cutoff falls on a session. The separate non-trading-calendar-cutoff regression also passed in the focused suite.
- The market/snapshot pinned panel starts on 15 December 2025, while the supplemental replay/breadth panel starts on 1 September 2025. Both vintages' prices and benchmark bytes have matching source-evidence records. Market weekly values match their pinned panel; supplemental replay/breadth values match their declared September panel.

Price-oracle details: `independent-market-breadth.json`.

## Konglo evidence boundary

The unchanged candidate has 32 groups and 75 memberships. The register observation date is 30 September 2026 and the captured availability date is 5 October 2026. The 2 October taxonomy view correctly emits `point_in_time_eligible=false`; its point-in-time rotation replay contains no Konglo observations. The supplemental historical comparison explicitly uses current membership retrospectively. Evidence gaps and exact-holder boundaries remain documented in the candidate decision ledger.

## Required checks and remaining step

- Focused diffusion, group-size, submission-builder, and release tests: **49 passed**.
- Current production build (TypeScript compilation plus Vite): PASS; existing config-loader and bundle-size advisories remain.
- `git diff --check`: PASS.
- The full suite's earlier 880-pass result was not rerun for this display-only change.

Activation/publication remains pending. The active Healthcare reading on 2 October is still `STABLE`; the candidate reading is `BROADENING_FIRM` for a five-name change in a 36-name cohort (+13.8889 pp). Verification of the source display fix does not activate the staged data package.
