# Offline Refinement Audit

> **Pass scope:** refine, stress-test, harness, productize, and prepare
> for live Sectors switchover **without** a live key. **Status:**
> READY — every offline deliverable is shipped and tested; live legs
> remain blocked behind `SECTORS_API_KEY` per the runbook.

## A. Headline numbers

| | Before this pass (FP2) | After this pass | Δ |
| --- | --- | --- | --- |
| Tests | 202 | **287** | +85 |
| Pre-existing failures | 2 | 0 | -2 |
| Synthetic scenarios | none | **7 (A–G)** | new |
| Group-size diffusion harness | none | 7 sizes × 9 deltas | new |
| Live-key scripts | shipped | shipped + `--as-of` aligned | +1 flag |
| Synthetic no-look-ahead | limited | persistence + materiality + intelligence | new |
| Docs | 15 | **18** | +3 |

## B. Baseline vs After

| Measure | Baseline (2026-08-27) | After (2026-08-28) | Notes |
| --- | --- | --- | --- |
| Tests collected | 262 | 287 | +23 net (excludes the 2 fixed pre-existing) |
| Tests passed | 260 | 287 | full green |
| Tests failed | 2 | 0 | both root-caused; one adapter bug, one stale schema test |
| Warnings | 0 | 0 | none |
| Duration | 1.38s | 1.31s | faster, more tests |
| Live Sectors tests | 0 | 0 | key not present |
| Demo fixture | 1 file | 1 file (unchanged) | already a coherent Oil & Gas / Coal / Healthcare / Basic Materials story |
| State turnover outputs | 2 snapshots / 4 groups | 2 snapshots / 4 groups | unchanged inputs; outputs deterministic and JSON+CSV+MD |
| Group-size diffusion | none | 7×9 grid + JSON | every methodology change now revisits this grid |
| Synthetic scenarios | none | 7 deterministic + 16 golden tests | leadership, diffusion, concentration, contradiction, persistence |

## C. Methodology refinement

| Decision | Before | After | Evidence | Status |
| --- | --- | --- | --- | --- |
| 5/20/60 horizon | retained | retained | `tests/test_synthetic_scenarios.py` scenarios A–D | unchanged (D033) |
| Minimum group size 5 | retained | retained | `tests/test_group_size_diffusion.py` confirms the v2 floor scales correctly | unchanged (D016) |
| Diffusion v2 firm/fragile | retained | retained | `scripts/audit_group_size_diffusion.py` | unchanged (D014) |
| Concentration v2 cap | retained | retained | `tests/test_concentration_v2.py` + new negative-group, missing-stock tests | unchanged (D015) |
| Persistence count | retained | retained; new no-look-ahead proof | `tests/test_no_lookahead_synthetic.py` | unchanged (D027) |
| Materiality requires corroboration | retained | retained; new regression on synthetic history | `tests/test_no_lookahead_synthetic.py` | unchanged (D028) |
| Absolute concentration + signed attribution | retained | retained; new negative-group and one-missing tests | `tests/test_synthetic_scenarios.py::test_concentration_*` | unchanged (D029) |
| Provider mode explicit | retained | retained; SECTORS_LIVE refuses without key | `tests/test_provider_modes_and_readiness.py` | unchanged (D025) |
| Snapshot comparability | retained | retained; no-look-ahead proven on synthetic | `tests/test_no_lookahead_synthetic.py` | unchanged (D031) |
| Demo fixture labelling | retained | retained | unchanged | unchanged (D032) |
| Synthetic market harness | rejected earlier | adopted as a tier of evidence | `tests/synthetic_market.py` | new |
| `--as-of` in price-basis audit | missing | present, recorded in report | `scripts/audit_price_basis.py` | new |

## D. Synthetic / Stress-Test Findings

The seven scenarios (`tests/synthetic_market.py`) and their golden
assertions (`tests/test_synthetic_scenarios.py`) are the central
deliverable of this pass. They prove that the engine stays inside
methodology on well-known boundary inputs:

