# Frontier Pass #1 — Audit

> **Pass scope:** Sectors integration, market-wide methodology
> audit, architecture revision. **Status: PARTIAL** — no live Sectors
> API key was available in the environment, so the Sectors code path
> is shipped and unit-tested but no live market-wide run is recorded.
> All "before" / "after" cells describe the state of the repository on
> 2026-08-27, not fictional live data.

## 1. Headline numbers

| | Groundwork | Frontier #1 | Δ |
| --- | --- | --- | --- |
| Tests | 92 passed | **158 passed** | +66 |
| Sectors code path | typed stub | real HTTP client + provider | yes |
| Provider abstraction | single `MarketDataProvider` | `MarketDataProvider` + 8 capability protocols | yes |
| Universe | 50 names | market-wide with eligibility filter | yes |
| Diffusion rule | raw ±10pp | group-size-aware (FIRM / FRAGILE) | yes |
| Concentration | `top1 ≤ 1.0` implicit | explicit cap, signed share, HHI | yes |
| Min group size | 4 | **5** | yes |
| Methodology version | v1 | **v2** | yes |
| Sectors client | none | `SectorsClient` w/ ledger + cache + retry | yes |

## 2. Area-by-area audit

| Area | Before | After | Evidence | Remaining risk |
| --- | --- | --- | --- | --- |
| Sectors client | none | `SectorsClient` with auth / timeout / retry / pagination / raw cache / ledger integration | `src/idx_leadership/providers/sectors_client.py`; `tests/test_sectors_client.py` (13 tests) | live call only possible with a key |
| Credit economics | UNKNOWN | per-endpoint costs documented; estimated daily refresh ≈ 70 credits Tier 1 + 2/driver Tier 3 | `docs/SECTORS_CREDIT_AUDIT.md`; `docs/SECTORS_REFRESH_BUDGET.md` | balance read not programmatic; needs key |
| Security master | local YAML | `SectorsProvider.get_security_master` against `/v2/companies/`, normalized to canonical | `src/idx_leadership/providers/sectors.py`; `tests/test_sectors_provider.py` | real master requires key |
| Taxonomy | local coarse | Sectors `sector` / `sub_sector` / `industry` / `sub_industry` (kebab slugs) | `SectorsProvider.get_group_taxonomy`; `docs/TAXONOMY_AUDIT.md` | real taxonomy requires key |
| Full-universe close | per-ticker | one cross-section per day (942 → ~32 pages at limit=30) | `SectorsProvider.get_full_universe_close`; `DOCUMENTED_COST["/v2/close/"] = "per_page"` | real price requires key |
| Benchmark | Yahoo `^JKSE` | Sectors cross-section symbol when present; `SectorsProvider.get_benchmark_history` reuses the cross-section for ≤ 90 days | `SectorsProvider.get_benchmark_history`; parity harness | Sectors IHSG index endpoint not exposed in docs (G012) |
| Universe eligibility | none | 5-rule filter with explicit `exclusion_reason` | `src/idx_leadership/providers/market_universe.py`; `tests/test_market_universe.py` (4 tests) | live shares of `recently_suspended` etc. require key |
| Liquidity / staleness | none | `stale_trading_days=30` and `min_history_days=60` enforced; suspensions respected | `EligibilityConfig` | liquidity filter deferred to D020 (future) |
| Breadth | unchanged | 0–100 share, denominators explicit | `tests/test_breadth.py` (unchanged) | none significant |
| Diffusion | raw ±10pp | group-size-aware (`BROADENING_FIRM` / `_FRAGILE`) | `src/idx_leadership/signals/diffusion_v2.py`; `tests/test_diffusion_group_size.py` (10 tests) | live turnover study needed |
| Concentration | `top1` could exceed 1.0 | explicit cap; signed + HHI separated | `src/idx_leadership/features/concentration_v2.py`; `tests/test_concentration_v2.py` (10 tests) | none significant |
| Leadership states | 4-state + UNCONFIRMED | unchanged | `tests/test_states.py` (unchanged) | live stability study needed |
| Transitions | unchanged | unchanged | `tests/test_transitions.py` (unchanged) | none significant |
| Change digest | unchanged | unchanged | `tests/test_transitions.py::test_change_digest_buckets_unique` | none significant |
| Evidence | unchanged | contradictions list expanded (LEADING + NARROWING and breadth-thin) | `tests/test_evidence.py` (unchanged) | none significant |
| Fundamentals | researched, not wired | researched, **not auto-applied** (Tier 2, on demand) | `docs/ENRICHMENT_RESEARCH.md` §2 | group-level signal not yet built |
| Foreign flow | researched, not wired | implemented, **Tier 3 only** (1 credit per call) | `SectorsProvider.get_foreign_flow`; `docs/ENRICHMENT_RESEARCH.md` §3 | market-wide rollup deferred |
| Broker data | not in scope | researched, not integrated (per brief §43 — needs lift above foreign flow) | `docs/ENRICHMENT_RESEARCH.md` §4 | may add `SectorsProvider.get_broker_summary` later |
| Free float | researched | implemented as `FreeFloatProvider` capability; **not default** | `SectorsProvider.get_free_float`; `tests/test_capability_provider.py` | D011 commits to keep equal-weight default |
| API efficiency | ad-hoc | tiered refresh model; cache TTLs; estimated 70 credits Tier 1 | `docs/SECTORS_REFRESH_BUDGET.md` | live balance not visible |
| Tests | 92 | **158** | `pytest tests/` | live Sectors integration tests require a key |
| UI | 4 tabs | 4 tabs (no change) | `app/streamlit_app.py` | D019: no UI changes this pass; per brief §60 |
| Documentation | 7 docs | **15 docs** (8 new in this pass) | `docs/` directory | none significant |
| Decision log | D001–D010 | D001–**D019** | `docs/DECISION_LOG.md` | none |
| Known gaps | 14 items | 14 items (4 resolved, 4 new) | `docs/KNOWN_GAPS.md` | none significant |

