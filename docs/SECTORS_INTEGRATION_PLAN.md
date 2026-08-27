# Sectors Integration Plan

> Status: **core implementation shipped; live validation pending**. The
> client/provider, core endpoints, request ledger, and market-snapshot
> path are implemented and live-gated. This document now tracks the
> remaining parity and enrichment work.

## 1. Tiered credit discipline

| Tier | Goal | Typical endpoints | Default frequency |
| --- | --- | --- | --- |
| 1 — Market-wide core | Replace the prototype data backbone | companies/universe, full-universe daily close, IHSG/index history | daily |
| 2 — Selected enrichment | Add group-level qualitative corroboration | subsector report, fundamental screener, free float | weekly / on-demand |
| 3 — Targeted evidence | Add per-name confirmation | foreign flow, broker activity, financials, corporate actions, filings, news, suspensions | on-demand, per-name |

The provider architecture supports tiers via
`CapabilityProvider`. Tier 1 is `MarketDataProvider`; Tiers 2 and 3 are
separate mixins.

## 2. Mapping future requirements to Sectors capabilities

| Future requirement | Likely Sectors capability | Tier |
| --- | --- | --- |
| Replace prototype universe with full IDX | `companies` / universe endpoint | 1 |
| Daily close for the full universe | full-universe-close | 1 |
| IHSG index history | index endpoint | 1 |
| Authoritative taxonomy | `subsector report` / taxonomy endpoint | 1 or 2 |
| Free-float weighting | `get_free_float` / companies.free_float | 2 |
| Group qualitative text | `subsector report` | 2 |
| Foreign flow per ticker | `get_foreign_flow` | 3 |
| Broker activity per ticker | `get_broker_activity` | 3 |
| Quarterly financials | `get_company_fundamentals` | 2 |
| Corporate actions | `get_corporate_actions` | 3 |
| Filings | `get_filings` | 3 |
| Suspensions | (sector-native) | 3 |
| News | (sector-native) | 3 |

## 3. Integration sequence (P0 list, from `NEXT_ITERATION.md`)

### P0.1 — Sectors authentication + client (shipped; live-gated)

- Read API key from `SECTORS_API_KEY` env var.
- Wrap the HTTP client in `SectorsProvider` with bounded retries.
- Wire the `RequestLedger` so every Sectors call records
  `actual_credit_cost` once Sectors publishes a credit model.

### P0.2 — Full-universe daily close integration (shipped)

- Implement `SectorsProvider.get_full_universe_close(as_of)`.
- Cache aggressively (raw payloads under `data/raw/sectors/`).
- Update `compute_excess_returns` to consume cross-sections, not
  per-ticker history. The current `get_price_history` shape can be
  retained for backward compatibility.

### P0.3 — Sectors security master and taxonomy (shipped)

- Implement `SectorsProvider.get_security_master()` and
  `get_group_taxonomy()`.
- Replace `config/universe.yaml` taxonomy with the Sectors mapping.
- The `group_id` becomes the Sectors `subsector_id` (or
  `industry_id`).

### P0.4 — IHSG benchmark from Sectors (shipped; parity pending)

- Implement `SectorsProvider.get_benchmark_history("IHSG", ...)`.
- Cross-validate against Yahoo `^JKSE` for a 30-day window as part of
  the parity test (P0.5).

### P0.5 — Provider parity validation

For a controlled subset (e.g. the 10 Financials names) compare:

- daily closes (Sectors vs yfinance),
- 5/20/60-day returns,
- excess returns vs IHSG,
- taxonomy labels.

Use `tests/test_provider_parity.py` to lock down a tolerance
threshold. Surface deltas as a CI artifact.

### P0.6 — Market-wide snapshot generation (shipped; live run pending)

Replace the prototype universe with the full Sectors universe in
`build_snapshot`. Keep the snapshot writer / manifest contract
unchanged. Cost: 1 daily full-universe close + 1 IHSG history pull
+ N company pulls only for the active universe (T1).

### P0.7 — Sectors request/credit audit (shipped; observed costs pending)

Promote `RequestLedger.actual_credit_cost` to a required field on
Sectors calls. Add a daily rollup script that emits a cost-vs-issues
table to `data/normalized/credit_audit.csv`.

### P0.8 — Free-float weighting

Implement `SectorsProvider.get_free_float()`. Switch the group
aggregation from equal-weight to free-float-weight. Update
`compute_concentration` to accept weights. Re-run parity tests.

### P0.9 — Fundamental confirmation integration

Implement `SectorsProvider.get_company_fundamentals()` (Tier 2) and
`get_foreign_flow()` / `get_broker_activity()` (Tier 3). Populate
`FundamentalConfirmation` and `FlowConfirmation`. Add a confirmation
column to `GroupEvidence` (e.g. `fundamental_aligned: bool`).

## 4. VERIFY BEFORE IMPLEMENTATION

> The Sectors public API surface should be confirmed by reading the
> latest official documentation at the start of each implementation
> sprint. Endpoint paths, parameters, authentication, rate limits, and
> credit costs are all subject to change.

Items to verify (not assumed):

- [ ] Authentication mechanism (header name, token format).
- [ ] Rate limits per endpoint.
- [ ] Pricing / credit model per endpoint.
- [ ] Endpoint for "full universe daily close" — exact path and
      parameters.
- [ ] Endpoint for "subsector report" and the exact text structure.
- [ ] Endpoint for "free float" — numeric field name and units.
- [ ] Endpoint for "foreign flow" — date parameter and aggregation
      level.
- [ ] Endpoint for "broker activity" — buyer/seller direction schema.
- [ ] Endpoint for "company fundamentals" — field names for revenue,
      earnings, valuation.
- [ ] Endpoint for "corporate actions" — action type vocabulary.
- [ ] Endpoint for "filings" — filter parameters.

Do not assert undocumented endpoint semantics. `SectorsClient` and
`SectorsProvider` are live-gated and keep unknown credit/field semantics
explicit until a credentialed probe verifies them.

## 5. Migration rollback

The migration must be reversible at every stage:

- The provider factory reads `providers.yaml`; flipping
  `enabled: false` and restarting falls back to yfinance.
- Snapshots written by yfinance remain readable forever.
- Methodology is shared; flipping the provider does not change
  method versions.

This is enforced by D002 (provider abstraction).
