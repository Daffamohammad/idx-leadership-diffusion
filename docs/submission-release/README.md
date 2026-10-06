# Submission release package

The selected local release is dated **2 October 2026**. It is an immutable offline package; the active pointer binds its manifest and SHA-256.

- **Active release:** `rel-514f199a7d88a377ccf623f647e9196bcbbaea3d750b81b550affeefe93520f2`
- **Active manifest SHA-256:** `bb9c5b655ca52026184787dedff9ddfd4c38774ce2b7ea2f2890c76e7f873ea3`
- **Previous release for rollback:** `rel-48500fc94300469fed51247a129a900cfbe9c541e2d679f7a55ef558212941e7`
- **Preview:** start it locally using [the installation and walkthrough instructions](LOCAL_INSTALLATION_AND_WALKTHROUGH.md). No preview server is currently assumed to be running.

## Handoff and evidence

- [Release handoff](HANDOFF-2026-10-06.md) — audit findings, implementation, provenance, operational state, and evidence index.
- [Git handoff and clean-checkout verification](GIT_HANDOFF-2026-10-06.md) — scoped source baseline, local source archive, and repeatable checks.
- [Calculation change report](CALCULATION_CHANGE_REPORT.md)
- [Catalog evidence ledger](CATALOG_EVIDENCE_LEDGER.md)
- [Source and reconciliation evidence](SOURCE_AND_RECONCILIATION_EVIDENCE.md)
- [Annotation resolution checklist](ANNOTATION_RESOLUTION_CHECKLIST.md)
- [Local installation and walkthrough instructions](LOCAL_INSTALLATION_AND_WALKTHROUGH.md)
- [Audit review](audit-2026-10-06/AUDIT_REVIEW.md) and [independent verification](verification-2026-10-06/VERIFICATION.md)
- [Earlier local walkthrough (5 Oct; predates this release's breadth and daily replay)](media/submission-walkthrough-2026-10-05.mp4), [captions](media/submission-walkthrough-2026-10-05.vtt), and [recording metadata](media/recording-metadata.json)

## Analysis scope

The historical comparison includes 21 daily observations from 4 September through 2 October and weekly endpoints on 4, 11, 18, and 25 September and 2 October. Sector calculations use 752 common eligible stocks. The retrospective series is labeled **Historical price replay using current membership**; dated prices do not imply historical membership evidence.

The comparison covers 11 sectors, 32 documented Konglo portfolios with 75 membership rows, 102 captured IDXIC subindustries, and 15 separately defined curated themes. Konglo membership is not point-in-time eligible for 2 October because the register was available on 5 October. Unresolved ownership links remain in the decision ledger.

The overview includes official daily market breadth, directional traded-value shares, activity and turnover context, foreign-flow context, fixed-cohort net advances, and strict 5D/20D/60D/52-week highs and lows. For the 52-week window, 819 of 829 traded stocks had complete history; the independent price oracle reproduced 11 new highs and 32 new lows with no ties promoted.

## Provider boundaries

Official IDX foreign flow is the default YTD series. Provider totals remain separate, missing observations are disclosed, and the partial Sectors YTD sum is not compared with full-period IDX YTD. The release preserves existing formulas and thresholds. **Sectors HOLD** remains in place for future live use. The activated package was built from saved evidence; viewing it does not make provider calls. Hosting and external submission were not performed.

## Verification record

The active package has 11 hash-matching assets and 124 source-evidence rows. Independent integer-count checks covered 160 groups, 3,360 daily observations, and 800 weekly observations with zero mismatches. The market-breadth price oracle passed all four horizons. Python, frontend typecheck, production build, and browser checks are recorded in the linked handoff and verification reports.

After changing the active pointer, rebuild `app/web/dist/` before using `npm run preview`; the preview serves a build-time copy of the pointer.
