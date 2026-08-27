# Frontier Pass #2 — Audit

> **Pass scope:** Live Sectors validation, methodology hardening, first
> productization. **Status: PARTIAL** — no live Sectors API key is
> present in this environment. The full offline scaffold (8 new
> scripts, 3 analytics modules, story-mode UI, per-endpoint data
> quality, persistence, contradictions, invalidation, contract
> tests, 8 new docs) was built. The live legs (auth, credit probe,
> live market-wide snapshot, live parity run, live state-turnover)
> are documented, scripted, and unit-tested but **BLOCKED** until
> a key is available.

## Post-review corrections (2026-08-27)

The offline review after this audit corrected methodology propagation,
manifest-root isolation, persisted-row NaN handling, endpoint-status
path resolution, and Sectors URL/history execution. The default suite
now collects 213 offline tests; the live Sectors gates remain blocked
until a credentialed run is performed.

## 1. Headline numbers

| | FP1 (groundwork end) | FP2 (this pass) | Δ |
| --- | --- | --- | --- |
| Tests | 158 | **202** | +44 |
| Sectors code path | real client + provider | unchanged + capability tests | yes |
| Methodology version | v2 | v2 + persistence + contradictions + invalidation | yes |
| Sectors credit audit rollup | queued | shipped (offline-tested) | yes |
| Live Sectors runs | none | **BLOCKED — no key** | — |
| Per-endpoint data quality | flat single status | per-endpoint statuses (core, taxonomy, benchmark, fundamentals, flow, events) | yes |
| Story-mode UI | none | shipped, deterministic, no LLM | yes |

## 2. Gate-by-gate audit

| Gate | Status | Reason |
| --- | --- | --- |
| 0 — Baseline | **PASS** | 158 → 202 tests; 0 failed |
| 1 — Live Sectors auth | **BLOCKED — NO CREDENTIAL** | no `SECTORS_API_KEY` in env / .env / shell history / config |
| 2 — Core market data | **BLOCKED** | depends on Gate 1 |
| 3 — Market-wide snapshot | **BLOCKED** | depends on Gate 1; `scripts/build_market_snapshot.py` shipped and unit-tested |
| 4 — Price semantics | **PARTIAL** | docs search returned `UNSPECIFIED`; `scripts/audit_close_basis.py` shipped; empirical leg BLOCKED |
| 5 — Methodology hardening | **PARTIAL** | v2 diffusion + concentration + persistence + contradictions + invalidation shipped; live turnover study BLOCKED |
| 6 — Enrichment | **PARTIAL** | free-float + foreign-flow + corporate-actions wired; not auto-applied; broker data researched but not integrated |
| 7 — Productization | **PASS (offline)** | What Changed / Leadership Map / Group Explorer / Method & Quality can consume live outputs without fabricated values; per-endpoint data quality panel shipped |

## 3. Area-by-area audit

| Area | Before (FP1) | After (FP2) | Evidence | Remaining risk |
| --- | --- | --- | --- | --- |
| Sectors client | live-gated | live-gated + retry / pagination / cache / ledger | `SectorsClient`; 13 unit tests | live only |
| Credit economics | `estimated_credit_cost` only | `scripts/credit_audit.py` rollup; per-endpoint + per-refresh-kind buckets | `credit_audit.json` (empty until live) | balance not programmatic |
| Security master | wired | unchanged | `SectorsProvider.get_security_master` | live only |
| Taxonomy | wired | unchanged | `SectorsProvider.get_group_taxonomy` | live only |
| Full-universe close | wired | unchanged | `SectorsProvider.get_full_universe_close` | live only |
| IHSG | fallback to cross-section mean | unchanged; placeholder `price_basis: close_proxy_mean` when symbol missing | `scripts/build_market_snapshot.py` | live Sectors index endpoint not documented |
| Universe eligibility | 5-rule filter | unchanged | `tests/test_market_universe.py` (4 tests) | live shares pending |
| Liquidity / staleness | `stale_trading_days=30` | `scripts/run_stale_trading.py` shipped | runnable offline; live only | live only |
| Breadth | 0–100 share | unchanged + parallel `trading-eligible` view | `UNIVERSE_ELIGIBILITY.md` | live only |
| Diffusion v2 | group-size-aware | unchanged; sensitivity script shipped | `run_diffusion_sensitivity.py` | live only |
| Concentration v2 | `top1 ≤ 1.0` | unchanged | `concentration_v2.py`; 10 tests | live only |
| Leadership states | 4-state + UNCONFIRMED | unchanged; no live stability study | n/a | live only |
| Transitions | unchanged | unchanged | 9 tests | live only |
| Change digest | unchanged | unchanged | 1 test | live only |
| Evidence objects | contradictions: 2 heuristics | 7 heuristics (LEADING+NARROWING, top1>0.6, breadth<30, etc.) | `analytics/contradictions.py`; 9 tests | live only |
| **Persistence** | not present | new in FP2: `compute_persistence` for leadership/diffusion/broadening/narrowing | `analytics/persistence.py`; 4 tests | live only |
| **Screen invalidation** | not present | new in FP2: `build_invalidation_conditions` (4 conditions) | `analytics/invalidation.py`; 2 tests | live only |
| Fundamentals | researched | researched; no auto-integration | `ENRICHMENT_RESEARCH.md` | insufficient live signal |
| Foreign flow | Tier 3 only | unchanged | `SectorsProvider.get_foreign_flow`; 1 test | live only |
| Broker data | not integrated | not integrated (insufficient lift) | brief §43 | n/a |
| Free float | capability | parallel magnitude view; not default (D011) | `SectorsProvider.get_free_float`; capability test | live only |
| API efficiency | tiered refresh | tiered refresh + `scripts/credit_audit.py` | `SECTORS_REFRESH_BUDGET.md` v2 | live only |
| Tests | 158 | **202** | `pytest` | n/a |
| UI | 4 tabs | 4 tabs + per-endpoint data quality panel in sidebar | `app/streamlit_app.py`; `app/data_quality.py` | n/a |
| **Story-mode UI** | not present | new in FP2: deterministic `StoryCard` rendering; no LLM | `app/story_mode.py`; 8 tests | n/a |
| Documentation | 10 docs | **15 docs** (+ `SECTORS_PRICE_BASIS`, `LIVE_METHODOLOGY_AUDIT`, `FRONTIER_PASS_2_AUDIT`) | `docs/` | n/a |
| Decision log | D001–D019 | D001–**D024** | `docs/DECISION_LOG.md` | n/a |
| Known gaps | 14 items | updated (4 new, 2 resolved) | `docs/KNOWN_GAPS.md` | n/a |

