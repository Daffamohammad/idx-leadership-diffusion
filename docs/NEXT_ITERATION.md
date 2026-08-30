# Next Iteration

> Updated during the **Frontier Pass #2 live integration** (2026-08-28).
> The first credentialed Sectors snapshot and live parity spot-check are
> complete. This file now tracks the remaining hardening work; the live
> bundle is `READY_WITH_GAPS`, not a demo fallback.

## P0 — Live Sectors validation (core evidence complete; follow-ups remain)

### P0.1 — Live Sectors auth + minimal validation (complete with one bounded gap)

- **Trigger:** `SECTORS_API_KEY` available in the process environment.
- **Required inputs:** key only; no other state needed.
- **Command:**

  ```bash
  .venv/bin/python -m scripts.validate_sectors_live \
    --live --allow-credit-spend --as-of YYYY-MM-DD
  ```

- **Expected outputs:** `data/raw/sectors_validation/<run>/validation_report.json`,
  sanitized fixtures under `sanitized_fixtures/`, request ledger.
- **Observed:** auth, taxonomy, and market-close contracts passed. The
  one-page benchmark probe returned `NOT_FOUND_IN_FETCHED_PAGES`; the
  market-wide runner separately used `/v2/index-daily/ihsg/` successfully.
- **Risk:** low; client is unit-tested offline.

### P0.2 — Price-basis audit (BBCA split 2021-10-13)

- **Trigger:** P0.1 PASS.
- **Required inputs:** key, the BBCA split window.
- **Command:**

  ```bash
  python -m scripts.audit_price_basis \
    --ticker BBCA.JK --start 2021-10-01 --end 2021-10-29 \
    --corporate-action-date 2021-10-13 \
    --sectors-mode SECTORS_LIVE --live --allow-credit-spend \
    --as-of 2021-10-29
  ```

- **Expected outputs:** `data/normalized/price_basis_BBCA_JK/series.csv`,
  `return_discontinuities.csv`, `report.json`.
- **Success criteria:** `sectors_live_status` is one of
  `CONFIRMED_RAW_CLOSE` / `CONFIRMED_ADJUSTED_CLOSE`; otherwise
  decision is escalated to D013 follow-up.
- **Risk:** may still be UNKNOWN; the runbook's rollback applies.

### P0.3 — Live market-wide snapshot (complete; `READY_WITH_GAPS`)

- **Trigger:** P0.1 PASS; benchmark source resolved.
- **Required inputs:** key, as-of date.
- **Command:**

  ```bash
  .venv/bin/python -m scripts.build_market_snapshot --as-of YYYY-MM-DD --allow-live --allow-credit-spend
  ```

- **Expected outputs:** `data/snapshots/sectors/sectors_<asof>/`,
  `manifest.json` with `provider_mode=SECTORS_LIVE` and all version
  fields.
- **Observed:** snapshot readable, 99.2% usable requested-history coverage
  for the 500-row used sample (265 policy-eligible), native Sectors IHSG
  through 2026-08-27, and explicit prefix-sample disclosure.

### P0.4 — Live credit audit

- **Trigger:** P0.3; before/after account balances are observed.
- **Command:**

  ```bash
  python -m scripts.audit_sectors_credit \
    --ledger data/raw/sectors_validation/<run>/request_ledger.jsonl \
    --request-category ALL \
    --before-balance <int> --after-balance <int>
  ```

- **Expected outputs:** `data/normalized/sectors_credit_audit.json`
  with `observed_delta` filled in.
- **Success criteria:** every entry has `estimated_credit_cost`; the
  observed delta is appended to `SECTORS_CREDIT_AUDIT.md`.

### P0.5 — Live parity run (complete for the bounded spot-check)

- **Trigger:** P0.3; both public and Sectors sources have true history.
- **Command:**

  ```bash
  .venv/bin/python -m scripts.compare_providers --sectors-mode SECTORS_LIVE \
    --live --allow-credit-spend --as-of YYYY-MM-DD
  ```

