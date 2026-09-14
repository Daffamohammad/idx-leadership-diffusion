# Sectors Migration Contract

> Provider-agnostic analytics must not be rewritten during migration.
> This contract specifies the canonical fields the future Sectors implementation must populate,
> the current yfinance groundwork mapping, and the Sectors endpoint/field that will replace it.
> `VERIFY WITH SECTORS` marks semantics that must be observed live before promotion.

## 1. Execution Mode for This Pass

| Role | Provider | Live calls |
| --- | --- | --- |
| Primary price / benchmark groundwork | `yfinance` via `YFinanceProvider` → canonical | YES (public data, no credits) |
| Research / discovery | Tavily + YOU.com | Bounded, qualitative only |
| Future production provider | `SectorsProvider` (live-gated) | NO — intentionally deferred |

All yfinance observations pass through `src/idx_leadership/providers/public.py` → canonical schemas in `src/idx_leadership/models/schemas.py`. Analytics (`src/idx_leadership/features/*`, `aggregation/*`, `signals/*`) never import yfinance.

## 2. Canonical Schemas (Source of Truth)

Defined in `src/idx_leadership/models/schemas.py` and exercised by `src/idx_leadership/providers/sectors_normalizers.py` (fixture-tested in `tests/test_provider_contracts.py`).

| Canonical entity | Required fields | Price basis field | Provenance fields |
| --- | --- | --- | --- |
| `SecurityMasterEntry` | `ticker` (canonical, e.g. `BBCA`), `vendor_ticker` (`BBCA.JK`), `exchange`, `sector`, `subsector`, `industry`, `subindustry`, `listing_status`, `active` | — | `source`, `source_as_of`, `taxonomy_version` |
| `PriceObservation` | `ticker`, `date`, `close`, `adjusted_close`, `volume`, `market_cap`, `currency` | `price_basis` (`adjusted_close` or `close`) | `source` |
| `BenchmarkObservation` | `benchmark_id`, `date`, `close` (index level) | `price_basis` | `source` |
| `GroupMetric` / `GroupSnapshot` | `group_id`, `20D excess`, `60D excess`, `breadth_outperforming`, `breadth_delta`, `top1/3/5`, `leadership_state`, `diffusion_state_v2` | — | `method_version`, `provider_mode` |

Only Sectors-verified taxonomy may set `taxonomy_version = sectors-v2`. The prototype `config/universe.yaml` taxonomy remains `prototype-v1` and is explicitly labelled `PROTOTYPE_CONFIG`.

## 3. Provider Abstraction Readiness

```
YFinanceProvider  ─┐
                   ├─→ canonical DataFrames → eligibility → features → aggregation → signals → snapshots → UI
SectorsProvider   ─┘                (same analytics, same schemas, same snapshot writer)
FixtureProvider   ─┘
```

* `src/idx_leadership/providers/base.py` — `MarketDataProvider` interface
* `src/idx_leadership/providers/capabilities.py` — `SecurityMasterProvider`, `PriceHistoryProvider`, `TaxonomyProvider`, `BenchmarkProvider`, `FreeFloatProvider`, `FlowProvider`, `EventProvider`
* `src/idx_leadership/providers/factory.py` — `build_provider_from_config` with `ProviderMode` enum (`PUBLIC_PROTOTYPE`, `SECTORS_LIVE`, `SECTORS_FIXTURE`, `DEMO_FIXTURE`)
* `src/idx_leadership/providers/sectors_client.py` — live-gated `SectorsClient` (auth, pagination `limit=200` screener / `limit=30` close, retry, ledger, `max_estimated_credits` gate)
* `src/idx_leadership/providers/sectors_normalizers.py` — normalizers for `companies`, `daily`, `index-daily`, `close`, `free-float`, `foreign-flow`

No analytical code imports `yfinance` or `requests` directly; only `providers/public.py` and `providers/sectors_client.py` do.

## 4. Field-Level Parity Checklist

### 4.1 Security Master

| Current (yfinance groundwork) | Canonical field | Future Sectors field / endpoint | Validation required |
| --- | --- | --- | --- |
| `config/universe.yaml` `ticker` (`BBCA.JK`) + `sectors`/`sub_sectors` | `SecurityMasterEntry.ticker` (`BBCA`), `vendor_ticker` (`BBCA.JK`), `sector`, `subsector`, `industry`, `subindustry` | `GET /v2/companies/` `symbol`, `company_name`, `sector`, `sub_sector`, `industry`, `sub_industry`, `listing_board`, `listing_status`, `market_cap` · `sectors_normalizers.normalize_companies` | Verify taxonomy null rates, board values, instrument classification, duplicate tickers, pagination completeness; see `SECTORS_API_AUDIT.md` §2.1 |
| `config/universe.yaml` `benchmark: ^JKSE` | `BenchmarkObservation.benchmark_id` | `GET /v2/index-daily/ihsg/` `index_code`, `date`, `price` | Verify native IHSG series vs Yahoo `^JKSE` parity; see §2.4 |
| `YFinanceProvider.get_security_master()` synthetic active flag | `SecurityMasterEntry.active` | `listing_board` + `listing_status` filter | Verify delisted/suspended semantics |

