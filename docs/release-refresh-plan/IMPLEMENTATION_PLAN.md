# Release consistency and repeatable refresh: re-audit and implementation plan

Audit date: 5 October 2026, Asia/Jakarta. Inspected commit: `46cf739acaeb660aa00595fe61aba7f4471ac59c`.

This document preserves the audit findings and baseline from before implementation. The resulting implementation, real local activation and current verification are recorded in [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md). The audit itself changed no application code, active indexes, historical snapshots or source evidence; failure reproductions ran against temporary copies.

The rotation omission is confirmed. Fixing only that omission would leave mutable asset files, independent frontend indexes and incomplete evidence binding. The smallest sufficient change is one package publisher, one staged refresh orchestrator and one frontend release selection shared by all asset readers. Keep the analytical engines and existing comparability gates intact.

## Current evidence

| Check | Fresh result | Boundary |
|---|---|---|
| Full existing suite in the working checkout | 832 passed, 2 deprecation warnings | Host permissions were needed for Bun/TSX temporary files; the restricted first run had 26 subprocess failures and 806 passes |
| Full existing suite in a fresh local clone of the audited commit | 832 passed, 2 deprecation warnings | Reused installed Python dependencies and the existing Bun/TSX runtime; this verifies tracked-source completeness, not a fresh dependency installation |
| Frontend typecheck and production build | PASS | Existing Vite configuration and bundle-size warnings remain outside this task |
| Four active market asset hashes | All match the current index | Snapshot is outside that index; its separately recorded hash is in AUDIT_EVIDENCE.json |
| Existing replay rebuilt from pinned local inputs | Identical JSON and identical canonical publication bytes | No publication flag was used; 29 recorded source/configuration/served-file hashes were unchanged |
| Current snapshot | `snap_public_market_2026-10-02`, 760 eligible securities | This is the served session, not a claim that 2 October is the latest completed session on the audit date |
| Current chart history | 24 sessions; trails for 8/11 sectors and 95/102 themes | Konglo has 0 historical observations; canonical snapshot has `NO_COMPARABLE_HISTORY` and no previous snapshot |
| Current snapshot size | 25,454,416 bytes, approximately 25.5 MB | Size and download optimization stay in the separate performance release |

Machine-readable audit results are in [AUDIT_EVIDENCE.json](AUDIT_EVIDENCE.json). Desktop/mobile package-switch, rollback and publication-race behavior were not claimed as verified by the audit; see the implementation status for completed follow-up evidence.

## Findings and consequences

| Priority | Finding | Evidence and consequence |
|---|---|---|
| P1 | Ordinary publication removes rotation | `scripts/publish_market_workspace.py:11` accepts only market, ownership and foreign inputs and rebuilds the index with those three keys. Temporary-copy reproduction changed four market asset entries into three. The existing publisher test explicitly expects three assets (`tests/test_market_workspace.py:135`). |
| P1 | Atomic index replacement does not preserve the previous package | The same publisher writes date-only filenames and overwrites them before replacing the index (`scripts/publish_market_workspace.py:34`). An injected interruption before index replacement preserved the old index bytes but changed its referenced market file, invalidating the old hash. Ownership files can also be reused by later market sessions and overwritten for corrections. |
| P1 | Readers can combine revisions | `SnapshotProvider.tsx:18` reads `/snapshots/index.json`; `marketWorkspace.ts:72` independently fetches `/market/index.json` for every asset key. The request cache uses snapshot ID and asset key, not release identity (`marketWorkspace.ts:70`). Different-session mismatches are often rejected, but corrections with the same snapshot ID/date can pass identity checks and use different indexes. This race is established from the call paths, not a browser race reproduction. |
| P1 | Supporting IDX context bypasses a package | `SnapshotProvider.tsx:35` independently fetches a fixed investor release and `idx_daily_statistics_latest.json`. Date checks reject future dates but do not bind hashes or package versions. These context inputs must be frozen inside the snapshot family or declared by the same release manifest. |
| P1 | Publisher does not verify all referenced evidence | The general publisher validates schemas, dates and foreign continuity but takes no snapshot, rotation, source ledger or validation-report input. A temporary candidate with an all-zero `sources.validated_panel.validation_sha256` was accepted, without any snapshot file in its served root. Individual exporters have useful validation, but publication does not establish a closed, verified set of inputs. |
| P2 | Refresh is a collection of scripts with unsafe defaults for orchestration | The existing `refresh_and_export` targets paid Sectors and automatically exports/indexes when enabled. `refresh_public_panel` defaults to the host's calendar date and a reusable output directory. `build_snapshot_chain` discovers a latest panel and can silently substitute the nearest earlier session (`scripts/build_snapshot_chain.py:120`). No single public refresh produces all five families and a readiness report without publishing. |
| P2 | Official validation is tied to the previous source files | `validate_public_panel.py:415` selects the September composite workbook and `Stock Summary-20261002.xlsx`. A later refresh needs explicit, hash-bound official input paths and target-session checks; changing a label or choosing a later directory cannot establish freshness. |
| P2 | Acquisition evidence is uneven and some history paths are replaceable | Public panels have retrieval timestamps and CSV hashes; ownership source entries have URL/date/hash but no retrieval or publication record; foreign export entries also lack those timestamps. Catalog preparation writes mutable `konglo.yaml`/`themes.yaml`. Raw panel writes can replace an existing acquisition. `build_snapshot_chain --force-rebuild` removes existing snapshot directories. The new runner must never use those overwrite paths against canonical history. |
| P2 | Clean staging is not yet enough for reproducibility | Snapshot export still reads taxonomy views, foreign-flow context, official context, research events and registry enrichment from ambient project directories. Validation writes a tracked fixture by default. Runtime `created_at`, `bound_at` and `validated_at` values can change content hashes on rebuild. Inputs, enrichment and deterministic output boundaries must be explicit. |
| P2 | Date-labelled universe versions can block otherwise comparable future snapshots | `prepare_market_universe.py` incorporates the observation date into `universe_version`. A new date therefore changes a required comparability field even if the structural universe is identical. Version identity must follow verified structural facts and policy; acquisition/observation dates remain separate evidence. Never edit older contracts or relax the existing equality checks. |

