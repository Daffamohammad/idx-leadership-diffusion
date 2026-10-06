# Release audit — 6 October 2026

**Verdict: HOLD.** Taxonomy switching works in the local browser. The weekly cadence correction fixes the original comparison-period mistake, but the staged candidate still has diffusion errors at the constituent-count boundary. The small-group display defect and the two requested data deliverables remain open.

This audit inspected the current working tree at HEAD 46cf739acaeb660aa00595fe61aba7f4471ac59c on main. The tree contains substantial pre-existing changes and untracked implementation files. Current artifact hashes, source fingerprints, every classification mismatch, and verification results are recorded in [evidence.json](/Users/daffa/Hackathon/idx-leadership-diffusion/docs/submission-release/audit-2026-10-06/evidence.json).

## Findings, ordered by priority

### 1. P1 — The staged candidate still misclassifies firm diffusion moves

An independent check using integer breadth counts found **12 incorrect weekly states, 37 incorrect daily states, and 20 incorrect weekly transitions** in the candidate. These cover 750 weekly and 3,150 daily observations across 150 groups. Breadth counts and cadence deltas reconcile; the remaining defect is classification precision.

For IDXIC Banks on 18 September, the cohort contains 45 stocks and the outperforming count increases from 16 to 21. Five changed constituents meet the firm floor of five, and the breadth increase exceeds 10 percentage points. The candidate state is BROADENING_FRAGILE. Subtracting the two percentage values produces an implied count of **4.999999999999998**, which fails the comparison against five.

The root comparison is in [diffusion_v2.py](/Users/daffa/Hackathon/idx-leadership-diffusion/src/idx_leadership/signals/diffusion_v2.py:65). Both the daily and weekly replay use it in [build_submission_analysis.py](/Users/daffa/Hackathon/idx-leadership-diffusion/scripts/build_submission_analysis.py:218). Fix numeric representation while preserving the existing thresholds, constituent floor, eligibility rules, and intended fragile states. Recompute transitions after correcting the states.

The earlier zero-mismatch result reused the production classifier to check its own output. This independent audit supersedes that result.

### 2. P1 — The active package still contains the original weekly defect

The active release remains rel-48500fc94300469fed51247a129a900cfbe9c541e2d679f7a55ef558212941e7. Its Healthcare reading on 2 October still labels the +13.9 pp weekly breadth change STABLE. The integer-count audit finds **141 weekly mismatches** in that package; the earlier 138 figure used the same floating-point classifier as the implementation.

The staged candidate is rel-19b48d74e83da574599308c9a3a02109d83dafaa8dfe8e1e3690985998d2cf2d. It correctly classifies Healthcare as BROADENING_FIRM, but finding 1 prevents its acceptance. Its manifest SHA-256 is 4bbe6f051c9543095779714f7219b8ef0fafc8de70f88dd4cc573ba88706c6b1.

The source patch has not been activated. Complete candidate remediation and validation before the separate publication step.

### 3. P2 — Small-group leadership bypasses the display rules

At /map?taxonomy=KONGLO&q=Hartono, Hartono / Dwimuria holdings has one contributor. The table displays UNCONFIRMED. Selecting the row also exposes that raw value in the inspector and all five weekly history rows.

The three rendering sites are [the inspector](/Users/daffa/Hackathon/idx-leadership-diffusion/app/web/src/components/SubmissionRotationMap.tsx:298), [history](/Users/daffa/Hackathon/idx-leadership-diffusion/app/web/src/components/SubmissionRotationMap.tsx:302), and [the table](/Users/daffa/Hackathon/idx-leadership-diffusion/app/web/src/components/SubmissionRotationMap.tsx:306). The project already maps UNCONFIRMED to an em dash in [format.ts](/Users/daffa/Hackathon/idx-leadership-diffusion/app/web/src/data/format.ts:37) and uses the same rule in LeadershipChip. Reuse those display conventions and preserve the backend eligibility state.

![Hartono raw leadership state in the inspector and history](/Users/daffa/Hackathon/idx-leadership-diffusion/docs/submission-release/audit-2026-10-06/hartono-unconfirmed.png)

