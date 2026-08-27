# Sectors API Audit

> **Source of truth for this document:** the official Sectors v2 documentation at
> `https://docs.sectors.app` (fetched 2026-08-27). Each endpoint section includes
> the path, parameters, and response shape taken directly from the docs.
>
> Live calls were **not** issued during this pass because no API key was present in
> the environment. Where a contract is unclear, the field is marked `UNKNOWN / VERIFY`.

## 1. Base contract

| Field | Value | Source |
| --- | --- | --- |
| Base URL | `https://api.sectors.app/v2/` | docs.sectors.app overview |
| Auth header | `Authorization: <api-key>` (no `Bearer ` prefix) | every endpoint page |
| Default pagination | `offset=0, limit=20` (max `limit=30`) | every paginated endpoint |
| Common error codes | `400` (bad request), `404` (not found), `429` (`RATE_LIMIT_EXCEEDED`) | docs |
| `RATE_LIMIT_EXCEEDED` body | `{"error": "RATE_LIMIT_EXCEEDED", "message": "Rate limit exceeded. Consider upgrading."}` | `free-float` example |
| Versioning | v1 was discontinued 2026-05-11; only v2 supported | overview |

## 2. Endpoint-by-endpoint audit

### 2.1 `GET /v2/companies/`

- **Purpose:** IDX-wide company screener.
- **Granularity:** one row per company (paginated).
- **Pagination:** `offset`, `limit (max 30)`, response `pagination.total_count`.
- **Key fields in response (confirmed from docs):** `symbol`, `company_name`, `listing_board`, `industry`, `sub_industry`, `sector`, `sub_sector`, `market_cap`, `market_cap_rank`, `employee_num`, `listing_date`, `last_close_price`, `daily_close_change`, `forward_pe`, `intrinsic_value`, `esg_score`, `yield_ttm`, `dividend_ttm`, `payout_ratio`, `cash_payout_ratio`, `yoy_quarter_earnings_growth`, `yoy_quarter_revenue_growth`, `tags`, `indices`, `affiliates`.
- **Query modes:** `q` (natural language) **or** `where`+`order_by` (SQL-like, mutually exclusive).
- **Filter fields:** sector, sub_sector, industry, sub_industry (kebab-case slugs).
- **Bracket notation:** `field[YYYY]` for historical/forecast.
- **Arithmetic:** allowed on both sides of comparison.
- **Smart FY handling:** Jan–Apr queries default to the previous audited year.
- **Credit cost:** `UNKNOWN / VERIFY` (not stated on the doc page).
- **Use here:** canonical security master + taxonomy (replaces the local YAML).

### 2.2 `GET /v2/close/`

- **Purpose:** daily full-universe close cross-section.
- **Granularity:** one row per ticker (paginated).
- **Default date:** most recent trading day with data.
- **Pagination:** `offset`, `limit (max 30)`.
- **Response fields:** `symbol`, `date (YYYY-MM-DD)`, `close`.
- **Tickers with no recorded close for the day are omitted from the response.**
- **Future dates return `400`.**
- **Credit cost (DOCUMENTED):** **1 credit per page**; full ~950-ticker universe ≈ 32 credits at `limit=30`.
- **Use here:** primary price source for the engine. **Treated as raw close** until a corporate-action audit proves otherwise (see `KNOWN_GAPS.md` G011).

### 2.3 `GET /v2/free-float/`

- **Purpose:** free-float percentage for IDX-listed companies, optionally filtered to one taxonomy level.
- **Granularity:** one row per company.
- **Response fields:** `symbol`, `company_name`, `free_float` (fraction 0–1).
- **Definition (DOCUMENTED):** `share_percentage` of the `Public` entry in the company's major shareholders list.
- **Filter parameters (MUTUALLY EXCLUSIVE):** `sector`, `sub_sector`, `industry`, `sub_industry` (kebab-case slugs).
- **Credit cost (DOCUMENTED):** **1 credit per 100 companies returned, rounded up.**
- **Order:** descending by `free_float`.
- **Use here:** separate "magnitude" weighting channel (D011 in `DECISION_LOG.md`).

### 2.4 `GET /v2/foreign-flow/{symbol}/`

- **Purpose:** daily net foreign-broker inflow (IDR) for one ticker over a date range.
- **Path param:** `symbol` (4 letters, optional `.JK`, case-insensitive).
- **Date window:** up to **90 days**.
- **Response:** `{symbol, start, end, data: [{date, net_foreign_inflow}]}`.
- **Sign convention (DOCUMENTED):** positive = net foreign buying; negative = net selling.
- **Domestic note (DOCUMENTED):** domestic flow is `−net_foreign_inflow` (closed market identity).
- **Error codes:** `404` if symbol not in broker data; `429` rate limit.
- **Credit cost (DOCUMENTED):** **1 credit per call**.
- **Use here:** Tier-3 enrichment only — invoked when a transition is flagged material, for the top driver per highlighted group.

### 2.5 `GET /v2/company/corporate-actions/{symbol}/`