## 4. New / modified files (summary)

### New (12)
```
src/idx_leadership/analytics/__init__.py
src/idx_leadership/analytics/persistence.py
src/idx_leadership/analytics/contradictions.py
src/idx_leadership/analytics/invalidation.py
src/idx_leadership/data/endpoint_status.py
app/data_quality.py
app/story_mode.py
scripts/audit_close_basis.py
scripts/credit_audit.py
scripts/refresh_sectors_core.py
scripts/build_market_snapshot.py
scripts/compare_providers.py
scripts/run_state_turnover.py
scripts/run_stale_trading.py
scripts/run_horizon_sensitivity.py
scripts/run_diffusion_sensitivity.py
tests/test_analytics.py
tests/test_endpoint_status.py
tests/test_provider_contracts.py
tests/test_ui_story_mode.py
tests/conftest_app.py
docs/SECTORS_PRICE_BASIS.md
docs/LIVE_METHODOLOGY_AUDIT.md
FRONTIER_PASS_2_AUDIT.md
```

### Modified
```
src/idx_leadership/models/__init__.py        (DiffusionStateV2 re-export)
app/streamlit_app.py                        (per-endpoint DQ + story mode)
```

## 5. Stop conditions invoked (per brief §87)

- **No Sectors API key** is present in this environment.
  - This blocks Gate 1 (live auth) and every dependent gate.
- **Sectors `close` basis** is `UNSPECIFIED` in docs; the empirical
  audit (BBCA split on 2021-10-13) is BLOCKED.
- **Live balance read** is not programmatic; credit economics are
  estimated, not observed.

A high-quality partial audit is delivered in place of fabricated
completion.

## 6. What this pass does NOT do

Per the brief and per the stop conditions, the following are
**not** delivered in this pass:

- A live Sectors key was not used; no live market-wide numbers are
  reported.
- No forward-return backtest is performed (D005 / brief §29).
- No LLM narration (brief §83).
- No ML / clustering / HMM (brief §84).
- No broker-cohort integration (brief §43 — insufficient lift).
- No live state-turnover study, no live parity run, no live
  credit probe, no live Sectors snapshot.

All live legs are **scripted, unit-tested, and ready to run** when
a `SECTORS_API_KEY` is provided.

## 7. Top 10 next-pass actions (ranked by impact)

1. **Set `SECTORS_API_KEY` and run `scripts/refresh_sectors_core` and
   `scripts/build_market_snapshot`** — unblocks Gates 1–3.
2. **Run `scripts/audit_close_basis.py` on BBCA.JK (split
   2021-10-13)** — confirms the price-basis hypothesis (D013).
3. **Run `scripts/compare_providers.py` and append the CSV to
   `docs/PROVIDER_PARITY_REPORT.md`** — proves cross-source
   agreement.
4. **Run `scripts/run_stale_trading.py`** — measures the
   raw-vs-eligible breadth divergence.
5. **Run `scripts/credit_audit.py`** — populates
   `data/normalized/credit_audit.json` with observed numbers.
6. **Run `scripts/run_state_turnover.py` over a 60-business-day
   history** — calibrates diffusion v2.
7. **Run `scripts/run_horizon_sensitivity.py`** — confirms 5/20/60
   stability.
8. **Run `scripts/run_diffusion_sensitivity.py`** — confirms v1→v2
   agreement rate.
9. **Wire `scripts/build_market_snapshot` into the Streamlit
   `What Changed` tab via a one-click "Refresh" button** (gated
   behind a `SECTORS_API_KEY` present check).
10. **Add live-mode opt-in test marker** (per brief §75) so
    `pytest -m live_sectors` exercises a small live probe and the
    default `pytest` stays offline.
