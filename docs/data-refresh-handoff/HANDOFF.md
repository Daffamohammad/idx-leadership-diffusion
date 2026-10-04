# Data refresh handoff — IDX Leadership Diffusion (as of 2026-10-02)

**Refresh window:** 2026-08-27 (previous active bundle) → 2026-10-02 (latest trading session)
**Active snapshot:** `snap_public_2026-10-02` · PUBLIC_PROTOTYPE · price basis `adjusted_close`
**Sectors API calls: 0** (preflight, credit, connectivity — the provider was never invoked)

### Files in this handoff

| File | Contents |
|---|---|
| `HANDOFF.md` | this document (sources, coverage, calculations, lineage, ledger, tests, runbook, outcome matrix) |
| `source-manifest.json` | sha256 + session for all 13 cached official IDX files (copy of `data/raw/official_sources_manifest.json`) |
| `panel-validation-report.json` | full cross-check report (copy of `data/normalized/public_panel_validation.json`) |
| `snapshot-chain-report.json` | per-snapshot chain summary and hash parity (copy of `data/normalized/public_chain_report.json`) |
| `group-coverage-2026-10-02.csv` | per-group coverage and metrics table |
| `research-ledger.jsonl` | every research/parser request with counts, status, and outcome |

---

## 1. Source manifest

### 1.1 Official IDX sources (validation evidence)

Cached unmodified under `data/raw/`, hashed in `data/raw/official_sources_manifest.json`
(sha256 per file; 13 files).

| Source | Sessions | Role | Provenance |
|---|---|---|---|
| `Composite Stock Price Index & Stock Trading Volume - Sep 2026.xlsx` | 218 sessions, 2025-09-30 → 2026-08-31 | Benchmark validation (official IHSG close) | IDX statistical reports (user-supplied download) |
| `Stock Summary-20261002.xlsx` | 963 codes, session 2026-10-02 | Per-stock validation (official unadjusted close) | IDX Stock Summary (user-supplied download) |
| `ds_260828.pdf`, `ds_260921.pdf` … `ds_261002.pdf` | 11 sessions, 2026-08-28 + 2026-09-21 → 2026-10-02 | Benchmark validation (IHSG close + change) | IDX Daily Statistics |
| `idx_daily_statistics_2026-10-02.json` | 2026-10-02 | Browser market-context card (LlamaParse) | `scripts.refresh_idx_daily_statistics` |

Provenance detail: IDX publishes Daily Statistics PDFs at
`https://www.idx.co.id/Media/<token>/ds_YYMMDD.pdf`, where `<token>` is random per file and
not derivable; the authoritative index page
`https://www.idx.co.id/en/market-data/statistical-reports/statistics/` returns **HTTP 403** to
automated fetches (bot protection). Provenance is therefore recorded at the index-page level,
and every cached file is content-hashed (see ledger WP-B).

### 1.2 Market data source

| Field | Value |
|---|---|
| Provider | yfinance (Yahoo Finance public chart API), repo default `PUBLIC_PROTOTYPE` |
| Endpoint | `https://query1.finance.yahoo.com/v8/finance/chart/<ticker>?period1&period2&interval=1d` |
| Window | 2025-12-15 → 2026-10-02 (188 benchmark sessions, 192 per ticker) |
| Requests | 55 (54 tickers + 1 benchmark); 54 succeeded, 1 failed, retried per provider policy |
| Artifact | `data/raw/public/panel_2025-12-15_2026-10-04/` (`prices.csv`, `benchmark.csv`, `source_manifest.json` with sha256s) |
| Fetch log | `data/raw/request_ledger.jsonl` |

### 1.3 Units and price basis

| Quantity | Unit / basis |
|---|---|
| Stock prices | IDR per share; `close` = raw official close, `adjusted_close` = dividend/split adjusted |
| Benchmark `^JKSE` | IDX Composite (IHSG) index points, `close` basis (no adjustment) |
| Volume | shares |
| Return series (methodology) | stocks `adjusted_close`, benchmark `close` → this is the established prototype methodology, unchanged |
| Official comparison | always against raw `close` (unadjusted), never a reconstructed value |
| Foreign flow | aggregate = **billion IDR net value**; per-stock = **share quantities** (never × price) |

Corporate actions: 44 of 53 tickers have `adjusted_close ≠ close` somewhere in the window
(dividends). Full list and per-ticker divergent-row counts: `corporate_actions` block of
`tests/fixtures/public_panel_validation.json`. Returns use the adjusted basis; official
validation uses the raw basis. No rounded or reconstructed price is ever written.

### 1.4 Scope and constraints honoured

- Sectors API: **0 requests**. `build_provider_from_config(mode="PUBLIC_PROTOTYPE")` only;
  no `--allow-live`, no credit ceiling consumed.
- Research ceilings: web search 4 requests (2 work packages), parser 1 distinct public document
  / 2 pages / 20 credits.
- Fail-closed comparability, 65% foreign-flow mapping gate, 60% coverage gate, group minimum
  (5 eligible constituents) — all unchanged and enforced.