### 4.2 Price History

| Current | Canonical | Future Sectors | Validation |
| --- | --- | --- | --- |
| `yfinance.download(ticker, start, end)` `Close`, `Adj Close`, `Volume` | `PriceObservation.ticker`, `date`, `close`, `adjusted_close`, `volume`, `price_basis` | `GET /v2/daily/{symbol}/` `symbol`, `date`, `close`, `volume`, `market_cap` + `GET /v2/close/` `symbol`, `date`, `close` for cross-section | **VERIFY WITH SECTORS**: `close` basis is raw (G011); `adjusted_close` is currently a mirrored alias for raw close until corporate-action audit proves otherwise; see `SECTORS_PRICE_BASIS.md` and `KNOWN_GAPS.md` G011 |
| Yahoo adjusted close (splits/dividends) | `PriceObservation.price_basis = adjusted_close` | Sectors `close` retained as raw and mirrored to `adjusted_close` with warning | Run `scripts/audit_price_basis.py --ticker BBCA.JK --corporate-action-date 2021-10-13 --sectors-mode SECTORS_LIVE --live --allow-credit-spend` |

### 4.3 Benchmark

| Current | Canonical | Future Sectors | Validation |
| --- | --- | --- | --- |
| `yfinance ^JKSE` `Close` | `BenchmarkObservation.close` | `GET /v2/index-daily/ihsg/` | Verify 90-day window parity: `scripts/compare_providers.py --sectors-mode SECTORS_LIVE --live --allow-credit-spend --as-of YYYY-MM-DD` expects `delta_pct < 0.5%` for ≥80% rows |

### 4.4 Enrichment (Tier 2/3 — not in signal path yet)

| Current | Canonical (frozen) | Future Sectors | Validation |
| --- | --- | --- | --- |
| Not available in yfinance groundwork | `ConfirmationEvidence` fields remain `UNAVAILABLE` / `DATA_GAP` | `GET /v2/free-float/` `free_float` fraction 0–1 | Verify point-in-time semantics, effective date, restatement |
| Bounded `data/fixtures/foreign_flow_sample.csv` (6 market dates, 44 rows, `sample_eligible=false`) | `ForeignFlowSample` `SAMPLE_ONLY_NOT_FULL_UNIVERSE`, `quantitative_use=false` | `GET /v2/foreign-flow/{symbol}/` `net_foreign_inflow` | Verify coverage, missing-day semantics, date alignment |
| `data/derived/research_events.json` (5 curated events, `quantitative_use=false`) | `ResearchEvent` `quantitative_use=false` | `GET /v2/company/corporate-actions/{symbol}/`, `GET /v2/suspensions/` | Verify announcement cutoff, point-in-time eligibility |
| Not weighted | `ConcentrationMetrics` equal-weight | `GET /v2/free-float/` for future weighting channel | Do not silently replace equal-weight with float-weight |

## 5. Taxonomy Migration Requirements

| Aspect | Prototype (current) | Sectors target | Gate |
| --- | --- | --- | --- |
| Taxonomy source | `config/universe.yaml` `sectors` / `sub_sectors` (coarse, analyst-defined) | Sectors `sector` / `sub_sector` / `industry` / `sub_industry` | `SECTORS_BLOCKERS.md` Taxonomy nulls |
| Taxonomy version | `prototype-v1` | `sectors-<date>` or documented Sectors version | `check_snapshot_compatibility` requires exact match |
| Level for primary view | `sector` (config `groups.primary_taxonomy_level`) | Sectors `sub_sector` preferred for diffusion stability (median ≥10 names), `sector` for overview, `industry`/`sub_industry` only when `minimum_constituents=5` and `coverage ≥60%` hold | `docs/TAXONOMY_AUDIT.md` |
| Membership policy | `PRIMARY_ONLY` | `PRIMARY_ONLY` for group aggregation; `MULTI` for Themes only (never double-count into market total) | `config/konglo.yaml`, `config/themes.yaml` `membership_policy: MULTI` with dedup |
| Konglo / Themes | `ANALYST_DEFINED` prototype taxonomies (`konglo-prototype-v1`, `themes-prototype-v1`) with confidence 0.5–0.9 | Only promote to authoritative if Sectors exposes ownership / theme fields and multiple reliable sources verify membership (`VERIFIED`/`SUPPORTED`) | `data/fixtures/foreign_flow_discovery.json` provenance style |

## 6. Universe Parity Requirements

| Check | How |
| --- | --- |
| Discovered count | Sectors `/v2/companies/` `pagination.total_count` vs fixture `data/raw/sectors_validation/` sanitized capture |
| Security-master valid | `normalize_companies` drops duplicates, flags `missing_taxonomy`, `instrument_classification_unverified_rows` |
| Price-history usable | `SectorsProvider.history_diagnostics` `returned_symbols` / `failed_symbols` / `empty_symbols` vs `YFinanceProvider` usable count |
| Eligibility | `src/idx_leadership/providers/market_universe.py` `eligible` = `active` + taxonomy present + sufficient history + freshness (≤30d stale) + not suspended |
| Funnel disclosure | `data/snapshots/<id>/coverage.json` `raw_candidate_constituents`, `policy_eligible_constituents`, `acquisition_failed_constituents`, `observed_eligible_features`, `coverage_pct`, `exclusion_reasons`, plus `is_prefix_sample` and `discovered_universe_disclosure` |