Preserve the controls already working: panel integrity and quarantine checks, export eligibility-cohort checks, source-ledger hashes, availability bounds, per-group replay segments, endpoint reconciliation and existing fail-closed canonical comparability. A valid rotation asset may correctly contain unavailable trails, including zero Konglo observations.

## Target contract

Use immutable package files under `app/web/public/releases/<release-id>/`, an immutable `manifest.json` for each package and one mutable `app/web/public/releases/active.json` pointer. The pointer records the selected manifest path/hash and the previous verified selection in one atomic write. Runtime readers use this pointer, not the two older indexes.

Every manifest requires the five named families: `snapshot`, `market`, `ownership`, `foreign`, `rotation`. Each entry carries a relative file reference, SHA-256, byte count, schema and observation date. Manifest metadata includes the exact target session, snapshot identity/provider/basis, analytical contract fingerprints, deterministic validation verdict and source-evidence inventory. Optional IDX context belongs to the snapshot family and is either embedded or listed as additional hashed package files. Declared absence is explicit; runtime discovery of a mutable latest file is removed.

Calculate a deterministic release ID from a canonical inventory of content hashes, target session and analytical/source contracts, before adding the release directory prefix to paths. The immutable manifest does not include its predecessor, activation time or run ID: those describe publication events, not package identity. Hash the completed manifest and bind that hash in the active pointer. This avoids identity cycles and permits the same package to be selected again for rollback.

Consistency means compatible dates and provenance, not equal observation dates. Snapshot, market and rotation reach the exact target session; foreign history reaches it with the required session/YTD continuity. Ownership retains its separate 1% and 5% observation dates and prior-register chronology, bounded by the target for the existing date checks. Source publication/capture times remain visible separately from observations. A capture after a historical session cannot establish availability during that session.

Keep two verdicts distinct: package integrity/readiness to publish, and analytical coverage/readiness. Missing required files, stale hashes or failed mandatory validation block publication. Correctly disclosed coverage gaps and unavailable trails retain their existing analytical status; they do not become confirmed signals merely because package validation passes.

No new dependencies are expected. Use the existing Python tools, installed pandas/Pydantic where useful, standard-library hashing/serialization/filesystem operations and the current React context structure.

## Implementation sequence

### 1. Establish the manifest validator and a single publisher

Primary files: a small `src/idx_leadership/data/releases.py`, `scripts/publish_market_workspace.py`, `scripts/build_rotation_replay.py` and a publication CLI, proposed as `scripts/publish_release.py`.