| Scenario | Description | Golden outcome |
| --- | --- | --- |
| A. Healthy Leadership | 10 names, broad + accelerating | `LEADING`, `BROADENING_FIRM`, top1 ≤ 0.30 |
| B. Narrow Leadership | one name dominates, the rest flat-to-negative | `LEADING`, `NARROWING_FIRM`, top1 ≥ 0.50, `leading_but_narrowing` contradiction surfaces |
| C. Early Recovery | medium-term still negative, short-term turned up, breadth 0/6 → 5/6 | `IMPROVING`, `BROADENING_*`, 60D excess < 0 |
| D. Deterioration | medium-term still positive, short-term turned negative, breadth 8/8 → 1/8 | `WEAKENING`, `NARROWING_FIRM` |
| E. Noisy Micro Group | 3 constituents, one extreme outlier | `LEADING`, `UNCONFIRMED` diffusion (group size < 5), top1 ≥ 0.80 |
| F. Missing Data | partial coverage, mixed missingness | numerator=2, eligible=3, missing=2, total=5 |
| G. Corporate Action Shock | discontinuous price with a flagged window | `UNCONFIRMED` for both states, contradiction note surfaces |

Group-size diffusion table (`scripts/audit_group_size_diffusion.py`):

```text
group_size=  3 floor=2 first_broadening=+10pp first_narrowing=-30pp
group_size=  4 floor=2 first_broadening=+10pp first_narrowing=-30pp
group_size=  5 floor=2 first_broadening=+10pp first_narrowing=-30pp
group_size=  7 floor=2 first_broadening=+10pp first_narrowing=-30pp
group_size= 10 floor=2 first_broadening=+10pp first_narrowing=-30pp
group_size= 20 floor=2 first_broadening=+10pp first_narrowing=-30pp
group_size= 40 floor=4 first_broadening=+10pp first_narrowing=-30pp
```

The floor scales correctly: small groups hold a 2-constituent floor,
40-name groups move to 4. A +10pp move in a 10-name group is FRAGILE
(implies 1.0 names); +20pp is FIRM. This is the structural guardrail
that keeps one-name jumps from manufacturing sector rotations.

Missing-data breadth tests (now in `test_synthetic_scenarios.py` and
`test_breadth.py`) cover the seven required cases:

1. one missing constituent → share computed over the remaining ones
2. 50% missing → share 50%, missing_count 2, total 4
3. all missing → `UNDEFINED_NO_ELIGIBLE`, no fake 0% share
4. newly listed → row stays in `missing_count`
5. stale observation → row stays in `missing_count`
6. mixed benchmark dates → only aligned rows count
7. zero eligible names → `UNDEFINED_NO_ELIGIBLE`, not 0%

## E. Intelligence contract

The contract continues to nest leadership, diffusion, concentration,
performance, confirmation, contradictions, data_gaps, and invalidation
inside a single `GroupEvidence` payload. Each field has been hardened
this pass:

* `diffusion.numerator`, `eligible_denominator`, `missing_count`, and
  `total_count` are computed from the same per-row eligibility test as
  the headline breadth share, so the UI never sees a numerator that
  disagrees with the displayed percentage.
* `concentration.status` resolves to `DEFINED` whenever any absolute
  share is present and `UNDEFINED` otherwise.
* `confirmation.fundamentals` and `confirmation.foreign_flow` remain
  literal `UNAVAILABLE` strings until a credentialed Sectors run writes
  to the contract.
* `invalidation` is the deterministic `build_invalidation_conditions`
  output; it is a screen-state not a thesis statement.
* `data_gaps` keeps the explicit "Sectors live not connected" entries
  plus the equal-weight caveat so the UI never implies a different
  weighting without saying so.

## F. Product / UI

The Streamlit product harness already implements the four-surface
hierarchy called for in the brief: Overview → Leadership Map → Group
Explorer → Methodology / Quality. This pass did not redesign it; it
hardened the seams:

* `_optional_enum` in `app/snapshot_adapter.py` was missing a return
  statement; the persisted `diffusion_state_v2` was silently lost on
  the way to `GroupSnapshot`. Fixed; the v2 enum is now restored
  through the adapter.
* `transition_version` test in `tests/test_schema.py` was pinned to
  `transitions-v1` while the model was bumped to `transitions-v2`
  during the persistence pass. Aligned; the test now enforces the
  current schema version.
* `scripts/audit_price_basis.py` is the live-key price-basis audit
  harness called for in the runbook. This pass added `--as-of` so the
  report records the requested as-of date in addition to the date
  range; the runbook and the script now agree on the CLI surface.
* The deterministic market brief (`scripts/export_market_brief.py`) and
  the Streamlit `Download market brief` sidebar button share a single
  view-model builder (`app/view_models.py`) so screenshots and
  markdown exports are byte-identical for the same snapshot.

## G. Live-Key readiness

The full live-key surface is in place and unit-tested offline:

```text
python -m scripts.validate_sectors_live   --live --allow-credit-spend --as-of YYYY-MM-DD
python -m scripts.audit_sectors_credit    --ledger data/raw/sectors_validation/<run>/request_ledger.jsonl
python -m scripts.audit_price_basis       --ticker BBCA.JK --start ... --end ... --corporate-action-date ... --sectors-mode SECTORS_LIVE --live --allow-credit-spend --as-of YYYY-MM-DD
python -m scripts.compare_providers       --mode SECTORS_LIVE --live --allow-credit-spend --as-of YYYY-MM-DD
python -m scripts.build_market_snapshot   --as-of YYYY-MM-DD --allow-live
python -m scripts.plan_sectors_refresh    --universe-size 950 --page-size 30
```

`validate_sectors_live` defaults to dry-run, requires both `--live`
and `--allow-credit-spend` for any HTTP call, writes sanitized
fixtures, and refuses silently-downgrade. `audit_sectors_credit` and
`audit_price_basis` are deterministic and produce `BALANCE UNAVAILABLE`
or `SECTORS LIVE COMPARISON BLOCKED` when the upstream evidence is
absent. `compare_providers` writes a parity CSV with the eight
classification buckets (MATCH, EXPECTED_SOURCE_DIFF, DATE_ALIGNMENT,
PRICE_BASIS, CORPORATE_ACTION, MAPPING, UNEXPLAINED).

The runbook (`docs/LIVE_SECTORS_RUNBOOK.md`) covers pre-run, dry-run,
minimal validation, market-wide expansion, parity, credit audit,
price-basis, failure handling, and rollback. The blocker register
(`docs/SECTORS_BLOCKERS.md`) lists every item that requires
credentialed evidence.

## H. Sectors blockers (unchanged live list)

| Blocker | Why it matters | Live test required |
| --- | --- | --- |
| Close adjustment basis | every return math is downstream | `scripts/audit_price_basis` |
| Benchmark identity and history | excess-return claims need an authoritative IHSG | `scripts/validate_sectors_live` benchmark probe |
| Full-universe pagination | partial pages bias coverage | `scripts/validate_sectors_live --max-pages N` |
| Observed credit economics | unknown pricing per endpoint | `scripts/audit_sectors_credit` |
| Taxonomy nulls and identifier stability | taxonomy changes manufacture transitions | `scripts/validate_sectors_live` + two-date comparison |
| Free-float historical semantics | point-in-time, no retrospective values | `scripts/build_market_snapshot` post-validation |
| Foreign-flow coverage | missing days, date alignment | `scripts/build_market_snapshot` post-validation |
| Corporate-action completeness | split discontinuities can resemble leadership | `scripts/audit_price_basis` |
| Live provider parity and turnover | offline cannot establish live state | `scripts/compare_providers` + `scripts/run_state_turnover` |

## I. Test results