## 7. Return Parity Requirements

* Compute `(P[d]/P[d-h]-1)*100` at `h=5,20,60` trading days from both providers for the prototype 54-name universe.
* Excess = `return_h - benchmark_return_h`.
* Compare `group_excess_return_20d`, `group_excess_return_60d`, `breadth_outperforming`.
* Use `scripts/compare_providers.py` tolerance `delta_pct < 0.5` for ≥80% of overlap rows; investigate `UNEXPLAINED` rows (splits, stale, missing).
* Sectors price basis remains `close` (raw) until audit proves otherwise; do not compare adjusted vs raw without the disclaimer.

## 8. Benchmark Parity Requirements

* Align dates: Sectors `ihsg` `date` vs Yahoo `^JKSE` trading dates.
* Verify 30-day window correlation and spot-check 3 tickers' closes (exercised live 2026-08-27, 3/3 matched) but not market-wide adjusted parity.
* If benchmark latest date diverges >1 trading day, surface `benchmark_latest_date` vs `latest_available_security_trade_date` in `coverage.json` and degrade gracefully (`UNCONFIRMED`).

## 9. Known yfinance Limitations (Must Be Explicit)

* No authoritative IDX security-master discovery; 54-name prototype is not full IDX (≈962 discovered live rows).
* No authoritative taxonomy; prototype `sectors` labels are coarse.
* Corporate-action semantics may differ (adjusted vs unadjusted); holidays handled via trading-day walk, no IDX holiday calendar.
* Intermittent missing observations for thin names; `WSKT.JK` insufficient history example.
* No free-float, no per-ticker or per-group structured foreign-flow, and no
  per-ticker fundamentals. The separate official IDX market-level investor
  release is documented in `docs/IDX_STATISTICS_SOURCE.md` and does not close
  this per-name confirmation gap.
* Benchmark `^JKSE` quality for IDX not validated at scale.

These are labelled `METHODOLOGY VALIDATED ON PUBLIC DATA`, not `PRODUCTION DATA VALIDATED ON SECTORS`.

## 10. Recommended First Sectors Migration Test (When Credentials Authorized)

```bash
# 1. Bounded validation (no snapshot write, one page per endpoint)
.venv/bin/python -m scripts.validate_sectors_live --dry-run --as-of 2026-08-28
.venv/bin/python -m scripts.validate_sectors_live --live --allow-credit-spend --max-pages 1 --as-of 2026-08-28

# 2. Live parity spot-check (3 tickers, 30-day window)
.venv/bin/python -m scripts.compare_providers --sectors-mode SECTORS_LIVE --live --allow-credit-spend --as-of 2026-08-28

# 3. Price-basis audit on known split
.venv/bin/python -m scripts.audit_price_basis --ticker BBCA.JK --start 2021-10-01 --end 2021-10-29 --corporate-action-date 2021-10-13 --sectors-mode SECTORS_LIVE --live --allow-credit-spend --as-of 2021-10-29

# 4. Bounded live snapshot (full listing, 250-history demo sample, 400-attempt cap)
.venv/bin/python -m scripts.build_market_snapshot --allow-live --allow-credit-spend --max-symbols 250 --max-http-requests 400 --max-estimated-credits 1000 --history-workers 1 --as-of 2026-08-28
.venv/bin/python -m scripts.export_snapshot_json --snapshot-id snap_sectors_2026-08-28
.venv/bin/python -m scripts.build_snapshot_index --provider-mode SECTORS_LIVE

# 5. Credit audit (fill before/after balances)
.venv/bin/python -m scripts.audit_sectors_credit --ledger data/raw/sectors_validation/<run>/request_ledger.jsonl --before-balance <int> --after-balance <int>
```

All live calls are gated by `SECTORS_API_KEY` env var and `--allow-live --allow-credit-spend`; the client hard-stops before any request that would exceed `max_estimated_credits`. See `docs/LIVE_SECTORS_RUNBOOK.md`.

## 11. Contract Enforcement

* `tests/test_provider_contracts.py` — fixture-only contract tests for Sectors normalizers
* `tests/test_snapshot_comparability.py` — fail-closed comparability (requires `provider_mode`, `price_basis`, `eligible_ticker_set_hash`, all version fields)
* `tests/test_parity_public_sectors.py` — bounded parity harness (expects fixture, not live)
* `src/idx_leadership/pipeline.py:_load_compatible_history` — only earlier, comparable snapshots contribute to diffusion `breadth_delta` and `diffusion_state_v2`
* `scripts/export_snapshot_json.py:_enrich_with_taxonomy_views` — only taxonomy views built for exact `snapshot_id`/`provider_mode`/`price_basis`/`as_of` are attached
* Any field listed above with `VERIFY WITH SECTORS` must remain `UNKNOWN / VERIFY` in docs until a live probe fills it; see `SECTORS_BLOCKERS.md`.