- Define the manifest schema, five required families, supported schemas and canonical serialization. Validate strict ISO dates, finite JSON values, contained paths, source identities, file existence, hashes and sizes. Reject traversal, symlink escapes and paths that still refer to mutable served aliases.
- Reuse existing validators to bind snapshot/market identity, eligible cohort, taxonomy views, ownership row dates, foreign session/YTD continuity, rotation endpoints and panel/source provenance. Match validation reports to the exact input hashes, official-source hashes and validator contract. A `PASS` label alone is insufficient.
- Materialize the candidate into a unique incoming directory under the served filesystem. Verify the final bytes and the complete reference graph before marking the package verified. Retain original source evidence locally; publish only the currently sanitized ownership representation, preserving address/account redaction.
- Create immutable files exclusively. Existing identical packages are verified and reused without rewriting; any different bytes at an existing immutable path cause refusal. Flush files and relevant directories, finalize the release directory, then replace only `active.json` with a uniquely named temporary file on the same filesystem.
- Hold a standard filesystem writer lock across active-pointer comparison and switch. Accept an expected active release ID, refuse competing/stale writers and release the lock on process exit. This prevents two operators from replacing each other's selection.
- Store the previous verified selection in the same pointer replacement. Rollback verifies the selected retained package again and changes that pointer only. Never rebuild, rewrite, delete or prune the rollback package as part of refresh/publication.
- Remove the old independent index-switch logic from the general publisher and `build_rotation_replay.publish`. Replay becomes build/export-only; legacy publication invocations must refuse with migration guidance or route through the complete candidate publisher. There must be one activation path.

This phase is complete when failure injection proves that both the active pointer and every file it references remain valid after a failed or interrupted publication.

### 2. Pin frontend reads to one manifest

Primary files: `SnapshotProvider.tsx`, `SnapshotContext.ts`, `marketWorkspace.ts`, relevant snapshot types and existing adapter tests. Retain page interfaces where practical.

- Fetch `active.json` once when the app loads, validate its manifest hash/schema and pin that release for the life of the loaded page. Read the snapshot and every workspace/context reference from that same manifest.
- Keep lazy asset loading where currently appropriate. Each lazy fetch uses the pinned manifest; it never rereads an active index. Verify snapshot bytes as well as the other assets, then check family identity/schema/date before adapting them.
- Key promises and returned state by release ID plus asset hash. Prevent stale state from an old release from rendering during any context transition; cancellation must not permit old asynchronous completions to replace current data. A failed family displays a gap/error for its pinned release, never a fallback family from another package.
- Navigation remains on the pinned release even if publication occurs meanwhile. A full browser refresh selects the newly active manifest. Avoid adding background polling or a new refresh UI.
- Remove runtime reads of the old snapshot/market indexes and independent latest IDX paths. Resolve historical/debug selection through a verified release manifest, rather than a free-standing snapshot ID. Preserve existing historical files as evidence; do not delete them during migration.
- Keep loading/error wording suitable for users. Release identity and source dates can appear in existing diagnostics; no general UI redesign is needed.

The snapshot retains its approximately 25.5 MB payload. This phase changes integrity and selection, not serialization size, compression, chunking or chart performance.

### 3. Add the repeatable candidate command

Proposed entry point: `scripts/refresh_release.py`. It orchestrates existing preparation, validation, quarantine, snapshot, taxonomy, export and replay tools; it does not duplicate analytical implementations.

Proposed operator interface:

```bash
# Offline candidate construction from explicit, already acquired inputs.
.venv/bin/python -m scripts.refresh_release \
  --target-session 2026-10-02 \
  --sources path/to/source-plan.json \
  --out-dir data/staging/release-candidate

# Separate, explicit activation after review.
.venv/bin/python -m scripts.publish_release \
  --candidate data/staging/release-candidate/manifest.json \
  --expect-active <active-release-id>

# Explicit rollback by selecting a retained verified manifest.
.venv/bin/python -m scripts.publish_release \
  --manifest app/web/public/releases/<previous-release-id>/manifest.json \
  --expect-active <active-release-id>
```

`--target-session` is required. Reject an absent, future, incomplete or unsupported session; do not silently use the prior session. If a requested calendar date is also supplied for reporting, record it separately from the explicitly selected completed session. Establish the session using actual benchmark observations and validated dated official inputs, not weekday arithmetic. The command must not claim that a target is the latest session merely because it is the newest cached file.

The source plan lists exact cached paths/capture IDs, hashes, dates, required official comparison files, classification/membership versions and any optional snapshot context. Optional bounded public acquisition can be an explicit mode of the same command. Default rebuild/validation is offline. Sectors stays HOLD; existing paid/provider/parser permission and request-budget controls remain enforced. Never auto-inject live or credit-spend flags.

Run the stages in dependency order:

