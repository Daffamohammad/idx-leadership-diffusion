# IDX Leadership Diffusion — Decision Log

## D001 — Public-data-first prototype

- **Decision:** Start with `yfinance` (or another public data source)
  for the analytical backbone; defer Sectors-native data to a later
  stage.
- **Reason:** Validate the full pipeline end-to-end before spending
  Sectors credits; iterate quickly on schema, units, and methodology
  without API throttling.
- **Alternative considered:** Sectors-first. Rejected because
  credentials are not yet available and we want a runnable foundation.
- **Consequence:** The provider layer abstracts this; future
  SectorsProvider slots in without engine rewrites.
- **Revisit trigger:** Sectors API access available + parity test
  plan approved (P0.5 in `NEXT_ITERATION.md`).

## D002 — Provider abstraction

- **Decision:** All data access goes through a `MarketDataProvider`
  interface; the analytical layer never imports vendor SDKs.
- **Reason:** Reproducibility, testability, auditability, and future
  multi-provider parity checks.
- **Alternative considered:** Direct yfinance calls in scripts.
  Rejected because it couples the engine to one vendor.
- **Consequence:** A `CapabilityProvider` mixin defines optional
  Sectors-native methods as separate, opt-in interfaces.
- **Revisit trigger:** Never (foundational design).

## D003 — Leadership and diffusion kept separate

- **Decision:** Two independent state machines
  (`LeadershipState` × `DiffusionState`); not collapsed into one
  composite score.
- **Reason:** Strong performance with thin participation (LEADING +
  NARROWING) is a meaningful and common market pattern. A single
  ordinal score would hide it.
- **Alternative considered:** Weighted composite conviction score.
  Rejected as opaque and methodologically premature.
- **Consequence:** Evidence objects always carry both states; the
  contradiction detector flags LEADING + NARROWING explicitly.
- **Revisit trigger:** Never (semantic commitment).

## D004 — No opaque conviction score

- **Decision:** The product exposes per-metric evidence and per-axis
  states, not a single opaque "conviction" or "momentum" number.
- **Reason:** Auditability; the downstream narration layer must be
  able to justify every claim.
- **Alternative considered:** Composite scoring 0-100.
  Rejected as a black box.
- **Consequence:** No "momentum score", "smart money index", etc.
- **Revisit trigger:** Never (commitment to interpretability).

## D005 — No full backtest in groundwork

- **Decision:** This pass produces infrastructure and a sample
  snapshot; it does NOT backtest parameter choices against historical
  returns.
- **Reason:** The prompt explicitly forbids tuning thresholds using
  future returns. Adding a backtest now would invite optimization
  creep.
- **Alternative considered:** Lightweight descriptive forward-return
  diagnostics. Implemented as `export_diagnostics` for manual review
  without making performance claims.
- **Consequence:** The diagnostic CSV is descriptive only.
- **Revisit trigger:** Frontier review may add non-optimizing
  diagnostics; never optimization against realized returns.

## D006 — Full-market Sectors integration deferred

- **Decision:** No full-market Sectors calls in this pass. The
  `SectorsProvider` is a typed stub with explicit
  `NotImplementedError`s.
- **Reason:** Sectors credits are finite; we want every credit to
  pay for the next material feature, not exploratory data
  exploration.
- **Alternative considered:** Best-effort Sectors calls. Rejected
  because partial integration is worse than no integration.
- **Consequence:** `docs/SECTORS_INTEGRATION_PLAN.md` enumerates the
  exact P0 items.
- **Revisit trigger:** P0.1 (auth + client) in
  `NEXT_ITERATION.md`.

## D007 — Equal-weight group returns in groundwork

- **Decision:** Group returns and contributions are equal-weight.
- **Reason:** Market-cap and free-float weights are not available
  from the public prototype; the weighting interface is reserved for
  Sectors.
- **Alternative considered:** Approximate market-cap from price*volume.
  Rejected as noisy and unrepresentative.
- **Consequence:** Group conclusions may differ from Sectors
  cap-weighted results; documentation labels this clearly.
- **Revisit trigger:** Sectors full-universe + free-float available
  (P0.8).

## D008 — Absolute-move concentration convention

