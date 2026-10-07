# The Diffusion repair verification · 8 October 2026

**App verdict: VERIFIED LOCAL BUILD. Public hosting: BLOCKED.** The repaired
source is pushed to the existing public repository. Vercel returned HTTP 400
because its GitHub integration is not installed. No public deployment or URL
has been verified. Videos, the social post, and final submission remain deferred.

The tested source is `63d9dced8088f76f2bcfa480a7b778e6d6fc6777`, including the
repair in `c25ece9e82dc009b402c0cc6a812a31d807a5509` and the subsequent external
heatmap navigation fix. Later evidence-only commits do not change the tested
application or data. The production preview is running independently at
<http://127.0.0.1:5173/sectors>; the local machine must remain running.

## Visible workflow

The application and browser title use **The Diffusion**. Coverage and provenance
are at `/sources`; `/recorded-sample` redirects there. The Sectors landing page
places replay controls, the leadership map, and compact 20D rankings before
detailed readings. Desktop shows the map and rankings together; mobile stacks
them. The recorded date replaces the previous blanket READY claim.

- All 11 sector rankings and all 66 tracked constituents are present.
- Nine current sectors have eligible map coordinates. Financials and Technology
  each have four matched contributors and explicitly fail the five-name floor.
- Every one of the 21 daily and five weekly replay dates was exercised.
- All 11 constituent inspectors were selected: six unique names in each sector,
  66 names in total. Ranking and map selection both update the inspector.
- The 23 supported stock YTD readings remain dated through 2 October 2026 during
  earlier replay selections. A concise explanation replaces the 11 unavailable
  YTD sector aggregate rows. The sources page has no separate Q3 return calculation.
- Retrospective selection, raw unadjusted prices, corporate-action exclusions,
  fixed comparison cohorts, missing readings, and the five-contributor floor
  remain visible. Unsupported readings are never converted to zero.
- The context overview renders the IHSG close, **6,036.89**, and its selected-release
  curve. The underlying close is `6036.88818359375`. Both price-breadth curves render.
- What Changed renders a breadth curve and 11 weekly sector rows. Summary,
  participation, returns, breadth changes in percentage points, concentration,
  and Firm/Fragile diffusion agree with the same verified weekly comparison.
  The current weekly cohort has 752 contributors and 450 outperformers (59.8%).
- The context leadership map renders 11 current sector points and their valid
  trails. Current points remain visible without history; missing coordinates
  remain missing, and trails break across gaps.

## Browser evidence and failure recovery

All **17 required browser checks passed** on the production build. Fresh loads
and interactions were verified at **1036×799, 1440×900, and 390×844**, without
page overflow. All 15 visible navigation routes were exercised. Healthy loads
and navigation produced zero unexpected console errors. A navigation race in
the external TradingView stock heatmap was fixed by isolating the embed in an
iframe; daily/YTD options and theme behavior were retained.

The [browser receipt](browser-qa.json) contains the actual observations, route
inventory, counts, and hashes of 12 captured screenshots. Representative views:

| View | Evidence |
| --- | --- |
| Sectors, 1036×799 | [Screenshot](sectors-1036x799.jpg) |
| Sectors, 1440×900 | [Screenshot](sectors-1440x900.jpg) |
| Sectors, 390×844 | [Screenshot](sectors-390x844.jpg) |
| Weekly breadth | [Screenshot](weekly-breadth-1440x900.jpg) |
| Context map | [Screenshot](context-map-1440x900.jpg) |

Faults were served through a separate, read-only localhost test server. The
original release files were never edited. Recorded checks cover delayed loading,
HTTP 503 responses, missing manifest entries, corrupt analysis/YTD bytes, missing
selection lineage, absent history, and a stopped/restarted server. Failures appear
beside their affected figures with Retry; genuine absence has its own message.
Corrupt Sectors assets block rankings and map marks. A failed comparison does not
fall back to inconsistent cached readings. Retry restored the IHSG, breadth
curves, weekly comparison, and context map after the relevant faults cleared.
See [request results](fault-server-requests.json).

## Calculation, regression, and reproduction checks

- **915 Python tests passed**, with two existing provider deprecation warnings.
  [Full output](python-checks.log).
- Frontend typecheck and production build passed. Existing Vite config-loader
  and bundle-size warnings remain. [Clean-build output](frontend-checks.log).
- The independent Sectors oracle found zero mismatches across 5,148 member-window
  values, 858 sector aggregates, 286 diffusion/cohort checks, 66 YTD contributor
  values, and 11 YTD aggregates. Corporate-action exclusions and the five-name
  floor passed the [readiness gate](readiness.json).
- The broader count-based diffusion oracle checked **4,160 observations** across
  160 groups, with zero mismatches. [Result](diffusion-count-oracle.json).
- All four price-breadth horizons (5D, 20D, 60D, 52W) matched the independent
  source calculation and contributor lists. [Result](market-breadth-oracle.json).
- A clean archive of the tested commit reproduced the analysis byte for byte
  with credentials absent and network access disabled. Its frontend typecheck
  and build passed using the existing locked dependencies; the compiled JS/CSS
  hashes matched the workspace build. [Result](clean-reproduction.json).
- Readiness now requires `--browser-qa-receipt`. Regressions reject missing,
  failed, incomplete, wrong-release, wrong-hash, or stale evidence, and preserve
  existing historical receipts. A documentation-only descendant of the tested
  source is permitted; changed application code or released data requires fresh QA.

The [check index](checks.json) records the test and preservation results. Use
the reproduction commands in [the current reviewer instructions](../README.md).
The 6 and 7 October audit reports and receipts remain dated historical records.

## Data, budget, and rollback

The active release is unchanged:

`rel-fad218940fcc7e2492d97613681175b6cb2b2e38d387254737fafc0cadfa09dc`

Manifest SHA-256:
`2defade3acf1688eb96e0e40d577189f390eafd03fea69a1175ce5e07aa1f11c`

The retained rollback release is:

`rel-246dd63fa62c1321143334c799f116e686a7602141a94a97aa3cc41d54b0d708`

Rollback manifest SHA-256:
`f2d2a3866ec002e5a9a7f1a7ec4e3bc1b8d4b15f431aaa52af7efccf3471759b`

All 450 protected recording, budget, ledger, and active-pointer files retained
their pre-repair hashes. The ledger remains **461 estimated credits / 500**, with
39 unused slots. **Paid acquisition remains on HOLD; this repair made zero paid
requests.** Neither this receipt nor browser acceptance authorizes more acquisition.

## Publication status

Before pushing, 1,802 reachable Git blobs across 99 commits and the tracked tree
were checked for credentials and private keys, including exact comparisons with
locally configured secrets without recording their values. Twelve matches were
reviewed as policy text or explicit offline test fixtures; no issued-credential
matches or tracked credential files were found. Pending evidence files also had
zero matches to configured credentials. See [review scope](credential-review.json).
This is a bounded pattern-based review, not a guarantee against every secret format.

The application repair is pushed to
[the existing repository](https://github.com/Daffamohammad/idx-leadership-diffusion).
The [launch receipt](launch.json) records the Vercel failure. Connect the Vercel
GitHub integration with access to this repository, then complete the authorized
deployment and verify fresh loads of its public URL. Public hosting remains an
explicit blocker until that succeeds; local app verification does not complete
the submission.