1. Resolve and verify source inventory and session; register newly acquired evidence without modifying old captures.
2. Prepare listing/daily-market and ownership records into staging. Prepare the dated membership/classification versions and their edges.
3. Acquire or reuse the exact public panel; validate against explicit official files. If the existing rules permit quarantine, retain the failed original report/panel, derive a distinct panel and independently validate it again. Do not remove failures merely to obtain PASS.
4. Build the target canonical snapshot in a new snapshot root, supplying retained verified predecessors for comparison. Existing history is read-only. An incompatible predecessor remains incompatible; an unconfirmed target is reported faithfully.
5. Export the market workspace from the validated panel and cohort, build taxonomy views, then export the complete snapshot from those staged inputs.
6. Export official foreign history and build the chart-only rotation replay with the final snapshot bytes as its endpoint.
7. Assemble the five-family manifest, validate it and produce the review report. Exit with a clear candidate-ready or blocked verdict.

Keep all outputs under an explicit staging root outside served files. Pass explicit input/output paths to child scripts; use `--no-publish-fixture` for validation and no replay publication flag. Extend the few helpers that still read ambient derived directories to accept the runner's pinned enrichment paths. The runner must verify that each requested output was actually produced, including both taxonomy views; success of a child process alone is insufficient.

Failing any stage writes a useful report and leaves the active release, served files, canonical history, configuration catalogs and tracked test fixtures untouched. Never use `--force-rebuild` on historical roots or overwrite a canonical catalog during normal refresh.

### 4. Capture future evidence and separate acquisition from rebuild

Use the existing request ledger for request telemetry and a small append-only acquisition inventory for evidence. Record each acquisition/import with source URL/publisher, observation date or range, true retrieval timestamp in UTC, captured-file hash/size and hash scope, publication date when independently supported, publication evidence, availability bound and derivation/input hashes. A normalized Yahoo payload hash must be labelled as normalized content; do not claim it is an original HTTP-response hash.

- Preserve each dated listing, board, classification and membership capture in its own versioned location. A correction creates a new record with a supersession link; it never changes the original. Importing an older file today records today's actual verification/retrieval boundary when earlier provenance is unknown.
- For Konglo, verify a captured ownership/membership source and bind its bytes/hash to the recorded timestamp. Leave the publisher date null if unknown and use `capture_upper_bound`. Generalize the present listing-registry-specific capture check just enough to verify a source capture record for ownership; a free-text evidence note or a newly authored config does not prove earlier availability.
- Never manufacture a historical retrieval timestamp or turn the ownership observation date into publication evidence. Current descriptive membership and historical session eligibility remain separate claims. Historical replay admits a version only after its verified availability and observation bounds.
- Preserve the existing per-group segmentation and minimum of three comparable daily observations or weekly endpoints. Keep the weekly sampling rule. No bridge across membership, eligibility, contributor, source-contract or data-gap changes is permitted.
- Keep structural version IDs stable only when the relevant verified listing/board/classification/membership/policy facts are actually identical. Separate this identity from dated acquisition records and mutable market quotes. Real structural changes produce new versions. Do not rewrite the October 2 contract or prior eligible hashes to manufacture compatibility.
- Canonical diffusion still uses the existing `check_snapshot_compatibility` result and chronological predecessor selection. Chart replay availability does not establish canonical diffusion history. If a new structural contract needs a baseline, accumulate new comparable snapshots and report the boundary.
- Freeze genuine acquisition timestamps as source evidence. Keep invocation times, temporary paths and publication events in separate run receipts. Make new snapshot creation/provenance and validation verdict content deterministic from pinned inputs; their wall-clock receipts must not perturb release hashes. Preserve previously recorded historical fields as-is.

The reproducibility promise is byte-identical artifacts and release manifests for the same pinned captures, tool/configuration contracts and inputs. A new retrieval is a new evidence event even when returned values match; do not overwrite its predecessor or pretend its timestamp is identical.

### 5. Migrate, verify and document recovery

Freeze the currently served snapshot plus its four verified market assets and required IDX context as the bootstrap package. Verify their exact bytes and cross-references. Preserve older snapshots and evidence at their current paths; subsequent candidates use versioned packages. Coordinate the first pointer activation with the frontend loader change so the browser is never deployed without the manifest it requires.

Use the existing tests first, revise the three-asset publisher expectation and add only the missing behavioral regressions. Extend `tests/test_market_workspace.py`, `test_point_in_time_rotation.py`, `test_refresh_tool_safety.py` and `test_public_refresh_chain.py` where they fit. Add a focused release test module rather than folding publication rules into the analytical engines.