- **Decision:** Concentration uses **absolute-move decomposition** by
  default (`convention="absolute_move"`).
- **Reason:** Avoids the sign-confusion trap: a positive group return
  driven by one large gainer should report high concentration, even if
  most constituents are flat.
- **Alternative considered:** Signed contribution share. Exposed as
  a separate `compute_signed_contribution_table` for drill-down.
- **Consequence:** `top1_contribution_share` is a robust indicator of
  dependence on a single name; HHI of absolute shares measures true
  driver concentration.
- **Revisit trigger:** If a downstream use-case requires signed
  dominance; the function exists already.

## D009 — Provisional thresholds in `methodology.yaml`

- **Decision:** All numerical thresholds (horizons, breadth bands,
  acceleration threshold) live in `config/methodology.yaml`.
- **Reason:** Configuration-driven methodology is auditable and
  change-tracked; magic numbers in code would hide assumptions.
- **Alternative considered:** Hard-code. Rejected for the same
  reason.
- **Consequence:** Tests in `tests/test_states.py` lock down the
  current thresholds; future calibration is a config change, not a
  code change.
- **Revisit trigger:** Frontier calibration study (P3).

## D010 — Atomic snapshot writes

- **Decision:** Per-file writes use `tmp + rename` for atomicity; the
  per-snapshot `manifest.json` is the last file written.
- **Reason:** A partial snapshot must not replace a good one.
- **Alternative considered:** Single-tarball writes. Rejected
  because it complicates the read path.
- **Consequence:** A reader can detect a half-written snapshot by the
  absence of `manifest.json`.
- **Revisit trigger:** Never (engineering hygiene).

## D011 — Free-float kept separate from equal-weight group return

- **Decision:** Sectors free-float weights are wired through
  `SectorsProvider.get_free_float` but **not** used to override the
  default equal-weight group return.
- **Reason:** The brief §26 is explicit: equal-weight is the
  participation layer; magnitude weighting (market-cap or
  free-float) is a separate layer. Collapsing them hides whether
  leadership is broad or narrow.
- **Alternative considered:** Default to free-float. Rejected for
  the same reason.
- **Consequence:** Two views available: equal-weight for
  participation, free-float-weight for magnitude. The engine can
  expose both side-by-side.
- **Revisit trigger:** User demand for a single weighted number.

## D012 — Suspensions: exclude from current breadth, retain in metadata

- **Decision:** A suspended security contributes 0 to the
  current-snapshot breadth but remains in the group's
  membership metadata.
- **Reason:** Treating suspended as 0% would hide the suspension
  event; treating as 100% would over-state participation.
- **Alternative considered:** Mark UNCONFIRMED for the group.
  Rejected because the group's other constituents may still have a
  valid breadth.
- **Consequence:** Group snapshot has `constituent_count` (group
  membership) and `eligible_count` (active on as-of). The
  participation denominator is `eligible_count`.
- **Revisit trigger:** A new "suspension-adjusted" view is needed.

## D013 — Sectors `close` treated as raw until basis is verified

- **Decision:** The Sectors `/v2/close/` `close` field is
  treated as **raw** (not split/dividend adjusted) and duplicated
  to `adjusted_close` for downstream compatibility.
- **Reason:** The official docs do not state the basis. The
  parity harness (this pass, `PROVIDER_PARITY_REPORT.md`) will
  measure the difference against yfinance `Adj Close`; the
  hypothesis is a dividend-yield-magnitude gap (~1–2% over 20D
  for normal Indonesian banking names).
- **Alternative considered:** Treat as adjusted. Rejected
  because a documented 410 for v1 demonstrates docs can be wrong;
  prefer a labeled, defensive default.
- **Consequence:** Until verified, group returns understate
  dividend income. G011 in `KNOWN_GAPS.md`.
- **Revisit trigger:** Corporate-action audit confirms a basis.

## D014 — Group-size-aware diffusion (BROADENING_FIRM / _FRAGILE)

- **Decision:** Diffusion classification adds a **constituent-count
  floor** that scales with the group size:
  `floor = max(2, ceil(0.10 × group_size))`. A `+10pp` move only
  flips the state to `BROADENING_FIRM` if at least `floor`
  constituents are implied to have changed direction. Otherwise
  `BROADENING_FRAGILE`.
