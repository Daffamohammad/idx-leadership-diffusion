# Outsource implementation prompt — release remediation and completion

You are the implementation engineer responsible for closing the remaining IDX Leadership Diffusion submission-release defects and deliverables. Work in:

/Users/daffa/Hackathon/idx-leadership-diffusion

The release target is the completed session **2 October 2026**. Inspect the current files and behavior before editing. Read AGENTS.md and follow Scope Guard. You are not alone in this codebase: the working tree contains substantial existing tracked changes and untracked implementation files. Preserve other work, do not reset or clean the tree, and do not overwrite the existing staged or published packages.

Your deliverable is implemented source changes, meaningful regression coverage, completed evidence-backed data work where access permits, and one independently validated staged candidate ready for review. Do not activate a release, deploy, submit externally, push, or claim final acceptance without a separate explicit instruction.

## Verified baseline — reproduce it first

Read these artifacts:

- docs/submission-release/audit-2026-10-06/AUDIT_REVIEW.md
- docs/submission-release/audit-2026-10-06/evidence.json
- docs/submission-release/CATALOG_EVIDENCE_LEDGER.md
- docs/submission-release/CALCULATION_CHANGE_REPORT.md
- docs/release-refresh-plan/IMPLEMENTATION_STATUS.md

The audit was performed at HEAD 46cf739acaeb660aa00595fe61aba7f4471ac59c on main with a dirty working tree. Treat current source files as authoritative if they have advanced.

Active release: rel-48500fc94300469fed51247a129a900cfbe9c541e2d679f7a55ef558212941e7.

Staged candidate: data/staging/submission-2026-10-02/candidate-weekly-diffusion-fix/manifest.json, release rel-19b48d74e83da574599308c9a3a02109d83dafaa8dfe8e1e3690985998d2cf2d.

The independent count audit found 12 incorrect weekly classifications, 37 incorrect daily classifications, and 20 incorrect weekly transitions in the candidate. The active package still has the original weekly cadence defect, with 141 weekly discrepancies under the independent count rule. Both packages pass all ten asset hash checks.

The four taxonomy buttons now work and correctly clear the group parameter in one URL update. Preserve that fix. Hartono still exposes UNCONFIRMED in its table, inspector, and weekly history.

The Konglo catalog still contains 22 portfolios and 64 membership rows. The candidate adds no memberships. The validated stock and IHSG panels start on 15 December 2025; the requested 1 September vintage and 52-week highs/lows are incomplete.

## Ownership and scope

You own these responsibilities and the smallest necessary related edits:

| Work | Primary files and inputs |
| --- | --- |
| Diffusion precision and cadence regressions | src/idx_leadership/signals/diffusion_v2.py; scripts/build_submission_analysis.py; existing diffusion and submission builder tests |
| Rotation display and URL behavior | app/web/src/components/SubmissionRotationMap.tsx; reuse app/web/src/data/format.ts and StatusChips.tsx conventions |
| Konglo evidence and membership expansion | scripts/prepare_market_catalogs.py; src/idx_leadership/providers/idx_ownership.py where needed; config/market_expansion/konglo_rules.yaml; staged membership/ownership evidence; data/research/konglo/ |
| Public history and supported high/low horizons | scripts/refresh_public_panel.py; scripts/validate_public_panel.py; scripts/build_market_breadth.py; existing public provider and panel contracts |
| Complete candidate and handoff | scripts/refresh_release.py; scripts/extend_submission_release.py; existing release validator; new versioned staging output; submission release documentation |

Do not redesign the UI, change economic formulas or axes, weaken eligibility or confirmation thresholds, add unrelated abstractions, or optimize the deferred initial-download performance problem. Prefer existing code, standard library facilities, and installed dependencies. Justify any new dependency before adding it.

## Phase 1 — establish an independent editing baseline

The previous candidate was made using hardlinks. It shares 115 of 119 files with candidate-next-release, including seven manifest assets. Before writing any shared input, make a new ordinary or copy-on-write candidate copy with independent file inodes. Verify that candidate edits cannot alter the old staging inputs or active package. Keep the old manifests and evidence available for comparison.