| Required scenario | Observable assertion |
|---|---|
| Ordinary refresh and same-session correction | Candidate/publication contains all five families, including rotation; the old manifest and files are unchanged |
| Missing/empty/wrong-schema/nonfinite asset | Candidate is refused and active pointer plus referenced bytes remain unchanged |
| Stale asset, panel, source, verdict or provenance hash | Refusal occurs before activation, with the exact mismatch in the report |
| Incompatible source/session dates | Refusal before publication; ownership's valid older observation dates remain allowed |
| Failed mandatory validation or quarantine revalidation | Failed evidence is retained, candidate is blocked and served/history/fixture trees are unchanged |
| Interrupt after any asset write, finalization or pointer preparation | Current package is fully readable; no partially written new package is selected |
| Interrupt immediately after pointer replacement | Either old or complete new package is selected; a retry safely recognizes the actual active state |
| Concurrent publishers or stale expected active ID | One activation succeeds; another refuses without lost updates or mutable files |
| Reader loads while publication occurs | All asset requests resolve through the manifest already selected by that reader, including same-session revisions |
| Route navigation and cached promises after publication | No data from a different release appears; a full reload selects the new manifest |
| Missing asset/failed fetch after activation | Browser shows bounded failure or retains a complete already loaded release; no individual-family fallback to another release |
| Rollback | Selected previous manifest is reverified; all five families return to its hashes after reload |
| Invalid or tampered rollback package | Rollback is refused and active package remains unchanged |
| Repeat offline construction in two staging roots/on different dates | Identical family files and manifest/release ID; only run receipts differ |
| Historical evidence protection | Before/after relative-path, byte-size and SHA-256 inventory is unchanged across rebuild, validation, failure and rollback |
| Unknown publication and future Konglo capture | No point before the verified availability bound; sufficient later comparable observations enable trails without backdating |
| Stable and changed structural facts/cohorts | Existing comparability checks pass only for equal contracts and hashes; changed facts split history and keep unsupported diffusion unconfirmed |

After those changes, run the full suite, frontend typecheck/build and diff checks. Verify from a clean clone using lockfile installations and no copied `.env`, raw cache or ignored snapshots. The tracked bootstrap package and synthetic release fixtures must cover normal clean-clone testing. A full historical candidate rebuild may require a separately supplied hash-verified source archive; report missing source evidence as blocked instead of substituting fixture evidence or refetching history silently.

Exercise the production preview at desktop (1440×900) and mobile (390×844). Test initial load, hard refresh/deep links, ordinary publish followed by refresh, same-session correction, delayed requests during a switch, network/asset failures and rollback. Check market overview, stock heatmap, ownership, foreign flow and sector/Konglo/theme rotation pages. Record requested manifest/release IDs and every family hash in addition to screenshots, loading/error behavior and console results. Confirm Konglo remains unavailable before its real evidence bound and that desktop/mobile readers obey the same package selection.

The runbook must state the serving boundary. Atomic filesystem selection is verifiable for the local static root; remote deployment/CDN atomicity is not established by a local file rename. A future deployment must upload verified immutable package files first, make them reachable and only then select the manifest using that platform's supported mechanism. Mutable pointers require fresh/revalidated fetches; immutable assets can use their immutable paths. Do not add a new remote hosting adapter or deploy a site in this scope.

## Review report and completion gates

Each candidate command writes JSON plus a readable report containing requested calendar date (if any), exact target/completed session and proof, run mode, acquisition/capture inventory, source observation/publication/availability/retrieval dates, hashes, required-file checks and current-release comparison.

Report listing/requested/downloaded/failed/empty/quarantined/eligible counts separately, ticker-level coverage changes and reasons, raw/derived-panel lineage, ownership register dates/populations, foreign-flow session coverage and units, rotation segment start/end/cohort/reasons, daily/weekly trail readiness, canonical predecessor/comparability decisions and limitations. End with package validity, analytical readiness, publication readiness, blocking reasons and the explicit publication command. No manual editing of readiness flags is permitted.

Completion requires one command to create a validated five-family candidate, one explicit step to select it, proof that all failures preserve the current package and successful rollback, reproducible output from pinned evidence, full-suite/fresh-install clean-clone checks and desktop/mobile publication/refresh evidence. Baseline tests passing today do not establish those future behaviors.

Formulas, return axes, confirmation thresholds, Sectors HOLD, ownership identity limitations, redactions and foreign-flow units remain unchanged. The approximately 25.5 MB initial snapshot download, UI redesign, unrelated warnings, background scheduling and remote deployment stay outside this release.