- **Purpose:** full corporate-action history per ticker.
- **Response structure (DOCUMENTED):** `{symbol, corporate_actions: {agm[], bonus, warrant, dividend[], right_issue, stock_split[], upcoming_dividend}}`.
- **Dividend fields:** `ex_date`, `payment_date`, `dividend_yield`, `dividend_amount`.
- **Stock split fields:** `date`, `split_ratio`.
- **AGM fields:** `agm_date`, `agm_time`, `agm_place`, `agm_result`.
- **Credit cost (DOCUMENTED):** **1 credit per call**.
- **Error:** `404` if no data.
- **Use here:** corporate-action guardrail. Mark affected security with `caveat`; do not silently edit prices.

### 2.6 `GET /v2/suspensions/`

- **Purpose:** historical IDX stock suspensions.
- **Filters:** `symbol` (single), `start`, `end` (independent and optional).
- **Response fields:** `symbol`, `suspension_date`, `reason`, `pdf_url` (IDX notice).
- **Credit cost (DOCUMENTED):** **1 credit per call**.
- **Future `end` dates return `400`.**
- **Use here:** suspension filter in the universe eligibility check (excluded from current breadth denominator).

### 2.7 `GET /v2/company/report/{symbol}/`

- **Purpose:** per-company overview + valuation + future + financials + ratios.
- **Response (partial, DOCUMENTED):** `overview` (listing board, industry, sub_industry, sector, sub_sector, market_cap, market_cap_rank, listing_date, last_close_price, latest_close_date, daily_close_change, all_time_price{...}, esg_score, tags, indices, affiliates), `valuation` (forward_pe, intrinsic_value, historical_valuation[{pb, pe, ps, pcf, peg, year, ...}]), `future` (company_value_forecasts, company_growth_forecasts, analyst_rating_breakdown), `financials` (eps, historical_eps, ...).
- **Use here:** Tier 2 enrichment for group drilldown (subsector report style). Not auto-applied.
- **Credit cost:** `UNKNOWN / VERIFY` (not stated on the doc page).

### 2.8 Other endpoints of interest (NOT integrated this pass)

- `/v2/indonesia/brokers/broker-activity-by-code`
- `/v2/indonesia/brokers/broker-activity-top`
- `/v2/indonesia/brokers/broker-registry`
- `/v2/indonesia/brokers/broker-summary-by-symbol`
- `/v2/indonesia/brokers/broker-summary-top`
- `/v2/indonesia/company/shareholders-composition`
- `/v2/indonesia/helper-list/company-quarterly-dates`
- `/v2/indonesia/helper-list/latest-quarterly-dates`
- `/v2/indonesia/news/news`
- `/v2/indonesia/report/company-report` (partial — see §2.7)

## 3. Cross-cutting observations

- **Authentication is uniform:** all endpoints use the same `Authorization` header. No
  per-endpoint scoping observed.
- **Pagination is uniform:** `{results, pagination: {total_count, showing, limit,
  offset, has_next, has_previous, next_offset, previous_offset}}` shape.
- **Credit costs are documented per-endpoint** in the prose ("Costs N API credit(s)").
  This makes `SECTORS_CREDIT_AUDIT.md` tractable without an active key — see
  `docs/SECTORS_CREDIT_AUDIT.md` for the budget table.
- **Rate-limit error is a separate, well-typed payload** — easy to detect and back off.
- **Documented 410 Gone for `/v1/*`:** the client MUST use `/v2/` exclusively.
- **Bracketed field notation `field[YYYY]`** is part of the structured query language; only
  relevant for the screener endpoint.

## 4. UNKNOWN / VERIFY items

| Item | Reason | Required action |
| --- | --- | --- |
| `close` field adjustment basis (raw vs split/dividend adjusted) | docs do not state | corporate-action audit, then choose basis (see `KNOWN_GAPS.md` G011) |
| Credit cost for `/v2/companies/`, `/v2/company/report/{symbol}/`, `/v2/suspensions/` over window | not always stated | initial Sectors call with key will record in `RequestLedger` |
| Maximum lookback window for `/v2/close/` per single call | only `date` is documented, not `start/end` | probe with key |
| `/v2/close/` adjustment for splits when querying historical dates | docs silent | probe; pair with `corporate-actions` |
| Whether `companies` paginates the same way as `close` | confirmed for `close`; not explicitly for `companies` | client should support both anyway |

## 5. Endpoint summary table

| Endpoint | Method | Cost (doc'd) | Pagination | Date filter | Path filter | Used by engine |
| --- | --- | --- | --- | --- | --- | --- |
| `/v2/companies/` | GET | `UNKNOWN` | offset/limit (max 30) | — | — | yes (security master + taxonomy) |
| `/v2/close/` | GET | **1/page** | offset/limit (max 30) | `date` | — | yes (primary price) |
| `/v2/free-float/` | GET | **1 / 100 co** | none observed | — | sector/sub_sector/industry/sub_industry | yes (magnitude weight) |
| `/v2/foreign-flow/{symbol}/` | GET | **1** | none | `start`, `end` (≤90d) | `symbol` | yes (Tier 3, on demand) |
| `/v2/company/corporate-actions/{symbol}/` | GET | **1** | none | — | `symbol` | yes (guardrail) |
| `/v2/suspensions/` | GET | **1** | offset/limit | `start`, `end` | `symbol` | yes (eligibility) |
| `/v2/company/report/{symbol}/` | GET | `UNKNOWN` | none | — | `symbol` | research only (Tier 2) |