- **Reason:** The v1 raw ±10pp rule is unstable for small
  subsectors: in a 5-stock group, a single name flip produces
  20pp, which the v1 rule treats as a sector rotation. The v2
  rule keeps the v1 thresholds but demands a structural change in
  the membership.
- **Alternative considered:** z-score over trailing 60D.
  Rejected for v2 — adds complexity without an observed turnover
  baseline; can be added later as a parallel signal.
- **Consequence:** A new v2 enum (`DiffusionStateV2`). v1 states
  are derived via `to_v1_state`. v1 manifests remain readable.
- **Revisit trigger:** Live turnover study.

## D015 — Concentration v2: top1 ≤ 1.0, signed share, HHI

- **Decision:** `compute_concentration_v2` enforces `top1_abs_share
  ≤ 1.0`, reports `top1_signed_share` and `top3_signed_share`
  alongside, and preserves HHI ≤ 1.0.
- **Reason:** The v1 absolute-move share could exceed 1.0 in
  pathological cases (the underlying `_normalize` step doesn't
  guarantee the sum is 1.0 across all `top_n`). v2 enforces the
  invariant and reports signed shares for attribution.
- **Alternative considered:** Drop the cap and document. Rejected
  because the cap is trivially correct and the signed share is
  useful for the contradiction detector.
- **Consequence:** v2 is the default. v1 `compute_concentration`
  remains for back-compat.
- **Revisit trigger:** A downstream use-case requires uncapped
  shares.

## D016 — Minimum group size: 4 → 5

- **Decision:** Bump the minimum eligible constituents from 4 to
  5.
- **Reason:** In a 4-stock group, the constituent floor for
  diffusion is 2, which equals a single name flip. Combined with
  the 10pp threshold this is still unstable. 5 raises the floor to
  2, same as 4, but the relative fraction (2/5 = 40%) is more
  defensible than (2/4 = 50%) in a 50% threshold vocabulary.
- **Alternative considered:** Keep 4. Rejected because the
  liquidity / staleness audit (this pass) shows that 4-stock
  sub-industries are common in the Sectors taxonomy and the
  engine should not over-react to a 1-name flip.
- **Consequence:** A handful of sub-industries that qualified at
  4 constituents now report UNCONFIRMED. The change is small.
- **Revisit trigger:** Live stability study.

## D017 — Methodology v2 carries forward; v1 snapshots remain readable

- **Decision:** Bump `method_version` to `methodology-v2`; keep the
  v1 Pydantic schemas in place; manifests with `methodology-v1`
  are deserialized unchanged via `extra=ignore` on
  `GroupSnapshot` and Pydantic's default-tolerant loading of
  `SnapshotManifest`.
- **Reason:** A future migration must not silently overwrite old
  outputs as if they were produced under the new method.
- **Alternative considered:** Hard-fail on v1 manifests. Rejected
  because it would orphan historical artifacts and break the
  point-in-time discipline.
- **Consequence:** The engine reads both. New writes carry
  `methodology-v2`. The `to_v1_state` helper maps v2 diffusion
  back to v1 for legacy UI code paths.
- **Revisit trigger:** A future v3 will require a migration
  script.

## D018 — Corporate-action guardrail is annotation-only

- **Decision:** The engine surfaces `SectorsProvider.get_corporate_actions`
  in `GroupEvidence.data_gaps` and as a per-row `caveat`. It
  does **not** silently edit prices.
- **Reason:** Per D013 the Sectors `close` basis is unverified.
  Silently editing prices would hide the unknown and could create
  look-ahead if an event date is treated as a market event.
- **Alternative considered:** Auto-exclude rows with a split
  within the horizon. Rejected for the same reason.
- **Consequence:** A user who needs the guardrail can call
  `get_corporate_actions(symbol)` explicitly. The UI surfaces the
  absence as a data gap.
- **Revisit trigger:** D013 resolved.

## D019 — Live Sectors HTTP is gated behind `allow_live=True`

- **Decision:** `SectorsClient` and `SectorsProvider` refuse to
  make any live HTTP call unless `allow_live=True` is set
  explicitly. The factory defaults to `False`; the CLI scripts
  pass `--allow-live` to opt in.