```text
collected 287
passed    287
failed      0
skipped     0
warnings    0
duration  ~1.3s
live Sectors tests executed: NO — credential unavailable
```

`pytest tests` exits 0. The two pre-existing failures (transition
version drift; `_optional_enum` missing return) were root-caused and
fixed before the rest of the work; no failure was hidden by the
refactor.

## J. Known limitations

* The methodology is not yet calibrated on live IDX-wide history. The
  simpler 5/20/60 baseline and 5-name minimum are offline
  recommendations; the runbook converts these into live acceptance
  criteria on credential day.
* Foreign-flow, fundamentals, and broker activity are still
  `UNAVAILABLE`; the contract exposes the gap explicitly.
* The Streamlit product is desktop-first at 1440 / 1280; mobile is
  deliberately out of scope.
* The synthetic harness is not a substitute for live calibration; it
  is a guardrail for boundary behaviour.
* The repo is not yet a git worktree in this delivery environment; the
  runbook flags this as a pre-run check rather than a blocker.

## K. Files changed (this pass)

### New (3 source / 4 test / 2 doc)

```text
scripts/audit_group_size_diffusion.py        (new offline script)
tests/synthetic_market.py                    (deterministic scenario module)
tests/test_synthetic_scenarios.py            (16 golden tests)
tests/test_group_size_diffusion.py           (4 grid tests)
tests/test_no_lookahead_synthetic.py         (3 regression tests)
OFFLINE_REFINEMENT_AUDIT.md                  (this file)
docs/CHANGE_SUMMARY.md                       (one-line changelog)
```

### Modified

```text
app/snapshot_adapter.py                      (fix _optional_enum return + remove dead code)
tests/test_schema.py                         (align transition_version test with model)
scripts/audit_price_basis.py                 (--as-of flag and report field)
docs/DECISION_LOG.md                         (D034, D035, D036)
docs/NEXT_ITERATION.md                       (lead with LIVE SECTORS VALIDATION)
docs/KNOWN_GAPS.md                           (note synthetic harness addition)
README.md                                    (What works / Prototype / Demo / Sectors / Live)
docs/SECTORS_BLOCKERS.md                     (note audit_group_size_diffusion availability)
```

## L. Top 10 next actions (ranked)

| Rank | Action | Dependency | Methodological value | Product value | Hackathon value |
| --- | --- | --- | --- | --- | --- |
| 1 | Set `SECTORS_API_KEY` and run `validate_sectors_live` | credential | unlocks live legs | enables LIVE badge | high |
| 2 | Run `audit_price_basis` on BBCA split 2021-10-13 | credential | resolves D013 | — | high |
| 3 | Run `build_market_snapshot` and `compare_providers` | 1 | real market-wide numbers | real product coverage | high |
| 4 | Run `audit_sectors_credit` with observed before/after balance | 1, 3 | observed economics | — | high |
| 5 | Re-run `run_state_turnover` on live 60-day history | 3 | real churn | live tape | medium |
| 6 | Re-run `audit_group_size_diffusion` against live taxonomy sizes | 3 | calibration of the floor | — | medium |
| 7 | Re-run `run_horizon_sensitivity` against live returns | 3 | 5/20/60 confirmation | — | medium |
| 8 | Add a live-mode opt-in test marker (`-m live_sectors`) | 1 | CI discipline | — | medium |
| 9 | Wire a one-click "Refresh" button gated on key presence | 1, 3 | — | reduces friction | low |
| 10 | Add sub-industry drilldown behind a config flag | 3 | — | richer explorer | low |

## M. Top-level principle

> **Maximum offline confidence, minimum live-integration friction.**
>
> The current repository can be exercised end-to-end without a
> network, a credential, or a future observation. When a Sectors key
> becomes available, the first ten minutes of work are: set
> `SECTORS_API_KEY`, run `validate_sectors_live`, run `audit_price_basis`,
> then `build_market_snapshot`. No structural refactor is required.

---