---

## 2. Coverage

### 2.1 Refresh accounting (requested → eligible)

| Stage | Count | Note |
|---|---|---|
| Requested tickers | 54 | `config/universe.yaml` prototype universe |
| Downloaded | 53 | 1 failure |
| Failed / empty | 1 | `WSKT.JK` (Yahoo 404 "possibly delisted"; in official Stock Summary, absent from the Sectors 962 registry) |
| Usable (≥60 sessions) | 53 | eligibility history requirement |
| YTD-baseline present | 53 | all at session **2025-12-30** |
| Eligible in snapshot | 54 | WSKT is policy-eligible but carries no data → `missing_count` in its group |
| Coverage status | `READY_WITH_GAPS` 98.15% | disclosed in `quality.issues` as `failed_securities=['WSKT.JK']` |

### 2.2 Three distinct populations (never merged)

| Population | Count | Source |
|---|---|---|
| Official listed codes | **963** | Stock Summary 2026-10-02 |
| Sectors snapshot registry | **962** | validated live capture 2026-08-28 |
| Prototype universe | **54** requested / 53 with data | `config/universe.yaml` |

These are different populations by construction (all listed codes vs. a validated capture vs. an
analyst prototype subset). No count was forced to equal another; WSKT appears in the official
list, not in the Sectors registry, and not on Yahoo — that three-way split is reported as-is.

### 2.3 Coverage by group (2026-10-02)

| Group | Eligible | Missing | YTD excess % | 20D % | 60D % | Breadth % | Δ breadth (pp) | Diffusion v2 |
|---|---|---|---|---|---|---|---|---|
| Energy | 9 | 0 | +39.34 | +3.55 | +7.58 | 66.67 | 0.00 | STABLE |
| Consumer | 10 | 0 | +19.06 | +4.23 | −0.11 | 80.00 | **+40.00** | BROADENING_FIRM |
| Financials | 10 | 0 | +8.95 | −2.46 | −7.35 | 50.00 | 0.00 | STABLE |
| Telecom | 3 | 0 | +8.57 | −1.57 | −1.40 | 33.33 | +33.33 | UNCONFIRMED |
| Industrial | 7 | 1 (WSKT) | +3.23 | −0.54 | −3.10 | 42.86 | **−28.57** | NARROWING_FIRM |
| Property | 4 | 0 | −2.28 | −9.13 | −6.89 | 25.00 | 0.00 | UNCONFIRMED |
| Healthcare | 3 | 0 | −6.71 | −1.39 | −18.02 | 33.33 | +33.33 | UNCONFIRMED |
| Materials | 3 | 0 | −11.72 | −8.22 | −5.03 | 0.00 | 0.00 | UNCONFIRMED |
| Transportation | 1 | 0 | −18.79 | −16.34 | −6.63 | 0.00 | 0.00 | UNCONFIRMED |
| Technology | 3 | 0 | −20.20 | −15.81 | −20.27 | 33.33 | −33.34 | UNCONFIRMED |

Groups below the 5-eligible minimum stay `UNCONFIRMED` **with their real breadth numbers still
visible** — the gate suppresses the classification, not the data.

### 2.4 Coverage by date

| Date | Snapshot | Role |
|---|---|---|
| 2026-08-28 | `snap_2026-08-28` | prior public capture (incomparable cohort, see §4) |
| 2026-09-04 → 2026-09-25 | `snap_public_2026-09-{04,11,18,25}` | chain priors |
| 2026-10-02 | `snap_public_2026-10-02` | **active** |
| 2026-09-21 → 2026-10-02 | ds PDFs | official benchmark checks |
| through 2026-08-31 | composite workbook | official benchmark checks |

---

## 3. Calculation checks

Report: `panel-validation-report.json` (this directory; live copy at
`data/normalized/public_panel_validation.json`, which is gitignored);
enforced by `tests/test_public_refresh_chain.py` against the tracked
`tests/fixtures/public_panel_validation.json`.

| Check | Threshold | Result |
|---|---|---|
| Benchmark vs official workbook | ≥150 sessions, ≤0.01 idx pts | **164 sessions, max diff 0.0053, 0 mismatches** |
| Benchmark vs 11 ds PDFs | every date ≤0.01 | **11/11, max diff 0.0002** |
| Stocks vs official Stock Summary | ≥95% within 1 IDR | **53/53 exact (0.0 IDR)** |
| YTD baseline | 2025-12-30 present for all | **53/53** |
| Panel integrity | no duplicates/non-positive | **0 / 0**, 10,205 rows |

Representative examples:

- **YTD baseline.** Official 2025-12-30 IHSG close **8646.94** vs panel **8646.938**
  (diff 0.0015). Every feature's `return_ytd_start_date = 2025-12-30`.
- **Benchmark YTD return.** `(6036.888 / 8646.94 − 1) × 100 = −30.1847%`; the payload publishes
  `benchmark_return_ytd = −30.18%` for every group (asserted in tests).