- **Reason:** Test isolation. The parity / sample pipeline must
  not accidentally spend credits. The gate also surfaces a
  clear `ProviderError` when an API key is missing in CI.
- **Alternative considered:** Environment flag. Rejected because
  the in-code flag is auditable in the test name itself.
- **Consequence:** `SectorsProvider(api_key="")` raises on every
  call. Tests use stub clients via `p.client = ...` to inject
  canned responses.
- **Revisit trigger:** Production deployment requires a
  documented opt-in path.

## D020 — Per-endpoint data-quality status

- **Decision:** Adopt the per-endpoint `EndpointQuality` model
  (READY / READY_WITH_GAPS / PARTIAL / STALE / FAILED / UNKNOWN)
  and a per-endpoint sidebar panel in the Streamlit UI.
- **Reason:** Brief §65 / §73 require the data-quality UI to
  expose separate statuses per data domain rather than one global
  flag. The current `assess_quality` is one global status; the
  per-endpoint model extends it without breaking the global
  contract.
- **Alternative considered:** Keep one global status. Rejected
  because it hides partial enrichment failures.
- **Consequence:** The snapshot writer can write an
  `endpoints.json` per snapshot directory; the UI consumes it.
  The global `status` is the roll-up (any FAILED → FAILED).
- **Revisit trigger:** Never (foundational design).

## D021 — Sectors `close` treated as raw; explicit audit script

- **Decision:** Treat Sectors `/v2/close/` `close` as **raw close**
  until a corporate-action audit proves otherwise. Ship
  `scripts/audit_close_basis.py` to perform the audit on a known
  split (BBCA.JK, 2021-10-13, ratio 5).
- **Reason:** The Sectors v2 docs do not state the adjustment
  basis (D013, `SECTORS_PRICE_BASIS.md`). The canonical frame
  duplicates `close` into `adjusted_close` so downstream code is
  unchanged when the basis is confirmed.
- **Alternative considered:** Auto-treat as adjusted. Rejected
  for the same reason as D013.
- **Consequence:** Until resolved, return math understates
  dividend income. The audit script is the next-pass action.
- **Revisit trigger:** Audit script returns a non-`RAW` verdict.

## D022 — Contradiction engine (7 heuristics)

- **Decision:** Ship 7 contradiction heuristics in
  `analytics/contradictions.py`: LEADING+NARROWING, top1>0.6,
  breadth<30, IMPROVING+negative-20D-excess, WEAKENING+positive-20D,
  plus two bonus detectors.
- **Reason:** Brief §57 requires explicit contradiction logic.
  The evidence object's `contradictions` list is the right place
  for it.
- **Alternative considered:** None — the brief requires
  contradictions.
- **Consequence:** `GroupEvidence.contradictions` may contain
  multiple `EvidenceRecord` entries per group; the UI surfaces
  them in the story card.
- **Revisit trigger:** A live stability study suggests a heuristic
  produces too many false positives.

## D023 — Screen-state invalidation (4 conditions)

- **Decision:** Ship `build_invalidation_conditions` that
  produces 4 deterministic conditions per group: 20D excess
  sign, breadth floor, diffusion shift, persistence break.
- **Reason:** Brief §58 requires deterministic screen-state
  invalidation. The product must say *"what would make us
  reconsider this group on the next refresh"* without claiming
  investment-thesis invalidation.
- **Alternative considered:** Free-form LLM. Rejected per brief
  §83.
- **Consequence:** A new `invalidation` list is added to the
  story card. The output is descriptive, not prescriptive.
- **Revisit trigger:** A live signal study suggests a condition
  fires too often.

## D024 — Story-mode UI: deterministic, no LLM

- **Decision:** Implement `app/story_mode.py` as a deterministic
  renderer of `GroupEvidence` objects. No LLM. No AI. The output
  is one `StoryCard` per group, structured for the `What Changed`
  view.
- **Reason:** Brief §59 is explicit: *"Story mode must NOT mean
  AI-generated essay."* The first productization step is a
  narrative hierarchy built from deterministic evidence.
- **Alternative considered:** Defer until an LLM is integrated.
  Rejected because the brief allows a deterministic story mode
  now and an LLM later.