Record the starting active pointer and asset hashes. Use a fresh output directory for new acquisitions and regenerated artifacts. Ensure manifest source references point to the exact pinned evidence and validation reports used by the new build.

## Phase 2 — fix diffusion numeric correctness

The weekly builder now compares weekly breadth against the prior weekly endpoint, which is correct. The remaining root defect is the floating-point reconstruction of constituent changes in classify_diffusion_v2.

Reproduce IDXIC Banks on 18 September: n=45, outperforming count 16→21. The true count change is five and the firm floor is five. Percentage subtraction yields an implied count of 4.999999999999998, causing BROADENING_FRAGILE instead of BROADENING_FIRM.

Fix numeric comparison in the existing classifier or its necessary count-aware callers with the smallest sufficient change. Preserve:

- broadening at +10 pp and narrowing at −10 pp;
- firm floor max(2, ceil(0.10 × group_size));
- five contributors for group signal eligibility;
- legitimate fragile classifications;
- missing baseline and ineligible states as UNCONFIRMED;
- daily versus weekly comparison periods and unchanged leadership/rotation rules.

Do not classify from rounded display percentages. If using a numeric tolerance, bound and justify it, and prove that genuinely sub-threshold moves do not get promoted.

Add meaningful boundary regressions, including n=45 with 16→21 and its reverse; n=19 with 9→11; n=62 with 37→30; exact ±10 pp boundaries; a one-name fragile move; a move genuinely below the percentage gate; missing priors; and cohorts below five. Cover the replay builder so weekly and daily labels, legacy diffusion labels, and weekly transitions cannot diverge again.