- **Per-stock YTD.** BBCA: stock YTD −20.85% vs benchmark −30.18% → excess **+9.34%**, computed
  from `adjusted_close` 2025-12-30 → 2026-10-02.
- **Group YTD excess.** Energy +39.34% = equal-weight group return minus benchmark YTD.
- **Breadth delta.** Consumer 80.00% now vs 40.00% on 2026-09-25 → **+40.00 pp**, and the
  transition evidence string reads `breadth +40.0pp`.
- **Rotation momentum.** Industrial: 20D −0.54% − 60D −3.10% = **+2.56%** relative momentum,
  identical in the export (`relative_momentum`) and in the plotted trail.

---

## 4. Snapshot lineage and comparability

Chain built by `scripts/build_snapshot_chain.py` (offline, deterministic) from one persisted
panel, chronological so each snapshot sees a real compatible prior.

| Snapshot | as_of | Eligible | Hash | Selected previous |
|---|---|---|---|---|
| `snap_public_2026-09-04` | 2026-09-04 | 54 | `5ee90b3d073b02ec` | — (first in cohort) |
| `snap_public_2026-09-11` | 2026-09-11 | 54 | `5ee90b3d073b02ec` | `snap_public_2026-09-04` |
| `snap_public_2026-09-18` | 2026-09-18 | 54 | `5ee90b3d073b02ec` | `snap_public_2026-09-11` |
| `snap_public_2026-09-25` | 2026-09-25 | 54 | `5ee90b3d073b02ec` | `snap_public_2026-09-18` |
| `snap_public_2026-10-02` | 2026-10-02 | 54 | `5ee90b3d073b02ec` | `snap_public_2026-09-25` |

Parity is enforced, not assumed: the script compares `eligible_ticker_set_hash` across every
built snapshot and **exits 2** on mismatch. Chain report: `snapshot-chain-report.json`.

Comparability decisions on the active snapshot (18 candidates checked, fail-closed):

- **COMPATIBLE:** the four chain priors (identical provider mode, price basis, all version
  fields, and eligible-set hash).
- **INCOMPARABLE:** `snap_sectors_2026-08-27` (different provider mode, price basis, universe
  and taxonomy versions, cohort), and the August public captures
  (`snap_public_2026-08-20`, `snap_2026-08-28`, `yf_harness_*`, `yfinance_harness`).

**Why the August public snapshots are not comparable — documented, not hidden.** They were built
from a panel in which `WSKT.JK` had a single stray session, which failed the 60-session history
rule and was excluded (`insufficient_history`) → hash `a08b5e598af9551c`, 53 eligible. In the
refreshed panel Yahoo returns nothing at all for WSKT (HTTP 404), so it is an acquisition gap
rather than a thin history; per `market_universe.py` an acquisition issue bypasses only the
data-availability checks, leaving WSKT policy-eligible → hash `5ee90b3d073b02ec`, 54 eligible.
The gate is therefore correct to refuse mixing the two cohorts. Consequences, stated plainly:

- Breadth history and rotation history start at **2026-09-04** (5 dated sessions), not August.
- The chain does **not** connect to the August captures; those remain on disk as historical
  evidence and are selectable explicitly via `VITE_SNAPSHOT_ID`.
- Rebuilding the August snapshots against the new panel would connect them, but it would rewrite
  previously validated historical bundles to accommodate a vendor data gap. That trade was
  declined; 5 real dated priors already satisfy the ≥4 requirement.

Resulting real changes in the active bundle: 10 transitions each carrying `previous_*` values and
`breadth_delta`; 3 groups with confirmed v2 states (Consumer BROADENING_FIRM, Industrial
NARROWING_FIRM, Energy + Financials STABLE); 50 breadth-history points (10 groups × 5 dates) and
50 rotation-history points (10 groups × 5 dates).

---

## 5. Research and parser ledger

Full machine-readable ledger: `research-ledger.jsonl` (this directory).

| Package | Provider | Requests | Purpose / outcome |
|---|---|---|---|
| WP-A | web search | 2 | Historical Stock Summary availability → discovered the official `GetStockSummary?date=` JSON endpoint and the IDX data catalogue |
| WP-B | web search + fetch | 2 | ds PDF URL provenance → pattern confirmed; index page returns 403 to automation |
| WP-C | idx.co.id endpoint | 3 | Attempted official **mid-chain per-stock** validation (`GetStockSummary?date=20260911`): **403 WAF** via plain client, browser headers, and headless Chrome session. Not bypassed. |
| WP-D | LlamaParse | 3 jobs, 1 doc, 2 pages | Refresh of the IDX daily-statistics context to 2026-10-02 |

**LlamaParse receipt:** source `data/raw/idx_daily_statistics/ds_261002.pdf`, pages `1-2`,
estimated 26.0 credits, **actual 20.0 credits**, tier per repo default, status `READY`,
`as_of 2026-10-02`. Two jobs failed normalization because this PDF renders the IHSG card as a
single line (`6,036.888 +27.386 (0.46%)`); a third pattern was added to the parser that accepts
**only** that exact shape (close, change, percentage adjacent on one line) — reconciliation
against the independently parsed `Previous` close and the recomputed percentage is unchanged, and
the artifact still refuses to write when values do not reconcile.