- **Consequence:** The Streamlit `What Changed` tab shows up to
  5 ranked story cards + a Markdown export. LLM narration
  remains a future, gated enhancement.
- **Revisit trigger:** User demand for richer narrative; LLM
  integration when permitted.

## D025 — Four explicit provider modes; no downgrade

- **Decision:** User-visible mode is one of `DEMO_FIXTURE`,
  `PUBLIC_PROTOTYPE`, `SECTORS_FIXTURE`, or `SECTORS_LIVE`.
- **Reason:** Provider identity, fixture shape, and live status are different
  provenance claims. A cached Sectors payload or Yahoo series must not make a
  result `SECTORS_LIVE`.
- **Alternative considered:** one `provider=sectors/public/fixture` string.
  Rejected because it cannot distinguish demo, contract fixture, and live data.
- **Consequence:** Live mode requires an explicit key and live/cost flags; no
  automatic fallback is permitted. The UI badge comes from the artifact mode.
- **Revisit trigger:** Never; this is a research-integrity boundary.

## D026 — Methodology v3 is additive and old snapshots remain readable

- **Decision:** New artifacts use `methodology-v3`, `features-v3`,
  `schemas-v3`, `leadership-v2`, `diffusion-v2`, `concentration-v3`, and
  `snapshot-v2`.
- **Reason:** persistence semantics, signed-attribution status, materiality,
  nested intelligence contracts, and snapshot metadata changed materially.
- **Alternative considered:** keep labeling outputs v2. Rejected because that
  would make changed semantics appear comparable to older artifacts.
- **Consequence:** legacy fields remain additive/readable, but comparison gates
  reject incompatible method versions.
- **Revisit trigger:** a future semantic change to any analytical layer.

## D027 — Persistence counts the current observation

- **Decision:** a newly observed state has persistence 1; four consecutive
  observations display `Persistence: 4 observations`.
- **Reason:** human readers count the current observation, and a zero value can
  be mistaken for unavailable data.
- **Alternative considered:** count prior matches only. Rejected as
  counter-intuitive for the product contract.
- **Consequence:** persistence remains an integer count, never a weighted score.
- **Revisit trigger:** Never unless cadence semantics change.

## D028 — State change alone is not material

- **Decision:** leadership/diffusion transitions require corroboration from
  configured breadth, relative-strength, or rank movement before they enter the
  material feed.
- **Reason:** threshold-edge state changes can otherwise dominate `What
  Changed?` without a meaningful quantitative move.
- **Alternative considered:** every categorical transition is material.
  Rejected because it inflates churn and detached cards.
- **Consequence:** non-corroborated transitions remain auditable with reason
  `state changed without corroborating material move`.
- **Revisit trigger:** offline/live turnover evidence supports different
  thresholds, not a forward-return optimization.

## D029 — Absolute concentration is primary; signed attribution can be undefined

- **Decision:** top-1/top-3 absolute shares and HHI describe dependence on a few
  names. Signed contribution describes direction. When the signed denominator
  is near zero, signed shares return `None` with an explicit undefined status.
- **Reason:** mixed positive/negative moves can create arbitrarily large signed
  ratios even while absolute concentration is well-defined.
- **Alternative considered:** cap a misleading signed number. Rejected because
  undefined is the honest result.
- **Consequence:** the UI never substitutes signed attribution for absolute
  concentration.
- **Revisit trigger:** Never; only the numerical epsilon may be versioned.

## D030 — Benchmark-outperformance breadth is core

- **Decision:** benchmark-outperformance breadth is the canonical product
  participation metric. Positive-return and improvement breadth remain
  diagnostics.
- **Reason:** the product asks where leadership moves relative to IHSG. Exposing
  every breadth variant in the main tape obscures that question.
- **Alternative considered:** equal prominence for all metrics. Rejected for
  product clarity.
- **Consequence:** every breadth measure still retains numerator, eligible
  denominator, missing count, and total count in diagnostic contracts.
- **Revisit trigger:** a live data-quality study shows benchmark dates are not
  reliable enough for the core view.

## D031 — Conservative snapshot comparability

- **Decision:** transitions, persistence, and historical tails compare only an
  earlier snapshot with the same provider mode, methodology/feature/engine
  versions, universe version, and taxonomy version.