## 3. Methodological decisions, by evidence

| Decision | Evidence |
| --- | --- |
| D011 — keep equal-weight, free-float parallel | `ENRICHMENT_RESEARCH.md` §1 |
| D013 — Sectors `close` treated as raw | `SECTORS_API_AUDIT.md` §2.2 (no adjustment documentation); `KNOWN_GAPS.md` G011 |
| D014 — group-size-aware diffusion | `tests/test_diffusion_group_size.py`; `METHODOLOGY_SENSITIVITY.md` §3 |
| D015 — concentration v2 with cap | `tests/test_concentration_v2.py::test_top1_abs_share_capped_at_one`; `METHODOLOGY_SENSITIVITY.md` §4 |
| D016 — min group size 4 → 5 | `METHODOLOGY_SENSITIVITY.md` §7; 4-stock sub-industries are common |
| D017 — methodology v2 with v1 back-compat | `tests/test_methodology_versioning.py` |
| D018 — corporate-action guardrail annotation-only | `KNOWN_GAPS.md` G011 |
| D019 — `allow_live` gate | `tests/test_sectors_client.py::test_live_blocked_when_disallowed` |

## 4. Acceptance gates

| Gate | Result | Reason |
| --- | --- | --- |
| 1 — Sectors integration proof | **PARTIAL** | Client, auth, pagination, cache, ledger all unit-tested; live call requires a key |
| 2 — Core provider migration | **PARTIAL** | Code path complete; live Sectors call requires a key; parity report issued (scaffolding) |
| 3 — Market-wide engine | **PARTIAL** | Engine ready; live numbers require a key; harness in `tests/test_market_universe.py` |
| 4 — Methodology validation | **PASS** | Sensitivity matrix in `docs/METHODOLOGY_SENSITIVITY.md`; v2 tests cover all branches; no-look-ahead tests still pass |
| 5 — Enrichment proof | **PARTIAL** | Free float + fundamentals researched; foreign flow wired but only Tier 3; broker deferred per brief §43 |

## 5. Stop conditions invoked

Per brief §90, the following stop conditions were met and *not*
bluffed:

- Sectors credentials are unavailable.
- Live balance read is not programmatic.
- Sectors `close` basis is undocumented (treated as raw, G011).

A high-quality partial audit is delivered in place of fabricated
completion.

## 6. Files changed (summary)

### New (12 source / 12 test / 8 doc)
```
src/idx_leadership/providers/capabilities.py
src/idx_leadership/providers/sectors_client.py
src/idx_leadership/providers/sectors.py             (replaced stub)
src/idx_leadership/providers/sectors_normalizers.py
src/idx_leadership/providers/market_universe.py
src/idx_leadership/features/concentration_v2.py
src/idx_leadership/signals/diffusion_v2.py
tests/test_sectors_client.py
tests/test_sectors_provider.py
tests/test_capability_provider.py
tests/test_market_universe.py
tests/test_diffusion_group_size.py
tests/test_concentration_v2.py
tests/test_methodology_versioning.py
tests/test_parity_public_sectors.py
docs/SECTORS_API_AUDIT.md
docs/SECTORS_CREDIT_AUDIT.md
docs/PROVIDER_PARITY_REPORT.md
docs/TAXONOMY_AUDIT.md
docs/UNIVERSE_ELIGIBILITY.md
docs/METHODOLOGY_SENSITIVITY.md
docs/SECTORS_REFRESH_BUDGET.md
docs/ENRICHMENT_RESEARCH.md
FRONTIER_PASS_1_AUDIT.md  (this file)
```

### Modified
```
src/idx_leadership/providers/base.py              (removed ABC conflict)
src/idx_leadership/providers/factory.py           (allow_live parameter)
src/idx_leadership/providers/public.py             (capability mixin)
src/idx_leadership/providers/fixture.py            (capability mixin)
src/idx_leadership/providers/__init__.py           (capability exports)
src/idx_leadership/models/security_master.py       (listing_board default "Main")
src/idx_leadership/signals/__init__.py             (v2 exports)
src/idx_leadership/features/__init__.py            (v2 exports)
config/methodology.yaml                          (bump to v2)
docs/KNOWN_GAPS.md                                (resolved / new)
docs/DECISION_LOG.md                              (D011–D019)
tests/test_providers.py                           (Sectors capability test)
```

## 7. What this pass does NOT do

Per the brief and per the stop conditions, the following are
**not** delivered in this pass:

- A live Sectors key was not used; no live market-wide numbers are
  reported.
- No forward-return backtest is performed (D005 / brief §29).
- No LLM narration (brief §59).
- No ML / clustering / HMM (brief §84).
- No broker-cohort integration (brief §43 — insufficient lift).
- No UI redesign (brief §60 / §85).