Approved accessible sources used: IDX official workbooks/PDFs (downloaded), Yahoo Finance public
chart API (existing authorized provider), IDX statistics index (web search results), and the
LlamaParse parser for one public document. Rejected/unavailable: IDX `GetStockSummary` JSON
endpoint (WAF 403), IDX statistics index page direct fetch (403).

---

## 6. Tests and browser evidence

### 6.1 Automated

| Command | Result |
|---|---|
| `.venv/bin/python -m pytest -q` | **784 passed**, 2 warnings (both pre-existing `SectorsProvider.get_full_universe_close` deprecations in `tests/test_sectors_provider.py`) |
| `.venv/bin/python -m pytest -q` in a **fresh `git clone`** | **784 passed, 0 skipped** — identical, see §11 |
| `npm run typecheck --prefix app/web` | clean |
| `npm run build --prefix app/web` | built; chunk-size advisory only (pre-existing) |
| `git diff --check` | clean |

Baseline before this work was 729 passed with the same 2 warnings; +55 tests.
New coverage in `tests/test_public_refresh_chain.py` (25 tests): export completeness, manifest
parity, disclosed WSKT gap, YTD baseline and per-feature YTD, benchmark-YTD reconciliation against
official closes, comparability (COMPATIBLE with 4 real priors, Sectors INCOMPARABLE), transitions
carrying previous values, supported/under-minimum diffusion states, breadth-history dates, rotation
history (5 dates/group, axis consistency, endpoint equality with the group row, no future or
incompatible leakage), all panel-validation invariants, plus four `bun x tsx` contracts for
`pickLatestEntry` and `buildRotationTrail` (including the <3-point refusal and axis-drop rules).

`tests/test_refresh_tool_safety.py` (17 tests) locks the three post-review tooling fixes
described in §9 plus the fixture-publication guard. It is fully self-contained: the panel and
snapshot fixtures are generated inside `tmp_path`, official comparison is isolated with an empty
`--sources-root`, and `--no-publish-fixture` keeps it away from the tracked evidence. Verified by
hiding `data/raw/public`, `data/raw/idx_composite_index`, `data/raw/idx_stock_summary` and
`data/snapshots/`: the file runs **17 passed, 0 skipped**, and the full suite is **772 passed**
in that state.

Updated contracts in `tests/test_comparability_and_adapter.py`: the index is now the curated pair
(Sectors evidence + validated latest, both with fetchable payloads and matching identity), the
harness payload stays exported-but-unindexed, and the SPA must select by newest `as_of` rather
than provider brand while keeping `VITE_SNAPSHOT_ID`.

Also fixed while refreshing: `scripts/validate_data.py` crashed on the harness directory
(`yfinance_harness` has no `security_master.json`) — it now validates the newest **loadable**
snapshot by manifest `as_of`.

### 6.1.1 Hermeticity contract

The suite is now expected to produce **the same result in every checkout**, with no skipped tests and
no dependence on local artifacts, the official IDX caches, or an installed `node_modules`. Verified
both ways:

| Environment | Result |
|---|---|
| Full working tree (panel, `data/snapshots/`, official IDX caches, `node_modules` all present) | 772 passed, 0 skipped |
| Fresh `git clone` (committed files only; no `data/raw`, no `data/snapshots`, no `node_modules`) | 772 passed, 0 skipped |

To reproduce the fresh-clone run, note that an editable install of this package makes
`project_root()` (`src/idx_leadership/utils/config.py`, file-based) resolve to the *original*
checkout, so a clone must put its own `src` first on the path:

```bash
git clone <repo> /tmp/clone-matrix
cd /tmp/clone-matrix
PYTHONPATH=/tmp/clone-matrix/src /path/to/.venv/bin/python -m pytest -q
```

Three defects made the clone result diverge from the local result; all are fixed:

- **`tests/test_snapshot_enrichment.py` skipped 5 tests** because they asserted embedded sections
  against `snap_2026-08-28.json`, a gitignored legacy export absent from a clone. They now assert
  the same sections on the **tracked active bundle** (`ACTIVE_ID = "snap_public_2026-10-02"`), which
  is the artifact that actually matters; every pre-existing assertion holds unchanged (breadth 3+3,
  60 company observations, 9 themes, 6 konglo groups, `signal_eligible: False`, research events
  `published_at` ≤ `as_of`). Update `ACTIVE_ID` on each refresh.
- **`tests/test_e2e_snapshot_export.py` wrote into the repository.** The end-to-end exporter test
  copied a snapshot into the real `data/snapshots/` and exported into the served
  `app/web/public/snapshots/`, relying on `finally` cleanup (an interrupted run left stale served
  files). It now passes `--snapshot-root` / `--out` / `--allow-outside-root`, all inside `tmp_path`,
  so no repo location is touched.