- **Reason:** provider or taxonomy changes can manufacture transitions; directory
  name ordering can also select a future artifact.
- **Alternative considered:** compare every adjacent directory. Rejected as a
  no-look-ahead and semantic-integrity failure.
- **Consequence:** incompatible history returns a clear warning and no delta;
  it is not coerced.
- **Revisit trigger:** define and test a deliberate universe/taxonomy migration
  bridge.

## D032 — Demo fixture is a product harness, not evidence

- **Decision:** a deterministic demo fixture produces the same coherent story
  on every run and is labeled `DEMO FIXTURE` in the UI and exports.
- **Reason:** screenshot/demo reliability should not depend on a network or a
  thin 10-name unit fixture.
- **Alternative considered:** reuse prototype snapshots or fabricate Sectors
  payloads. Rejected because either produces unstable/unconfirmed states or
  confuses provenance.
- **Consequence:** Oil & Gas, Coal, Healthcare, and Basic Materials illustrate
  broadening, narrowing, early recovery, and weakening without any live claim.
- **Revisit trigger:** replace the demo story only with another explicitly
  synthetic scenario, never a relabeled live result.

## D033 — Retain 5/20/60 and minimum group size 5 offline

- **Decision:** retain the simpler 5/20/60 baseline and minimum eligible group
  size 5 after constrained fixture/synthetic sensitivity.
- **Reason:** no alternative dominates state agreement, rank stability, churn,
  duration, and coverage; groups below 5 remain structurally prone to one-name
  jumps.
- **Alternative considered:** 10/20/60, 10/40, 20/60 and a lower minimum.
  Rejected offline because none provides a clear structural improvement.
- **Consequence:** this is an offline recommendation, not live IDX calibration.
- **Revisit trigger:** live market-wide state-turnover evidence.

## D034 — Synthetic-market harness is a methodology guardrail, not a backtest

- **Decision:** ship `tests/synthetic_market.py` with seven deterministic
  scenarios (A Healthy, B Narrow, C Early Recovery, D Deterioration, E Noisy
  Micro, F Missing Data, G Corporate Action Shock) and a golden
  `tests/test_synthetic_scenarios.py` suite.
- **Reason:** the engine has many boundary cases (small groups, missing
  rows, concentrated moves, corporate-action windows) that are not safe to
  test against forward returns and not present in the 10-ticker unit
  fixture. The synthetic harness exercises those cases without claiming
  any live market fact.
- **Alternative considered:** a fixture-based full-universe simulation.
  Rejected as over-engineered for the guardrail role; the canonical
  `FixtureProvider` and live market-wide path remain the calibration
  surface once a key is available.
- **Consequence:** every methodology change now revisits the seven golden
  outcomes; the harness is the regression wall, not the calibration.
- **Revisit trigger:** never unless a new boundary class appears.

## D035 — Group-size diffusion sensitivity is reproducible offline

- **Decision:** ship `scripts/audit_group_size_diffusion.py` and
  `tests/test_group_size_diffusion.py` as the canonical offline evidence
  for the v2 floor (`max(2, ceil(0.10 × group_size))`).
- **Reason:** the v2 floor is a structural guardrail; without a live key
  it cannot be calibrated, but it can be reproduced and reasoned about.
  A 7-size × 9-delta grid is small enough to inspect and complete enough
  to detect drift.
- **Alternative considered:** a single static test. Rejected because the
  script emits machine-readable JSON alongside the human-readable bullets
  so the live runbook can replace the inputs (live taxonomy sizes) without
  code changes.
- **Consequence:** the runbook's live calibration step has a known
  baseline. The script must be re-run when the methodology floor or
  fraction changes.
- **Revisit trigger:** change to `constituent_floor` or
  `broadening_threshold_pp` in `config/methodology.yaml`.

## D036 — Pre-existing failures fixed before any other change

- **Decision:** the two test failures detected in the baseline
  (`test_transition_event_defaults` and
  `test_row_to_group_snapshot_normalizes_nullable_parquet_values`) were
  root-caused and fixed before methodology work.
- **Reason:** shipping a refinement pass on top of silently-passing-by-
  accident tests would hide future regressions. Both bugs were visible:
  the adapter had a missing `return` statement and a dead code tail;
  the test referenced a stale schema version.
