# The Diffusion · submission release, 8 October 2026

## Product and evidence boundary

**Problem.** Index performance can conceal different sector leadership and
constituent breadth. **Audience.** Market-intelligence reviewers and equity
researchers who want to inspect a sector signal down to the stocks contributing
to it.

The primary submission workflow is `/sectors`: sectors ranked by 20-session
excess return, a 60-session excess-return versus relative-momentum map, daily
and weekly replay, and a constituent inspector. The fixed retrospective universe
contains 66 stocks, six in each of 11 sectors, selected from the frozen market
source observed on 2 October 2026. The page retains every member and reports
eligible contributors. Returns use raw Sectors stock closes and native Sectors
IHSG closes. Mechanical corporate actions exclude affected stock windows;
missing values remain missing, each paired replay comparison uses a common
cohort, and signals below five contributors are unconfirmed. No adjusted-price
claim or historical point-in-time membership claim is made.

Opening the page reads only the active immutable release. If the selected
release lacks the recorded sample, frozen selection-market source, or analysis,
the primary workflow blocks and displays a distinct absent or validation-error
state. Broader IDX views remain supporting context.

## Current release

- **Active:** `rel-fad218940fcc7e2492d97613681175b6cb2b2e38d387254737fafc0cadfa09dc`
- **Active manifest SHA-256:** `2defade3acf1688eb96e0e40d577189f390eafd03fea69a1175ce5e07aa1f11c`
- **Rollback release:** `rel-246dd63fa62c1321143334c799f116e686a7602141a94a97aa3cc41d54b0d708`
- **Rollback manifest SHA-256:** `f2d2a3866ec002e5a9a7f1a7ec4e3bc1b8d4b15f431aaa52af7efccf3471759b`
- **Recorded sample SHA-256:** `9e9c8540e676eed99acd4dbfe4bdf86534e1a3a9a6e6575e3d3ce99281390f20`
- **Frozen selection-market SHA-256:** `f02edbe114d38543a1c13ac64df7b5b469e941e7859b15133d79e3a164cdf1c3`
- **Signal-analysis SHA-256:** `4aeea2a1e8417c81fa896351ad09597e206b2e1f8705a8daac275d78e27c82b9`
- **YTD baseline SHA-256:** `7f954900f67b0f701390c256b60412c60086d5ee5b2e5d09dfaf9ef18a357ff1`

The recorded sample validates against the original frozen selection-market
bytes whose hash it records, not a later market file. The analysis asset and
all four Sectors assets are bound by the immutable release manifest.

The YTD baseline uses the last observed 2025 native IHSG close, 30 December
2025. Twenty-four eligible stock requests returned 23 matching stock closes;
WBSA returned no matching baseline and remains an explicit gap. The full YTD
window excludes 42 constituents with listed mechanical actions. All 11 sector
aggregates remain unconfirmed because each has fewer than five eligible names;
the inspector shows only the 23 individual raw-price readings with a shared
baseline and action-free window. The acquisition receipt records one initial
DNS failure, the empty WBSA response, 461 total estimated requests/credits,
and 39 remaining retry slots under the 500 ceiling. No further paid calls are
authorized by this sign-off.

The dated 7 October receipts record the preceding acquisition and Sectors checks; they do not establish app-wide browser acceptance. The repair has a separate [browser QA receipt](repair-2026-10-08/browser-qa.json) and [readiness receipt](repair-2026-10-08/readiness.json), bound to its tested source commit and the active data release. See the [repair verification](repair-2026-10-08/VERIFICATION.md) for rendered figures, failure recovery, clean reproduction, and launch status.

The subsequent 8 October copy follow-up labels the primary navigation entry
**Dashboard** and displays **66** in the sources lead line. Its
[targeted browser checks](label-followup-2026-10-08/qa.json) cover those labels
on desktop and mobile. The full repair receipts above remain bound to their
earlier tested source commit; the label receipt does not replace them.