- **Two `bun x tsx` contract tests failed in a clone** with `Cannot find module 'react'`: they
  imported `pickLatestEntry` from `SnapshotProvider.tsx`, which needs `app/web/node_modules`. The
  pure selection logic now lives in `app/web/src/data/snapshotSelection.ts` (React-free) and is
  re-exported by `SnapshotProvider`, so the contract is testable without installing frontend
  dependencies. Typecheck and build are clean, and the served-index selection path was re-verified
  against `dist` (`pickLatestEntry` over the live index selects `snap_public_2026-10-02`).

**New guard — the suite may not dirty the working tree.** `tests/conftest.py` records
`git status --porcelain` at session start and compares it at session end; if the run introduced,
removed, or changed the status of any path, the run prints the offending paths and exits non-zero.
Pre-existing local modifications are tolerated (only *changes in status* count), and the guard stays
silent when git is unavailable or the run is outside a work tree. This makes the "a run rewrote
committed evidence" class of defect impossible to reintroduce silently — the failure mode behind both
P2 findings in §9. Verified to fire: a probe test that creates an untracked file makes the suite
exit 1 and name the file; a clean run exits 0.

### 6.2 Browser (headless Chrome via playwright-core, served from `app/web/dist`)

| Check | Result |
|---|---|
| Active bundle | `snap_public_2026-10-02.json` fetched; header shows "Data as of 2 Oct 2026 · Public prototype" |
| YTD copy | "Sector history covers 20D/60D/YTD excess vs IHSG, with the YTD baseline at **2025-12-30**" (data-driven; the old hardcoded "not available in this bundle" string is gone) |
| Rotation | Daily/Weekly enabled for sectors, **10 polylines drawn** (one per group); Daily has 21 sessions (up to `20 obs` tail steps), Weekly samples 5 week-ending sessions (`4 obs`), no diagnostic badge. See §11. |
| What Changed | "vs 25 Sep 2026", breadth movers `Consumer +40.0%`, `Technology −33.3%`, `Industrial −28.6%`, material shifts with `Broadening → Stable`, `Stable → Narrowing`, breadth history chart with all 5 dates |
| Network | **0 requests to api.sectors.app / any Sectors endpoint**; only local `/snapshots/*` and `/idx/*` plus api/cdn.fontshare.com font CSS/WOFF (pre-existing) |
| Console / page errors | none |
| Layout | `scrollWidth == clientWidth` at 1440×900, 1368×858, 768×1024, 390×844 (no horizontal overflow) |
| Regression | overview, map, explorer (Consumer group), what-changed, methodology all render; group/ticker navigation and tables intact |

Screenshots were written outside the repository (`/tmp/qc/`) per existing practice.

After the `pickLatestEntry` extraction (§6.1.1) the same behaviour was re-confirmed on a fresh
`dist`: typecheck and build clean, `dist/snapshots/` reduced to the tracked set, and the real
selection path exercised against the served index picks `snap_public_2026-10-02` (2 entries,
newest `as_of` wins). The four removed stale exports now resolve to the SPA shell instead of a
payload. No visual layout changed in this round — the refactor moved a pure function only.

---

## 7. Refresh runbook (reproducible)

```bash
# 0. env + official sources
#    cache the IDX workbooks/PDFs under data/raw/ (hashes → data/raw/official_sources_manifest.json)

# 1. panel fetch (public provider only; no Sectors)
.venv/bin/python -m scripts.refresh_public_panel --start 2025-12-15
python3 -m scripts.validate_public_panel          # needs openpyxl + pdfplumber (system python3)
                                                  # --sources-root / --no-publish-fixture for isolated runs

# 2. offline chain (one pass, point-in-time, hash parity enforced)
.venv/bin/python -m scripts.build_snapshot_chain --asofs 2026-09-04 2026-09-11 2026-09-18 2026-09-25 2026-10-02
# 2a. separate daily replay for rotation only (recipe in §11)
#     data/normalized/public_rotation_snapshots/ — never add daily dates to the canonical root

# 3. optional IDX context card (1 document, 2 pages)
.venv/bin/python -m scripts.refresh_idx_daily_statistics \
  --pdf-file data/raw/idx_daily_statistics/ds_261002.pdf --target-pages 1-2 \
  --allow-cloud-upload --allow-credit-spend \
  --public-output app/web/public/idx/idx_daily_statistics_latest.json

# 4. offline publication sequence
.venv/bin/python -m scripts.calculate_foreign_flow_sample
.venv/bin/python -m scripts.build_taxonomy_views --snapshot-id snap_public_2026-10-02
.venv/bin/python -m scripts.validate_data
.venv/bin/python -m scripts.export_snapshot_json --snapshot-id snap_public_2026-10-02 \
  --rotation-history-root data/normalized/public_rotation_snapshots
.venv/bin/python -m scripts.build_snapshot_index \
  --ids snap_sectors_2026-08-27 snap_public_2026-10-02

# 5. gates
.venv/bin/python -m pytest -q          # 784 passed / 0 skipped; also checks for changes in git status
npm run typecheck --prefix app/web && npm run build --prefix app/web
git diff --check
git status --porcelain                 # must be empty (the suite enforces this itself)
```

