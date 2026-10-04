# Point-in-time rotation history — Sectors, Konglo, Themes (delivered locally)

Date: 2026-10-04. Window: **2026-09-01 → 2026-10-02**, 24 trading sessions,
served against the active whole-market bundle `snap_public_market_2026-10-02`.
The rotation implementation covers all three maps, with evidence-limited
historical coverage: Daily and Weekly trails are available for 8 of 11 sectors
and 95 of 102 Themes (99 plotted). Konglo history remains unavailable for all
22 portfolios pending publication evidence. No push, no deployment, no Sectors
API calls, no paid calls.

## What is published

`app/web/public/market/rotation-2026-10-02-e71d3a145b698e0d.json`
(`schema_version: rotation-history-v1`), registered in the served
`market/index.json` **after** the asset itself (immutable content-addressed
artifact first, atomic index last). Every point carries its own
`source_ids`; every group carries comparable segments, gap records with
reasons, and cadence availability. Legacy exports, the five-date canonical
chain, and the active bundle are untouched.

| Taxonomy | Groups | Daily trails | Weekly trails | Dated observations (all segments) | In current segments |
|---|---|---|---|---|---|
| SECTOR | 11 | **8 of 11** | **8 of 11** | 264 | 196 |
| KONGLO | 22 | **0 of 22** | **0 of 22** | 0 | 0 |
| THEMES | 102 (99 plotted) | **95 of 102** (95 of 99 plotted) | **95 of 102** (95 of 99 plotted) | 2,376 | 2,286 |

Replay window: sessions 2026-09-01 … 2026-10-02. Weekly endpoints sample the
last actual session of each Monday–Sunday week: 2026-09-04, 09-11, 09-18,
09-25, and 2026-10-02 (the last week closes on its Friday, so the endpoint is
a complete week and is not labelled "week to date"). Coordinates are never
resampled: a weekly point is the daily point of that session, byte for byte.

Per-group coverage, first/last dates, segment identifiers and reasons:
`rotation-coverage-2026-10-02.csv` in this directory.

## What is deliberately NOT published

- **Konglo history: zero observations, and that is the correct result.** The
  September 30 named-holdings register (`config/market_expansion/konglo.yaml`,
  observed 2026-09-30) has no recorded publication date and no hash-bound
  availability capture. A September 30 ownership observation cannot establish
  September membership before its publication, so no Konglo session admits a
  dated version. Konglo groups remain plotted as current points from the
  snapshot, with the reason "Dated membership or eligibility publication
  evidence unavailable" surfaced in the map's History coverage panel. This
  stays unresolved until real publication evidence exists — it is not reported
  as completed history.
- **Three sector groups** (Consumer Non-Cyclicals, Healthcare, Industrials)
  end their current comparable segment with fewer than three sessions because
  newly eligible members (e.g. JELI.JK on 09-30, JECX/EMMI/PRDL in Healthcare,
  BACH.JK in Industrials) crossed the 60-session warm-up boundary mid-window.
  Their earlier segments are retained in the evidence; the UI draws no trail
  across an unsupported boundary and states "Fewer than three comparable
  observations in the current segment".
- **Seven theme groups** lack trails (four among the 99 plotted): two with no eligible members with complete
  session history (Footwear, Gas Utilities), one whose YTD baseline or warm-up
  is unavailable (Healthcare Equipment), and four with too few observations in
  the current segment (Healthcare Providers, Healthcare Supplies &
  Distributions, Processed Foods, Diversified Industrial Trading).

## Method (unchanged axes, dated observations)

- X = YTD excess return vs IHSG; Y = 20D excess − 60D excess. Equal-weight
  mean over the group's policy-eligible members with finite values. The
  canonical return engine owns every formula; the replay only changes how many
  dated sessions are observed and how cohorts are bounded.
- Membership and eligibility are resolved **per session** from hash-checked
  dated versions. A group's contract (eligible cohort ∩ members ∩ per-axis
  contributors, method, taxonomy version) defines a segment; any change —
  including a data gap — starts a new segment. Cohort hashes are never
  rewritten and never bridged.