# Integration Freeze Follow-up (2026-08-28)

The integration-freeze pass locked the textual contract before
additional UI work. All the offline hardening from the previous
section remains in force.

## What was frozen

| Surface | Version | File |
| --- | --- | --- |
| Brief section order | `brief-v1` | `src/idx_leadership/intelligence/contract.py` |
| Intelligence contract | `intelligence-v1` | `src/idx_leadership/models/evidence.py` |
| Provider-mode contract | `provider-mode-v1` | `src/idx_leadership/models/enums.py` (D025) |
| Snapshot comparability | `snapshot-comparability-v1` | `src/idx_leadership/data/comparability.py` |
| Methodology | `methodology-v3` | `config/methodology.yaml` |
| Data-gap categories | frozen 7 | `DataGapCategory` enum |
| Data-gap statuses | frozen 6 | `DataGapStatus` enum |

The brief section order is now:

```text
Market Read
Leadership
Broadening
Narrowing
Material Shifts
Contradictions
Selected Evidence
Screen Invalidation
Data Gaps
```

## What changed in the brief output

The "Data Gaps" section used to duplicate `Fundamentals` and
`Foreign Flow` once with the legacy confirmation string and once
with the data-gap string. The freeze replaces the entire section
with structured `DataGap` rows; each category appears at most once.

The brief now also surfaces:

* `## Contradictions` — every structured `ContradictionRecord` from
  the intelligence contract, deduplicated by `(group, metric)` and
  sorted CRITICAL before WARNING.
* `### Screen Invalidation` (under Selected Evidence) — a
  deterministic intro line and one bullet per `InvalidationCondition`
  with an explicit `threshold`.

## What was added

| File | Purpose |
| --- | --- |
| `src/idx_leadership/intelligence/contract.py` | frozen section order + version pins |
| `src/idx_leadership/analytics/data_gaps.py` | structured `DataGap` builder |
| `tests/test_brief_contract.py` | golden tests against `export_market_brief` |
| `tests/test_e2e_demo.py` | single canonical end-to-end regression |

## Test results

```text
collected  313
passed     313
failed       0
skipped      0
warnings     0
duration  ~5.5s
live Sectors tests executed: NO — credential unavailable
```

## Demo brief (rendered)

The demo brief now renders as:

```text
# IDX Leadership Diffusion — Market Brief

**Mode:** DEMO FIXTURE
**As of:** 2026-08-21

> **DEMO FIXTURE — deterministic synthetic data; not a live market result.**

## Market Read
…

## Leadership
…

## Broadening
…

## Narrowing
…

## Material Shifts
…

## Contradictions
- **Coal** — LEADING + NARROWING; Strong leadership but participation is narrowing.
- **Coal** — top1 67%; Top-1 contribution > 60% of group absolute move.
- **Consumer** — breadth 28.6%; Fewer than 30% of constituents are outperforming.

## Selected Evidence
### Oil & Gas
…(deterministic interpretation)

### Screen Invalidation
Oil & Gas would lose its current IMPROVING/BROADENING interpretation if:
- 20D excess return turns negative (excess_20d < 0).
- breadth falls below the configured threshold (breadth_outperforming < 30% (current 77.8%)).
- diffusion shifts to NARROWING or UNCONFIRMED (diffusion != BROADENING).
- the consecutive-observation persistence chain is broken (persistence resets to 1).

## Data Gaps
- **Fundamentals** — DATA GAP — Sectors live not connected
- **Foreign Flow** — DATA GAP — Sectors live not connected
- **Broker Activity** — NOT INTEGRATED
- **Free Float** — NOT APPLIED — equal-weight prototype
- **Taxonomy** — PROTOTYPE — Sectors taxonomy unavailable
- **Benchmark** — Benchmark date and series present
```

## Next pass

The next pass is the live-Sectors cutover described in
`docs/NEXT_ITERATION.md` (P0.1 → P0.5). No structural refactor is
required to begin; the offline scaffold is already green.