Notes for the next operator:
- `--ids` curates the index; without it the builder keeps its historical SECTORS_LIVE default.
  Under `--ids` a missing or invalid requested entry **fails the command** instead of publishing
  a partial index, so re-run `export_snapshot_json` first if a payload is missing.
- Re-running `build_snapshot_index` without `--ids` would drop the public entry — always pass it.
- If a new session lands, add it to `--asofs`; the chain enforces cohort parity and will refuse
  to continue if the eligible set changes (rebuild the whole chain, never one snapshot).
- **After re-fetching the panel**, every existing chain snapshot becomes stale by definition: the
  build will exit 2 with a panel-provenance error. That is intended — rerun with
  `--force-rebuild` to rebuild the entire chain from the new panel, then re-export and re-index.
  Never delete snapshots by hand to get past the check.
- `validate_public_panel` exits 1 on an integrity/provenance failure and writes only the
  `panel_integrity` check; official comparisons are skipped entirely in that case.
- **The tracked fixture is committed evidence of a clean run.** It is republished only when
  the report status is `PASS`; any `FAIL`/`SOURCE_UNAVAILABLE` run refuses to write it. Use
  `--no-publish-fixture` for synthetic or partial panels, and `--sources-root <dir>` to run
  the structural checks with no official comparison at all.
- It also exits 1 (never a traceback) when the official files or the `openpyxl`/`pdfplumber`
  parsers are unavailable, recording those checks as `SOURCE_UNAVAILABLE` while keeping the
  panel's own integrity verdict. Run it with an interpreter that has both parsers (the repo
  `.venv` does not; `python3` does).
- `data/raw/*`, `data/snapshots/*`, `data/normalized/*` are gitignored by design; the active
  payload is explicitly whitelisted so the SPA contract tests work on a clean checkout.
- **The test run is a gate on repo state, not just on code.** `tests/conftest.py` fails the run if
  any test left the working tree dirty, so a green suite also means "no committed file was
  rewritten and nothing was left behind". If it ever fires, the named paths are the culprit — do
  not delete the evidence to silence it; fix the test to use `tmp_path`.
- The frontend contract tests run through `bun x tsx` and need only `bun`; they deliberately no
  longer require `app/web/node_modules`. Pure logic used by those tests belongs in a React-free
  module under `app/web/src/data/` (see `snapshotSelection.ts`).
- When a refresh changes the active bundle, update `ACTIVE_ID` in
  `tests/test_public_refresh_chain.py` and `tests/test_snapshot_enrichment.py`.

---

## 8. Outcome matrix

| # | Outcome | Status | Evidence |
|---|---|---|---|
| 1 | YTD + prior-period performance from validated historical prices | **DONE** | 53/53 features with YTD from baseline 2025-12-30 (official 8646.94); 20D/60D/YTD group values published; benchmark validated on 164 workbook sessions + 11 PDF sessions |
| 2 | Real comparable prior snapshots producing diffusion changes | **DONE** | 5-date chain (2026-09-04 → 2026-10-02), hash parity enforced, `previous_snapshot_id = snap_public_2026-09-25`, 10 transitions with real previous values, breadth deltas up to ±40 pp, 4 confirmed v2 states |
| 3 | Refresh to the latest trading session (2026-10-02) | **DONE** | Latest session confirmed three ways (Stock Summary 963 rows @ 02 Oct 2026, Yahoo `^JKSE` last row 6036.888, ds_261002 PDF 6,036.888); active bundle + curated index + refreshed IDX context card |
| 4 | Accessible, permitted sources | **DONE** | Official IDX workbooks/PDFs (hashed), Yahoo public chart API (existing authorized provider), LlamaParse for 1 public document with receipt; rejected WAF-protected endpoint documented rather than bypassed |

### Known limitations carried forward

1. **WSKT.JK has no market data** (Yahoo 404; official Stock Summary lists it; Sectors registry
   does not). It stays eligible by policy and is reported as a disclosed gap
   (`failed_securities`, `missing_count=1`, coverage 98.15%). A Yahoo symbol change or IDX
   delisting notice could not be confirmed — the IDX pages that would confirm it return 403.
2. **August public snapshots are not comparable** to the new cohort (hash `a08b…` vs `5ee9…`,
   §4). Breadth/rotation history therefore begins 2026-09-04.
3. **Mid-chain per-stock official validation is unavailable** — IDX's per-date endpoint is
   WAF-blocked (403, three access modes). Per-stock prices are officially validated at
   2026-10-02 only (53/53 exact); mid-chain dates rely on the benchmark validation plus
   within-panel consistency.
4. **Groups below 5 eligible constituents** (6 of 10) remain `UNCONFIRMED` by policy — real
   numbers are shown, classifications are withheld.
5. **Daily/Weekly rotation is available for sectors only**, from the separate 21-session replay
   (§11). Stock/Konglo/Theme cadence stays unavailable because comparable daily observations
   for those views are not persisted. Sparse legacy bundles retain their dated snapshot tails.
