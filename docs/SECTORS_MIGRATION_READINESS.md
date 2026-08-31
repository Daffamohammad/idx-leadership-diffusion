# Sectors Migration Readiness

> Status snapshot of the Sectors migration path: what is wired, what is gated,
> what still requires parity validation, and the recommended first live test.
> Last verified 2026-08-30.

## 1. Execution Mode

| Role | Provider | Live calls this pass |
| --- | --- | --- |
| Primary price / benchmark groundwork | `yfinance` (`YFinanceProvider`) via `config/universe.yaml` | YES — public data, no credits |
| Official IDX release extraction | `idx_statistics` HTML parser (`src/idx_leadership/providers/idx_statistics.py`) | July 2026 market-level investor-type table, 23 trading days, reconciled and integrated |
| Research / discovery | Tavily + YOU.com (`scripts/enrich_tavily_context.py`, `scripts/enrich_you_context.py`) | Bounded, qualitative discovery/context only (`quantitative_use:false`) |
| Future production provider | `SectorsProvider` (live-gated) | NO — intentionally deferred |

Sectors-native validation is deferred until the human operator authorizes
`SECTORS_API_KEY` + `--allow-live --allow-credit-spend`. No live Sectors calls
were performed in this implementation pass; the existing `snap_sectors_2026-08-27`
snapshot remains the persisted live artifact from the prior credentialed run.

## 2. Provider Adapter Status

| Component | Path | Status |
| --- | --- | --- |
| `SectorsClient` | `src/idx_leadership/providers/sectors_client.py` | Implemented, live-gated, fixture-tested |
| `SectorsProvider` | `src/idx_leadership/providers/sectors.py` | Implemented, live-gated, fixture-tested |
| `SectorsNormalizers` | `src/idx_leadership/providers/sectors_normalizers.py` | Implemented |
| `SectorsContracts` | `src/idx_leadership/providers/sectors_contracts.py` | Implemented |
| `SectorsFixture` | `src/idx_leadership/providers/sectors_fixture.py` | Implemented for offline CI |
| `ProviderFactory` | `src/idx_leadership/providers/factory.py` | Three modes wired: `YFinanceProvider`, `SectorsProvider`, `FixtureProvider`; no silent fallback |

Operational parameters (verified in source):

- Screener pagination: `limit=200` (`sectors.py:188, 206, 629`)
- Close pagination: `limit=30` (`sectors.py:328, 349`; `sectors_client.py:235`)
- Daily history: 90-day maximum per call (`sectors.py:393`)
- Benchmark: native IHSG via `/v2/index-daily/ihsg/`
- Credit cap: `DEFAULT_MAX_ESTIMATED_CREDITS = 1_000.0` (`sectors_client.py:28`)
- Mode gate: requests only fire when `ProviderMode.SECTORS_LIVE` AND
  `max_estimated_credits` is not `None` (`sectors_client.py:577`)
- Hard refusal: preflight raises if requested cost would exceed cap
  (`sectors_client.py:587-591`)

## 3. Canonical Schema Readiness

Canonical schemas are Sectors-ready. All provider outputs pass through
`src/idx_leadership/models/schemas.py` and the normalized Sectors contract;
analytics consume canonical `pd.DataFrame` shapes, never raw API payloads.

## 4. Required Future Sectors Endpoints

These are the endpoints the live migration will exercise. Endpoint costs
are documented in `docs/SECTORS_API_AUDIT.md`.

| Endpoint | Purpose | Cost class |
| --- | --- | --- |
| `/v2/companies/` | Security master (taxonomy, identifiers, listing) | unknown / `VERIFY WITH SECTORS` |
| `/v2/close/` | Latest-date close discovery | per_page |
| `/v2/daily/{symbol}/` | Historical close-by-close | per_call_1 |
| `/v2/index-daily/ihsg/` | IHSG benchmark series | per_call_1 |
| `/v2/free-float/` | Free-float enrichment | per_100_companies |
| `/v2/foreign-flow/{symbol}/` | Foreign-flow enrichment | per_call_1 |
| `/v2/company/corporate-actions/{symbol}/` | Corporate-action audit | per_call_1 |
| `/v2/suspensions/` | Suspension detection | per_call_1 |