- Replay history is a separate chart-only asset. Canonical diffusion,
  `previous_snapshot_id`, breadth history and the five-member confirmation
  gates are untouched (`snap_public_market_2026-10-02` retains
  `previous_snapshot_id: null` and `NO_COMPARABLE_HISTORY`).

## Source ledger

`SOURCE_LEDGER.json` (schema `rotation-source-ledger-v1`) binds every input to
an observation date, availability evidence and sha256. Availability is asserted
only on real evidence:

| Source | Observed | Published | Available | Basis |
|---|---|---|---|---|
| Classification (`snap_sectors_2026-08-27.json`) | 2026-08-27 | unknown | **2026-08-29** | `capture_upper_bound` — hash-bound capture stamp `20260829T004355Z` precedes the first replay session |
| Themes (`config/market_expansion/themes.yaml`) | 2026-08-27 | unknown | **2026-08-29** | `capture_upper_bound` — exact partition of the captured subindustry evidence, verified by the builder |
| Listing/board (`config/universe_market.yaml`) | 2026-10-02 | unknown | — | Oct 2 official Stock Summary observation; no earlier state asserted |
| Konglo (`config/market_expansion/konglo.yaml`) | 2026-09-30 | unknown | — | no publication evidence; never admitted |
| Ownership evidence (`docs/market-expansion-handoff/SOURCE_MANIFEST.json`) | 2026-09-30 | unknown | — | same constraint as Konglo |

The builder refuses ledgers whose availability predates their capture evidence,
whose availability claims lack publication evidence, whose membership
partitions diverge from the captured registry, whose hashes do not match, or
whose universes lack explicit board/classification values.

## Reproducing the replay (verified identical JSON content)

All inputs are offline, hash-checked, and already in the repository or in the
gitignored derived panel documented by `docs/data-refresh-handoff/HANDOFF.md`:

```bash
.venv/bin/python -m scripts.build_rotation_replay \
  --ledger docs/rotation-history-handoff/SOURCE_LEDGER.json \
  --source-root . \
  --panel data/normalized/market_validated_panel_2026-10-02 \
  --validation data/normalized/market_validated_panel_validation.json \
  --snapshot app/web/public/snapshots/snap_public_market_2026-10-02.json \
  --snapshot-provenance data/snapshots/snap_public_market_2026-10-02/panel_provenance.json \
  --out /tmp/rotation_rebuilt.json \
  --publish-root app/web/public
```

The build binds the panel to the endpoint snapshot (`panel_provenance` hashes
must match), requires a `PASS` panel-integrity report, replays every benchmark
session 2026-09-01 → 2026-10-02, enforces endpoint equality with the snapshot's
group rows and the endpoint eligible-cohort hash (`240b98cb52d5a2d3`, 760
tickers), validates the whole asset, publishes the immutable artifact, and only
then rewrites `market/index.json` atomically. Omit `--publish-root` to build
the report without publishing. Rerunning this command reproduced the served
asset with identical parsed JSON content. The indented CLI `--out` report and
compact served asset are **not byte-identical**; their formatting differs.

## Verification evidence