6. **`Confirmation` on What Changed reads "Not available"** for all groups: confirmation requires
   a persistence/confirmation series that the current payload does not carry. Pre-existing,
   unchanged by this refresh.
7. **Breadth deltas render as `%` in the UI** (e.g. `+40.0%`) while the transition evidence text
   uses `pp`. Pre-existing display convention; the underlying unit is percentage points.

---

## 9. Post-handoff review fixes (four P2 tooling defects)

Independent reviews reproduced four defects in the new refresh tools. All four are fixed and
pinned by `tests/test_refresh_tool_safety.py`.

**9.1 Chain builder reused bundles regardless of the panel that produced them.**
`build_snapshot_chain` skipped any existing snapshot directory, so an edited panel left stale
values in place while the report still credited the new panel. Snapshots are now bound to their
inputs: each build writes `panel_provenance.json` (sha256 of `prices.csv` and `benchmark.csv`),
and reuse requires an exact match. A mismatch — or a bundle with no provenance record — aborts
with exit 2 and an actionable message instead of reporting success. `--force-rebuild` is the
explicit override; it deletes the previous bundle before rebuilding so no stale artifact (or the
bundle's own leftover manifest) can leak into the new one. After the fix, a clean rebuild of all
five chain dates reproduced a **byte-identical** exported payload, and a subsequent no-op run
reported `reuse verified` for all five.

**9.2 Validator accepted NaN prices and never verified panel hashes.**
`close <= 0` is False for NaN, so a corrupted baseline passed, and baseline coverage counted rows
rather than valid prices. The validator now requires finite positive prices everywhere
(`nonfinite_price_rows`, `benchmark_nonfinite_rows`, `ytd_baseline_invalid_rows`) and verifies the
panel files against the sha256 values recorded in `source_manifest.json`
(`panel_file_hashes_verified`, `panel_file_hash_mismatches`). Integrity and provenance are checked
in an **early gate** before any official comparison runs: a corrupt or unverified panel now exits
1 with a report containing only `panel_integrity`, so no downstream number can inherit the defect
while still looking validated.

**9.3 Index builder silently dropped a requested snapshot.**
With `--ids`, a requested id whose exported payload was missing (or unreadable, or failing an
identity check) was skipped and the index was still replaced — publishing a subset that omitted
the newest bundle. Every skip now records a reason, and under `--ids` any rejected requested id
fails with exit 2 **before** `index.json` is touched. The happy path is unchanged.
**9.4 A validator run could overwrite the tracked validation fixture.**
The structural panel test invoked `validate_public_panel` with the default sources root, so on a
machine that has the official IDX files and the `openpyxl`/`pdfplumber` parsers it compared
*synthetic* panel prices against *real* IDX closes and then failed on those comparisons. Because
fixture publication was unconditional, that same failing run rewrote
`tests/fixtures/public_panel_validation.json` with a synthetic failure report — committing a defect
as the expected state. Two fixes: `--sources-root` makes the official-source cache injectable (the
test passes an empty directory, whose correct verdict is `SOURCE_UNAVAILABLE`, identical whether or
not parsers exist locally), and publication is gated on a **passing** report — `_publish_fixture`
refuses any `FAIL`/`SOURCE_UNAVAILABLE` verdict, leaving an existing fixture untouched and never
creating a new one, with `--no-publish-fixture` / `--fixture-output` for explicit control. The
guard is unit-tested directly: a failing report must neither replace a published fixture nor create
one. Verified against the reviewer's exact scenario (parsers + official sources present, synthetic
panel, publication enabled): comparisons fail, the tracked fixture stays byte-identical, and the
real panel still validates `PASS`.

---

## 10. Test-suite hermeticity and hygiene (second review round)

A second review round hardened the suite itself. See §6.1.1 for the full contract and the
fresh-clone reproduction command.

- **The suite may not dirty the working tree.** `tests/conftest.py` snapshots
  `git status --porcelain` at session start and diffs it at session end; any path that appeared,
  disappeared, or changed status is reported and fails the run (exit 1). Pre-existing local edits
  are tolerated, and the guard no-ops outside a work tree. This closes the whole family of defects
  that §9.4 was an instance of.
- **The end-to-end exporter test no longer writes into the repo.** It uses
  `--snapshot-root`/`--out`/`--allow-outside-root` inside `tmp_path` instead of copying into
  `data/snapshots/` and exporting into the served directory.
- **No test depends on a gitignored artifact.** The 5 `test_snapshot_enrichment` assertions moved
  from the legacy `snap_2026-08-28.json` export to the tracked active bundle; two `bun x tsx`
  contract tests no longer need `app/web/node_modules` because `pickLatestEntry` moved to the
  React-free `app/web/src/data/snapshotSelection.ts` (re-exported by `SnapshotProvider`).