## 5. Fields Requiring Parity Validation

These fields must be compared against yfinance groundwork before promoting
Sectors as the production provider.

- `price_basis`: Sectors `close` (raw) vs yfinance `adjusted_close` —
  audit via `scripts/audit_price_basis.py --ticker <TICKER> --corporate-action-date <DATE>`.
  Documented open gap G011.
- `eligible_ticker_set_hash` — must match between providers at snapshot boundaries.
- All version fields: `provider_mode`, `price_basis`, `method_version`,
  `feature_version`, `leadership_version`, `diffusion_version`,
  `concentration_version`, `eligibility_version`, `universe_version`,
  `taxonomy_version` (see `src/idx_leadership/data/comparability.py`).
- Taxonomy nulls and instrument classification (counters on `taxonomy_complete_securities`).
- Credit debit (Sectors balance remains `BALANCE UNAVAILABLE` to the client).

## 6. Taxonomy Migration Requirements

| Source | Current state | Migration target |
| --- | --- | --- |
| Sectors | n/a (deferred) | Authoritative `sector / sub_sector / industry / sub_industry`; primary analytical view at `sub_sector` for diffusion stability |
| Prototype (`config/universe.yaml`) | `prototype-v1` (54 tickers, sector-only) | Replaced once Sectors master lands; do not aggregate during transition |
| Konglo (`config/konglo.yaml`) | `konglo-prototype-v1`, `ANALYST_DEFINED` | Remains analyst-defined unless provider-authoritative data is acquired and verified |
| Themes (`config/themes.yaml`) | `themes-prototype-v1`, `ANALYST_DEFINED`, MULTI policy | Remains analyst-defined; multi-membership never double-counts across themes |

Every taxonomy declares `taxonomy_id`, `taxonomy_version`, `source_kind`,
`source/provider`, `as_of`, and `membership_methodology` in
`config/universe.yaml`, `config/konglo.yaml`, `config/themes.yaml`.

## 7. Universe Parity

| Metric | Prototype (yfinance) | Sectors (persisted, not active this pass) |
| --- | --- | --- |
| Discovered | 54 (config) | 962 |
| Used | 54 | 500 (alphabetical prefix sample, `is_prefix_sample: true`) |
| Policy-eligible | 53 | 265 |
| Coverage | 98.15% | 100% taxonomy coverage |
| Acquisition failures | 0 | 0 |
| Excluded by reason | 1 insufficient_history | 235 (123 liquidity, 98 listing_board, 10 suspended, 4 history) |

Source: `data/snapshots/snap_sectors_2026-08-27/coverage.json`,
`data/snapshots/snap_public_2026-08-20/coverage.json`.

The Sectors persisted snapshot is a prefix sample, not full IDX coverage.
Funnel counts and `exclusion_reasons` must be surfaced in any UI claiming
Sectors-backed classification (see Methodology page Evidence Matrix).

### Foreign-flow authoritative source (reviewed and integrated)

The direct IDX Digital Statistics page for July 2026 is the source for the
market-level release integrated into the web product:

```
https://www.idx.co.id/id/data-pasar/laporan-statistik/digital-statistic/monthly/equity-trading-by-investor/table-daily-trading-by-type-of-investor?filter=eyJ5ZWFyIjoiMjAyNiIsIm1vbnRoIjoiNyIsInF1YXJ0ZXIiOjAsInR5cGUiOiJtb250aGx5In0%3D
```