| Gate | Command | Result |
|---|---|---|
| Rotation regressions | `.venv/bin/python -m pytest tests/test_point_in_time_rotation.py -q` | **21 passed** — future/unknown publication never backdated; publication bound starts history on the availability date; membership change splits segments without touching other taxonomies; eligibility change is a new contract; unrelated eligibility change does not disable a stable group; capture-upper-bound distinct from unknown; ledger backdating refused; duplicate rows, NaN prices, quarantined tickers, missing sessions and endpoint mismatches all refused; missing security session breaks history and never fills; no YTD baseline means no rotation point; stale ledger hash refused; tampered report cannot replace a published asset or the index; frontend cadence/endpoint/per-group gates exercised via `tsx` |
| Full suite | `.venv/bin/python -m pytest -q` | **832 passed**, 2 pre-existing deprecation warnings; tree guard confirms no tracked file was modified by the run |
| Typecheck / build | `npm run typecheck --prefix app/web` / `npm run build` | clean (chunk-size advisory pre-existing) |
| Independent recalculation | offline script over the raw panel | **7,920 historical axis comparisons** (`INDEPENDENT_CHECKS.json`), plus six separate current Konglo endpoint comparisons in the earlier audit — every point of every published SECTOR and THEMES segment recomputed with plain arithmetic from `prices.csv`/`benchmark.csv` (own-sequence horizon returns, common-calendar YTD), every contributor checked against the 20/60-session warm-up contract; eligibility re-derived from the documented policy reproduces the endpoint cohort hash exactly (240b98cb52d5a2d3, 760 tickers); Konglo endpoint values reconciled against the snapshot within its published 4-decimal rounding; weekly points verified coordinate-identical subsets of daily points; segment contiguity and boundary non-bridging verified; memberships cross-checked against the dated registry and themes configuration. **PASS** |
| Browser QC | production build on `vite preview`, Chrome headless | **37/37 passed** (`BROWSER_QA.json` in this directory) — all three maps render; Daily/Weekly switch and persist `?interval=`; tail draws 8 sector and 95 theme trails; phase filters and search reduce the plotted set; Konglo cadence disabled with 22 current points, zero invented polylines, reason and unavailable note surfaced; stocks mode renders without offering group history; no horizontal overflow at 1440/768/390; mobile nav opens; **0 console errors, 0 page errors, 0 Sectors API requests** |

The independent recalculation deliberately does not import
`idx_leadership` feature code: eligibility is re-derived from the policy
contract and the panel itself, equal-weight means are plain arithmetic, and the
comparison runs against the published artifact. It confirmed the replay's own
warm-up rule (a contributor must cover every benchmark session of the window)
and the canonical own-sequence horizon convention (a stock with a row on a date
the benchmark lacks computes its 20/60-day return over its own sequence — this
is the established prototype methodology, unchanged).

## Boundaries (unchanged)

Longer backfills, loading-performance work, new ownership claims, and formula
changes remain out of scope. The replay uses the latest evidenced disclosure
available by each close and a later-retrieved price vintage — it is not an
archived real-time feed. Intervening unrecorded register changes are not
asserted absent. Five-member confirmation requirements are independent of
trail availability. Sectors remains HOLD; no live or paid provider was called.

## Completion verification — 5 October 2026

- Actual clean clone of `4cfd9cc` at `/private/tmp/idx-rotation-clean-4cfd9cc`:
  **832 passed, zero skips, two pre-existing warnings**, exit 0. Imports and
  `project_root()` were asserted inside the clone before execution. The clone
  had no raw cache or frontend `node_modules`, and remained Git-clean afterward.
  Existing Python dependencies were reused with the clone's `src` explicitly
  first on `PYTHONPATH`; no original-checkout import was permitted.
- Rechecked all **7,920 published historical axis values** with independent CSV
  arithmetic (no feature-engine imports). Maximum absolute difference:
  **1.1368683772161603e-13 percentage points**. The report and exact asset hash
  are saved in `INDEPENDENT_CHECKS.json`. This count excludes the six current
  Konglo endpoint comparisons included in the earlier 7,926-check audit;
  no historical Konglo observations exist to compare.
- Rechecked the built preview using the in-app browser: 8 sector Weekly trails
  with five points each; 95 Theme trails; a Coal search reduced Themes to three
  matching trails; Konglo retained 22 current groups with disabled cadence
  controls, zero trails and explicit publication-evidence reasons. At 390px,
  all three views had no document-level horizontal overflow. The viewport
  override was reset afterward.
- Corrected two documentation errors: seven Themes lack trails (four of those
  are plotted); the canonical active snapshot has no comparable prior.
  No calculations, source assets or snapshot bundles changed in this completion
  pass. Implementation remains in local commits `9353632`, `2e2a702`, `17cc5d2`;
  no push or deployment was performed.

## Local delivery commits

- `9353632`: dated replay engine and source ledger.
- `2e2a702`: published rotation asset and map controls.
- `17cc5d2`: hermetic regression coverage.
- `4cfd9cc`: coverage, replay instructions and browser QC handoff.
- `32fa4b8`: clean-clone verification and independent arithmetic report.

These identify the implementation and verification milestones; later
documentation corrections are recorded in Git history. This is a local
delivery, with no push or deployment.