- **Served-directory hygiene.** Four stale gitignored exports were removed from
  `app/web/public/snapshots/` (`snap_2026-08-20.json`, `snap_2026-08-28.json`,
  `snap_public_2026-08-20.json`, `yf_harness_2026-08-28_raw.json`) and their stale `app/web/dist/`
  copies; a rebuild regenerates `dist/` clean. The directory now holds exactly the tracked set:
  `index.json`, `snap_public_2026-10-02.json`, `snap_sectors_2026-08-27.json`,
  `yf_harness_2026-08-28_adj.json`. Nothing referenced them (`SnapshotProvider` selects strictly
  through `index.json`), and the raw `data/snapshots/` chain evidence is untouched. They are
  recoverable from git history only if ever needed again, since they were never tracked.

**Result: 772 passed / 0 skipped in both the full working tree and a fresh clone.**

**9.5 The tree guard normalised filenames and could miss drift.**
`tree_drift` stripped the letters `R`/`C` from *paths* (they are also used in git status codes
for renames/copies). Renaming `notesR.txt` to `notes.txt` therefore produced identical keys and
the guard stayed silent. Paths are now compared verbatim alongside the exact two-letter status;
`_STATUS_LETTER` is gone. Covered by `test_tree_drift_preserves_exact_filenames`.

**9.6 An external `--sources-root` crashed the validator.**
When the cache directory lived outside the repository, a qualifying Sectors registry report hit
`report_path.relative_to(PROJECT_ROOT)` and raised ValueError — no report was written. The
source is now rendered with the existing `_display_path` helper (absolute outside the repo).
Covered by `test_validator_handles_populated_external_sources_root`, which fakes the parser gate
and the xlsx/pdf loaders in-process so it runs identically on a fresh checkout.

## 11. Real Daily/Weekly rotation (Codex continuation)

The validated public panel contains **21 benchmark sessions, 2026-09-04 → 2026-10-02**, with
the same 53 observed tickers on every day. Replayed offline through the existing snapshot
pipeline into **`data/normalized/public_rotation_snapshots/`**, these produce **210 real sector
observations**. No provider/network/parser request or additional credit spend was needed.

The daily root is separate from `data/snapshots/`. Its daily prior comparisons are not promoted
into the active market snapshot: `previous_snapshot_id` remains `snap_public_2026-09-25`, and
the published transitions, breadth deltas, classifications and canonical five-date history
are unchanged. Comparing the enriched payload against the prior active export showed **zero
changed existing fields**; only `rotation_daily_history` was added.

`export_snapshot_json --rotation-history-root` requires COMPLETE bundles, exact contract and
eligible-cohort parity, matching `prices.csv`/`benchmark.csv` hashes, every benchmark session
inside the replay window, finite group return axes, and endpoint equality with current group
rows. A missing day/group, stale panel, incomparable cohort or divergent endpoint refuses
export before replacing an existing output. Future snapshots cannot enter the history.
The served metadata records sessions, source snapshot ids and panel hashes.

Daily sampling uses every actual trading session; Weekly uses the last actual session in each
Monday–Sunday week, including a partial current week. Sampling never changes the axes:
**X = YTD excess vs IHSG; Y = 20D excess − 60D excess**. Both need at least three real points.
The interval is persisted in `?interval=daily|weekly`; the tail can show all 21 daily points or
all five weekly points. Unsupported selections keep explicit disabled controls.

To reproduce the separate daily replay from the current persisted panel:

```bash
.venv/bin/python - <<'PY'
import sys
from pathlib import Path
import pandas as pd
from scripts.build_snapshot_chain import main

panel = Path('data/raw/public/panel_2025-12-15_2026-10-04')
sessions = [d for d in sorted(pd.read_csv(panel / 'benchmark.csv').date)
            if '2026-09-04' <= d <= '2026-10-02']
sys.argv = ['build_snapshot_chain', '--panel-dir', str(panel), '--asofs', *sessions,
            '--snapshots-root', 'data/normalized/public_rotation_snapshots',
            '--report', 'data/normalized/public_rotation_chain_report.json']
# After a panel refresh, append --force-rebuild and rebuild the canonical chain too.
raise SystemExit(main())
PY
.venv/bin/python -m scripts.export_snapshot_json \
  --snapshot-id snap_public_2026-10-02 \
  --rotation-history-root data/normalized/public_rotation_snapshots
```

`tests/test_rotation_cadence.py` adds 12 hermetic regressions: generated replay/export fixtures,
failure without output replacement, future exclusion, actual week-end/partial-week sampling,
sparse/duplicate/invalid-axis refusal, and the tracked active daily/weekly contract. Tests never
read the ignored replay or panel. The full suite now has **784 tests**.

Browser verification of the production build: Daily draws 10 sector polylines with 21 points
each; Weekly draws the same 10 with five points each. Interval switching updates the URL;
Stock and Theme views disable cadence and draw no invented trails. No horizontal overflow
at 1440×1000, 1368×858, 768×1024 or 390×844; no console/page errors. Long daily date captions
show the range rather than listing all 21 dates. Typecheck/build pass with the existing Vite
config and chunk-size advisories. Fresh-clone tests run without raw data, replay bundles or
frontend node_modules and leave the clone clean.