Use an independent integer-count oracle. With the current defaults, broadening means d×10≥n, narrowing means d×10≤−n, and the exact firm floor is max(2, (n+9)//10), where d is the raw count change. Do not use classify_diffusion_v2 itself as the expected-value oracle. Check every regenerated observation and transition; the final mismatch count must be zero. Do not exclude groups or shrink the universe to make this check pass.

## Phase 3 — complete display rules and protect taxonomy switching

Use the existing enum formatting or chip conventions in the rotation table, selected-group inspector, and dated history. Preserve UNCONFIRMED in backend data while displaying the established em dash and appropriate accessible explanation. Groups below the signal floor must remain browsable with their members, returns, and contributor counts.

Verify Hartono / Dwimuria holdings and other small groups through search and Show all. No raw UNCONFIRMED token should appear in those user-facing readings. Apply the same existing formatting convention to other displayed enums.

Verify all four taxonomy buttons. Starting with a selected group, each switch must update the URL and plotted taxonomy, clear the group parameter, preserve unrelated query parameters, reset replay selection as intended, and synchronize table, inspector, and chart date. Retain the current single URL write. Check desktop and mobile interactions, including keyboard access.

## Phase 4 — finish evidence-backed Konglo expansion

Resolve the requested ecosystems in the evidence ledger: Jardine, Djarum, CT Corp, Lippo, Bakrie, Triputra, Happy Hapsoro/Rukun Raharja, Mayapada, Rajawali, Ciputra, Pakuwon, and Kawan Lama. Map aliases to existing portfolios before deciding whether a new group is needed.

Inspect the cached ownership register, issuer disclosures, and current rules before acquiring more material. All 20 existing candidate research observations are UNVERIFIED; search text is a discovery aid. Each accepted membership requires a dated primary IDX or issuer source establishing the specific direct holding, control relationship, or every necessary link in a documented chain.

Record group, ticker, holder/parent, relationship type, ownership percentage when disclosed, observation/publication dates, retrieval date, source URL, saved source hash, and the verification decision. Respect the 2 October evidence cutoff. Preserve ambiguity exclusions, overlapping memberships, privacy redaction, and the distinction between disclosed ownership and documented control. A named parent does not imply self-ownership. Shared names, directors, sectors, or projects do not establish a chain.

Publish genuinely new verified membership rows through the existing catalog and snapshot workflow. Keep rejected or blocked candidates in a review ledger. Do not fabricate additions, duplicate aliases to inflate group counts, or mark expansion DONE when no new verified memberships were added. Recompute group coverage and frozen replay cohorts from the accepted membership version, retaining the current-membership historical-replay disclosure.

## Phase 5 — acquire and validate the requested public history

Extend real observed stock adjusted-close and IHSG benchmark history from **1 September 2025 through 2 October 2026**. Use the existing approved public provider/cache path with an explicit universe, start, end, and fresh output directory. Do not use the script's default universe or today's date without confirming they match the selected release. Respect existing acquisition budgets and receipts.

Validate ticker/date uniqueness, positive finite prices, observed native benchmark sessions, source/adjustment basis, corporate-action treatment, missing sessions, exact target coverage, and the prior-year YTD base. Keep raw and adjusted price provenance separate. Do not interpolate, forward-fill missing observations into qualifying history, synthesize data, change to an incompatible provider basis, or silently reduce the universe.

Rebuild fixed-cohort historical breadth and add 52-calendar-week high/low readings only for stocks with complete qualifying observations. The high/low comparison must exclude the selected session from its prior range and require a strict break; ties do not qualify. Test exact lookback boundaries, non-trading cutoff dates, incomplete histories, new listings, and per-horizon denominators and ticker lists. A calendar cutoff falling between sessions must not invalidate otherwise complete history.

If access or source evidence is unavailable, preserve the exact failure receipt, complete the unaffected phases, and mark this deliverable BLOCKED or PARTIAL with the concrete missing inputs. Do not present December coverage as the requested September vintage or display unsupported 52-week values.

## Provider and release guardrails

- Sectors remains HOLD: make zero live, preflight, connectivity, credit, or validation API calls. Preserve the existing recorded sample and persistent request ledger. Reuse saved responses where appropriate.
- Use existing authorized public evidence access under its recorded caps. Do not incur unapproved costs, create accounts, bypass access controls, expose secrets, or transmit private ownership material.
- Leadership, Diffusion, Concentration, Confirmation, and rotation phase remain separate measures. Preserve coverage gates and descriptive research boundaries.
- Build one consistent five-family candidate with all required supplementary assets. Revalidate source evidence, panel reports, cross-file lineage, hashes, schemas, and dates. Do not merely edit manifest hashes around stale validation evidence.
- Do not modify immutable published directories or active.json during implementation. Preserve failure evidence and prepare the existing activation and rollback commands for the owner to review.

## Validation and acceptance

Run the relevant focused tests while implementing, then the required final checks once changes are complete:

~~~sh
.venv/bin/pytest -q tests/test_diffusion_group_size.py tests/test_group_size_diffusion.py tests/test_submission_analysis_builders.py tests/test_release_publication.py
.venv/bin/pytest -q
npm run typecheck --prefix app/web
npm run build --prefix app/web
git diff --check
~~~

Use scripts.validate_public_panel with explicit paths and --target-session 2026-10-02. Reuse scripts.refresh_release and scripts.extend_submission_release for the complete candidate workflow. Validate the final manifest with the existing validate_manifest_file function in candidate mode. Report the exact commands and resulting release ID and hashes. Include untracked source changes in the handoff because git diff alone omits them.

Acceptance requires zero independent diffusion and transition mismatches, preserved cadence baselines and thresholds, no raw small-group UNCONFIRMED labels, successful taxonomy URL interactions, evidence-backed catalog additions or explicit unresolved evidence decisions, genuine September history and supported 52-week outputs or a precise remaining data blocker, valid complete-package hashes/lineage, and proof that the active pointer and Sectors ledger were preserved.

Return:

1. A concise change summary and exact changed-file inventory.
2. Regression and independent-oracle results with before/after mismatch counts.
3. Desktop/mobile interaction evidence and screenshots for taxonomy switching and small-group display.
4. A Konglo decision ledger with accepted additions, primary sources, exclusions, and remaining blockers.
5. A history coverage report with dates, sessions, per-horizon eligibility, exclusions, and source hashes.
6. The new staged manifest path, release ID, manifest and asset hashes, reproducible rebuild commands, and prepared activation/rollback commands.
7. A DONE / PARTIAL / BLOCKED table for each requested deliverable. Distinguish staged, activated, and finally accepted status accurately.

Persist within the authorized scope. Resolve routine implementation choices yourself. Ask only when a material scope change, unapproved cost/access, or irreversible action is required. Finish the reviewable candidate before requesting any final publication approval.