### 4. P2 — The staging copy is not independent of its source

The candidate-weekly-diffusion-fix directory shares **115 of 119 files** with candidate-next-release through hardlinks. Seven of its ten manifest assets share the same device and inode as the source copy: foreign, ownership, rotation, snapshot, IDX daily statistics, IDX investor release, and the recorded Sectors sample.

Writing one of those files in place can change both staging directories. Hash validation will detect changed bytes, but this copy is unsuitable as an isolated editing baseline. Create an independent ordinary or copy-on-write staging copy before further work. This finding concerns staging isolation; no shared file was edited during this audit.

## Unfinished deliverables

| Deliverable | Verified current state | Completion evidence needed |
| --- | --- | --- |
| Konglo expansion | 22 portfolios, 64 membership rows, 61 summed replay contributors, 19 portfolios below five contributors. The candidate adds zero memberships versus the active release. All 20 candidate research observations are UNVERIFIED. | New, dated primary-evidence-backed membership rows; identity and relationship decisions for each requested ecosystem; regenerated catalogs and explicit contributor coverage. |
| Public-history extension | Both source panels start on 15 December 2025. The displayed fixed cohort has 751 stocks and 188 benchmark sessions through 2 October 2026. Available high/low horizons are 5D, 20D, and 60D; 52W is absent. | Validated observed stock and IHSG history from the requested 1 September 2025 start, complete-horizon exclusions, and independently reconciled 52-calendar-week strict-break lists. |

The requested Konglo ecosystems are listed in [CATALOG_EVIDENCE_LEDGER.md](/Users/daffa/Hackathon/idx-leadership-diffusion/docs/submission-release/CATALOG_EVIDENCE_LEDGER.md:38). Existing research observations remain discovery material until the primary ownership or control link is verified.

## What passed

- All **10 manifest asset hashes** match in both the active package and the staged candidate.
- All four rotation taxonomy buttons work in the browser at http://127.0.0.1:4174: Sectors, Konglo, IDXIC activities, and Curated themes. The selected group is cleared on switching and the search query is preserved. The URL and plot taxonomy agree.
- The focused diffusion and breadth tests passed: **19 passed** across test_diffusion_group_size.py, test_group_size_diffusion.py, and test_submission_analysis_builders.py. The existing tests do not cover the real count-boundary failures above.
- Current frontend typecheck passed. The production build passed in the preceding remediation turn and was not repeated in this audit.
- No captured runtime errors occurred during the audited map interactions. The audit browser returned to Overview. Mobile interaction checks were not rerun.
- The Sectors request ledger remains at SHA-256 3cf1733c752b6e44bc2fd97e6d94b68b5220f7a725c6b5d0f6f39f89c8d590ac, matching the recorded release ledger. No Sectors calls were made.

## Independent calculation rule

The checker does not import the production classifier. With the documented defaults, let n be the fixed cohort size and d the current outperforming count minus the prior count:

- Missing prior observation, missing counts, or n below five: UNCONFIRMED.
- Broadening threshold: d × 10 ≥ n.
- Narrowing threshold: d × 10 ≤ −n.
- Firm constituent floor: max(2, ceil(n / 10)), computed with integer arithmetic.
- A threshold-clearing move is firm when the absolute count change meets that floor; otherwise it is fragile. Moves below the percentage threshold are stable.

Weekly comparisons use the preceding weekly endpoint. Daily comparisons use the preceding daily observation. Transition expectations are reconstructed from the independently classified weekly sequence.

## Audit boundary and handoff

This audit changed only the new audit artifacts. It did not edit application or calculation source, acquire history or ownership evidence, activate a package, or approve final acceptance. It did not rerun the full Python suite or mobile UI audit.

The [outsource implementation prompt](/Users/daffa/Hackathon/idx-leadership-diffusion/docs/submission-release/audit-2026-10-06/OUTSOURCE_PROMPT.md) prioritizes the numeric defect, the display defect, evidence-backed data completion, and a validated isolated candidate. Publication remains a separate explicit step after review.