- **Alternative considered:** skip the failures. Rejected because the
  audit instruction explicitly forbids silently repairing unknown
  failures and the brief asks for an offline-pass audit.
- **Consequence:** the suite is green before any new behaviour is added.
  Subsequent additions (synthetic scenarios, group-size harness, no-look-
  ahead) are built on a known-good baseline.
- **Revisit trigger:** never.

## D037 — Brief contract frozen at v1

- **Decision:** ship `src/idx_leadership/intelligence/contract.py` as the
  single source of truth for the Markdown brief section order, the
  data-gap categories, the data-gap statuses, the intelligence
  contract version, and the provider-mode contract version. The
  section order is `Market Read → Leadership → Broadening →
  Narrowing → Material Shifts → Contradictions → Selected Evidence →
  Screen Invalidation → Data Gaps`.
- **Reason:** before more UI work, the textual mirror of the
  intelligence objects must be pinned. Renaming or reordering a
  section is a research-integrity break; the brief and the UI must
  consume the same labels.
- **Alternative considered:** a free-form brief assembled per call.
  Rejected because the next pass (live Sectors cutover) will rely on
  the brief as the canonical human-readable export.
- **Consequence:** a contract bump is now a deliberate, versioned
  change. The brief contract tests in `tests/test_brief_contract.py`
  and the end-to-end demo regression in `tests/test_e2e_demo.py`
  enforce the freeze.
- **Revisit trigger:** a future section is added or an existing one
  is renamed.

## D038 — Data gaps are structured objects, not free-form strings

- **Decision:** the intelligence contract now carries
  `DataGap(category, status, label, note)` objects with frozen
  `DataGapCategory` and `DataGapStatus` enums.
- **Reason:** the prior free-form string list produced duplicates in
  the brief and gave consumers no way to know whether a missing
  source was a `DATA_GAP`, `NOT_INTEGRATED`, `NOT_APPLIED`, or
  `PROTOTYPE`. A structured object makes the contract machine-
  readable and prevents the legacy "fundamental confirmation
  unavailable — Sectors live not connected" duplicate string from
  reappearing.
- **Alternative considered:** keep the strings but add a parallel
  structured field. Rejected as dual-source-of-truth; consumers would
  diverge.
- **Consequence:** the brief deduplicates by category; the UI mirrors
  the same shape; tests assert the frozen categories.
- **Revisit trigger:** a new category is needed.

## D039 — Contradictions and Screen Invalidation are first-class

- **Decision:** both `ContradictionRecord` and `InvalidationCondition`
  are frozen Pydantic models with explicit fields (`metric`, `label`,
  `severity`, `evidence`; and `condition`, `metric`, `threshold`,
  `rationale` respectively). The brief surfaces them in dedicated
  sections; the UI surfaces them in the evidence panel and the group
  explorer.
- **Reason:** the brief is the audit artefact. A free-form "I see
  this" line next to a group is not auditable; a structured
  contradiction is.
- **Alternative considered:** keep them as `EvidenceRecord`. Rejected
  because the field semantics diverge enough to warrant dedicated
  schemas.
- **Consequence:** the brief is now the textual mirror of the
  intelligence object, and the UI and the Markdown renderer consume
  the same source.
- **Revisit trigger:** a new contradiction or invalidation heuristic
  is added.

## D040 — End-to-end demo regression is canonical

- **Decision:** `tests/test_e2e_demo.py` is the single canonical
  regression that exercises source → snapshot → transition →
  intelligence → brief against the demo fixture. Any drift in
  the frozen contract, the brief structure, the intelligence shape,
  or the no-look-ahead invariant trips this test first.
- **Reason:** the integration-freeze pass explicitly rejected adding
  features until a single end-to-end regression confirmed the
  pipeline was intact end-to-end.
- **Alternative considered:** trusting the per-module test suite
  alone. Rejected because the failure mode "each module passes in
  isolation but the contract is broken at the join" is exactly what
  the freeze is meant to prevent.
- **Consequence:** future UI or enrichment work must keep this
  regression green.
- **Revisit trigger:** never; if a section is added, both the
  contract test and the e2e test must be updated together.