- **Expected outputs:** `data/normalized/parity_<asof>.csv`; appended
  to `PROVIDER_PARITY_REPORT.md`.
- **Success criteria:** `delta_pct < 0.5` for ≥ 80% of overlap rows;
  any `UNEXPLAINED` row is investigated.

## P1 — Live methodology hardening (depends on P0)

### P1.1 — Live state-turnover study

- **Trigger:** P0.3.
- **Command:** `python -m scripts.run_state_turnover --snapshots-dir data/snapshots/sectors`.
- **Success criteria:** `mean_change_rate < 2 transitions per group per
  month` over a 60-business-day window.

### P1.2 — Live horizon sensitivity

- **Trigger:** P0.3.
- **Command:** `python -m scripts.run_horizon_sensitivity --as-of YYYY-MM-DD`.
- **Success criteria:** 5/20/60 dominates or ties on the four metrics
  (state agreement, rank stability, churn, coverage).

### P1.3 — Live diffusion sensitivity

- **Trigger:** P0.3.
- **Command:** re-run the four constrained variants
  (`scripts/audit_group_size_diffusion.py` and `scripts/run_diffusion_sensitivity.py`).
- **Success criteria:** v1↔v2 agreement > 0.6 overall; the
  v2 floor visibly tightens small-group transitions.

### P1.4 — Live stale-trading study

- **Trigger:** P0.3.
- **Command:** `python -m scripts.run_stale_trading`.
- **Success criteria:** `is_stale` share < 15% on the full IDX.

## P2 — Optional enhancement (live or offline)

### P2.1 — Live-mode opt-in test marker

- Add `pytest -m live_sectors` that runs a single live probe per
  endpoint and asserts a 200 response. Default `pytest` stays
  offline.
- **Trigger:** P0.1.
- **Success criteria:** default `pytest` is offline; live tests are
  explicitly opt-in.

### P2.2 — Industry-level drilldown

- Add an "industry" view in the Streamlit UI behind a config flag.
- **Trigger:** P0.3; sufficient live universe size.
- **Success criteria:** industry view is opt-in; the default sector
  view is unchanged.

### P2.3 — Forward-return descriptive diagnostic

- The brief §52–54 allow a non-optimizing forward-return table.
- **Trigger:** methodology v3 has been live-validated.
- **Success criteria:** descriptive only; no parameter mining.

## Done in this pass (Offline Refinement, 2026-08-28)

- 287 tests passing (was 202; +85 from synthetic + group-size +
  no-look-ahead + breadth edge cases; 2 pre-existing failures fixed).
- 7 synthetic scenarios (A–G) with golden regression tests in
  `tests/test_synthetic_scenarios.py`.
- `scripts/audit_group_size_diffusion.py` (offline diffusion guardrail
  for group sizes 3, 4, 5, 7, 10, 20, 40) plus 4 tests.
- No-look-ahead regression on synthetic history for persistence,
  materiality, and the intelligence contract
  (`tests/test_no_lookahead_synthetic.py`).
- `scripts/audit_price_basis.py --as-of` flag aligned with the
  runbook; report now records the requested as-of date.
- `OFFLINE_REFINEMENT_AUDIT.md` and `docs/CHANGE_SUMMARY.md` shipped.
- D034, D035, D036 added to the decision log.

## Top 10 next-pass improvements (ranked)

1. **P0.1** — Live auth + minimal validation. *Unblocks every live gate.*
2. **P0.2** — Price-basis audit. *Authoritative return math.*
3. **P0.3** — Live market-wide snapshot. *Real product coverage.*
4. **P0.5** — Live parity run. *Cross-source agreement.*
5. **P0.4** — Live credit audit. *Operational discipline.*
6. **P1.1** — Live state-turnover study. *Calibration evidence.*
7. **P1.4** — Live stale-trading study. *Breadth-divergence evidence.*
8. **P1.2** — Live horizon sensitivity. *Stability across variants.*
9. **P1.3** — Live diffusion sensitivity. *v1→v2 agreement + floor.*
10. **P2.1** — Live-mode opt-in test marker. *Test isolation preserved.*