The [pre-acquisition readiness receipt](readiness-2026-10-07.json) records the
offline gate before live baseline collection. The separate [YTD preflight
record](budget-preflight-2026-10-07.json) documents its read-only plan: 433
carried reservations, 25 base requests, and 42 reserved retry slots. The
[acquisition validation receipt](ytd-acquisition-validation-2026-10-07.json)
and [repository sign-off receipt](signoff-2026-10-07.json) record the observed
responses and final release checks.

## Reproduction and checks

From a clean checkout with the locked project dependencies installed:

```sh
.venv/bin/python -m pytest -q
npm run typecheck --prefix app/web
npm run build --prefix app/web
```

Rebuild the Sectors analysis from the active release's sample and frozen source,
then verify it with the independent close-arithmetic and integer-count oracle:

```sh
RELEASE_ID="$(.venv/bin/python -c 'import json; print(json.load(open("app/web/public/releases/active.json"))["active"]["release_id"])')"
RELEASE_DIR="app/web/public/releases/$RELEASE_ID"
.venv/bin/python scripts/build_sectors_analysis.py \
  --sample "$RELEASE_DIR/assets/context/sectors_recorded_sample.json" \
  --selection-market "$RELEASE_DIR/assets/context/sectors_selection_market.json" \
  --ytd-baseline "$RELEASE_DIR/assets/context/sectors_ytd_baseline.json" \
  --out /tmp/sectors_signal_analysis.json
.venv/bin/python scripts/verify_sectors_analysis_oracle.py \
  --sample "$RELEASE_DIR/assets/context/sectors_recorded_sample.json" \
  --analysis /tmp/sectors_signal_analysis.json \
  --ytd-baseline "$RELEASE_DIR/assets/context/sectors_ytd_baseline.json"
```

The broader IDX snapshot and price-breadth oracles remain part of the existing
market release evidence in [the dated 6 October clean-checkout report](GIT_HANDOFF-2026-10-06.md).
That report describes an earlier release. Use this file and the separate repair evidence above for current browser acceptance.

For a production preview, build first, then keep this process running in a terminal:

```sh
npm run preview --prefix app/web -- --host 127.0.0.1 --port 5173 --strictPort
```

Open `http://127.0.0.1:5173/sectors`. A stopped preview process makes later data requests fail; cached screen content is not a working preview. The root route opens `/sectors`; `/sources` holds coverage and provenance. Browser rendering makes no Sectors requests.

Readiness requires real browser observations and hashed screenshots for 1036×799, 1440×900, and 390×844, including all visible navigation routes, interrupted serving, corrupt assets, and retry recovery. The verifier rejects failed, incomplete, or stale evidence:

```sh
.venv/bin/python scripts/verify_sectors_readiness.py \
  --browser-qa-receipt docs/submission-release/repair-2026-10-08/browser-qa.json \
  --out /tmp/diffusion-readiness-new.json
```

Existing dated receipts are never overwritten. Documentation-only commits may follow the tested source commit; any code or released-data change requires fresh evidence.

## Submission checklist

Repository verification, public hosting, and final submission are separate gates. The public launch currently depends on connecting the repository to the existing Vercel GitHub integration; a local readiness receipt does not establish a public deployment. The
[official track description](https://hackathon.sectors.app/tracks/market-intelligence)
and [hackathon rules](https://hackathon.sectors.app/rules) govern eligibility
and delivery. The repository/core workflow is tracked separately from the
remaining submission media: a public one-minute teaser, an accessible judging
video no longer than three minutes, the problem statement, track and team
details, and the prescribed social post. Submission closes 8 October 2026 at
23:59 WIB and the project freezes when submitted. Those materials remain to be
completed after repository sign-off.

## Dated historical records

The 6 October audit, handoff, release verification, source archive inventory,
and walkthrough remain unchanged as dated evidence of the preceding build.
They are retained for provenance and rollback history, not as descriptions of
the active `/sectors` workflow.