The parser consumes the two daily HTML tables and emits a **monthly release
made of daily market-level rows**, not a per-ticker observation. The checked-in
artifact is `app/web/public/idx/idx_investor_trading_2026-07.json`. The current
bounded-sample foreign-flow fixture (`data/derived/foreign_flow_sample.json`)
remains correct: it is a daily top-list sample. Both can coexist; neither
provides per-ticker/group ownership confirmation.

The statistics index is a separate discovery surface for Daily Statistics PDFs:

```text
https://www.idx.co.id/id/data-pasar/laporan-statistik/statistik/
```

The index parser extracts dated PDF links. PDF tiles such as Today/YTD net
foreign and Market PER/PBV are not promoted until a dedicated PDF parser has a
regression fixture; screenshot text is never treated as data.

## 8. Return / Benchmark Parity Targets

- Return parity: `delta_pct < 0.5` for ≥ 80% of matched securities at the
  5D / 20D / 60D horizons. Verify via `scripts/compare_providers.py`.
- Benchmark parity: Sectors `^JKSE` (via `/v2/index-daily/ihsg/`) vs yfinance
  `^JKSE` over a 30-day window. Verify in same script.

Until these thresholds are met live, snapshot exports keep `provider_mode`
and `price_basis` in `comparability.json` and the SPA surfaces
`READY_WITH_GAPS` for any panel that depends on cross-provider agreement.

## 9. Known yfinance Limitations

These are the limitations that Sectors migration is expected to resolve; they
must remain explicit until Sectors-native data supersedes them.

- No authoritative IDX security master; relying on a 54-ticker config.
- Coarse taxonomy: `sector` only; no `industry / sub_industry` mapping.
- No structured free-float or per-ticker/group ownership-flow fields. The
  official market-level IDX investor release is a separate reconciled lane.
- Thin-name securities intermittently missing from history.
- No IDX holiday calendar; benchmark observations may walk across IDX
  holidays incorrectly.
- Corporate-action semantics: `adjusted_close` vs `close` reconciliation
  not yet audited end-to-end (G011).

## 10. Recommended First Sectors Migration Test Sequence

Run in this exact order; do not skip steps. Each command refuses to proceed
without the previous gate satisfied.

```bash
# 1. Dry-run — exercises the full request graph with zero Sectors calls.
.venv/bin/python scripts/validate_sectors_live.py --dry-run

# 2. First live call — one page only, under the credit cap.
.venv/bin/python scripts/validate_sectors_live.py \
    --live --allow-credit-spend --max-pages 1

# 3. Provider parity — yfinance vs Sectors on matched securities.
.venv/bin/python scripts/compare_providers.py \
    --as-of 2026-08-27 --live --allow-credit-spend

# 4. Price basis audit — concrete corporate-action case.
.venv/bin/python scripts/audit_price_basis.py \
    --ticker BBCA.JK --corporate-action-date 2021-10-13

# 5. Build market snapshot under the documented credit cap.
.venv/bin/python -m scripts.build_market_snapshot \
    --max-estimated-credits 1000
```

A green pass at each step is required before promoting
`provider_mode=SECTORS_LIVE` as the active SPA snapshot.

## 11. Reference Documents

- `docs/SECTORS_MIGRATION_CONTRACT.md` — field-level parity checklist.
- `docs/SECTORS_API_AUDIT.md` — per-endpoint cost audit and `UNKNOWN/VERIFY` items.
- `docs/SECTORS_PRICE_BASIS.md` — adjusted vs raw close analysis (G011).
- `docs/SECTORS_CREDIT_AUDIT.md` — observed credit behavior; `BALANCE UNAVAILABLE`.
- `docs/SECTORS_BLOCKERS.md` — known blockers and resolution paths.
- `docs/SECTORS_REFRESH_BUDGET.md` — refresh cadence and credit budgeting.
- `docs/PROVIDER_PARITY_REPORT.md` — parity harness documentation.
- `docs/LIVE_SECTORS_RUNBOOK.md` — operator playbook.
