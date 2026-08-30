# Sectors API Audit

> **Source of truth for this document:** the official Sectors v2 documentation at
> `https://docs.sectors.app` (checked 2026-08-28). Each endpoint section includes
> the path, parameters, and response shape taken directly from the docs.
>
> Live calls were exercised on 2026-08-28 with the project credential. Response
> captures are sanitized and stored under `data/raw/sectors_validation/`; no
> credential material is persisted. Where the documentation and observed
> response differ, the field is marked `UNKNOWN / VERIFY` rather than inferred.

## 1. Base contract

| Field | Value | Source |
| --- | --- | --- |
| Base URL | `https://api.sectors.app/v2/` | docs.sectors.app overview |
| Auth header | `Authorization: <api-key>` (no `Bearer ` prefix) | every endpoint page |
| Documented screener pagination | `offset=0, limit=50` (max `limit=200`) | Companies Screener documentation |
| Documented close pagination | `offset=0, limit=20` (max `limit=30`) | Daily Full-Universe Close documentation |
| Observed companies pagination | `limit=200` returned 200 rows and `next_offset=200` | authenticated probe; consistent with the current screener contract |
| Common error codes | `400` (bad request), `404` (not found), `429` (`RATE_LIMIT_EXCEEDED`) | docs |
| `RATE_LIMIT_EXCEEDED` body | `{"error": "RATE_LIMIT_EXCEEDED", "message": "Rate limit exceeded. Consider upgrading."}` | `free-float` example |
| Versioning | v1 was discontinued 2026-05-11; only v2 supported | overview |

## 2. Endpoint-by-endpoint audit

### 2.1 `GET /v2/companies/`

- **Purpose:** IDX-wide company screener.
- **Granularity:** one row per company (paginated).
- **Pagination:** `offset`, `limit (max 200)`, response `pagination.total_count`.
- **Key fields in response (confirmed from docs):** `symbol`, `company_name`, `listing_board`, `industry`, `sub_industry`, `sector`, `sub_sector`, `market_cap`, `market_cap_rank`, `employee_num`, `listing_date`, `last_close_price`, `daily_close_change`, `forward_pe`, `intrinsic_value`, `esg_score`, `yield_ttm`, `dividend_ttm`, `payout_ratio`, `cash_payout_ratio`, `yoy_quarter_earnings_growth`, `yoy_quarter_revenue_growth`, `tags`, `indices`, `affiliates`.
- **Query modes:** `q` (natural language) **or** `where`+`order_by` (SQL-like, mutually exclusive).
- **Filter fields:** sector, sub_sector, industry, sub_industry (kebab-case slugs).
- **Bracket notation:** `field[YYYY]` for historical/forecast.
- **Arithmetic:** allowed on both sides of comparison.
- **Smart FY handling:** Jan–Apr queries default to the previous audited year.
- **Credit cost:** **1 credit per page for structured queries**; natural-language
  `q` queries cost **3 credits**. The unfiltered listing form is not used by the
  live provider because its price is not stated on the public page.
- **Use here:** canonical security master + taxonomy (replaces the local YAML).

**Live observation (2026-08-28):** a structured identity query using
`where=symbol IS NOT NULL` returned the full identity population at
`limit=200`. A second structured `where` query with
`include_query_values=true` returned nested taxonomy and listing-board values.
The live provider merges those two known-cost passes; missing taxonomy remains
an explicit diagnostic.

### 2.2 `GET /v2/close/`

- **Purpose:** daily full-universe close cross-section.
- **Granularity:** one row per ticker (paginated).
- **Default date:** most recent trading day with data.
- **Pagination:** `offset`, `limit (max 30)`.
- **Response fields:** `symbol`, `date (YYYY-MM-DD)`, `close`.
- **Tickers with no recorded close for the day are omitted from the response.**
- **Future dates return `400`.**
- **Credit cost (DOCUMENTED):** **1 credit per page**; full ~950-ticker universe ≈ 32 credits at `limit=30`.
- **Use here:** latest-date discovery and current-close evidence. Historical
  returns use the per-symbol daily route below. **Treated as raw close** until
  a corporate-action audit proves otherwise (see `KNOWN_GAPS.md` G011).

**Live observation (2026-08-28):** the latest observed market date was
2026-08-27. A request for `date=2026-08-28` returned HTTP 200 with no rows,
where the documentation describes a future-date 400 response. The distinction
between “no close published yet” and “future date” is therefore
`UNKNOWN / VERIFY`; the runner resolves the latest date from a one-page
date-discovery request and never relabels an empty requested date.

The close endpoint was not used to reconstruct the full historical panel: its
per-page cost would make that unnecessarily expensive. The live history path
uses the documented per-symbol daily route below.

### 2.3 `GET /v2/daily/{symbol}/`

- **Purpose:** per-security daily history.
- **Live observation (2026-08-28):** `BBCA.JK` returned 61 dated rows for
  2026-05-29 through 2026-08-27, including `symbol`, `date`, `close`, `volume`,
  and `market_cap`. The 90-calendar-day request boundary was accepted.
- **Credit cost:** **1 credit per call** according to the current endpoint
  documentation; actual account debit is not exposed to this client.
- **Basis:** close is retained as raw close and mirrored to the canonical
  adjusted-close slot with an explicit `UNKNOWN / VERIFY` corporate-action
  warning.

### 2.4 `GET /v2/index-daily/{index}/`

- **Purpose:** native index history.
- **Live observation (2026-08-28):** `/v2/index-daily/ihsg/` returned dated
  `index_code`, `date`, and `price` rows for the requested window and was used
  as the benchmark in the live snapshot.
- **Credit cost:** **1 credit per call** according to the current endpoint
  documentation; actual account debit is not exposed to this client.

### 2.5 `GET /v2/free-float/`

- **Purpose:** free-float percentage for IDX-listed companies, optionally filtered to one taxonomy level.
- **Granularity:** one row per company.
- **Response fields:** `symbol`, `company_name`, `free_float` (fraction 0–1).
- **Definition (DOCUMENTED):** `share_percentage` of the `Public` entry in the company's major shareholders list.
- **Filter parameters (MUTUALLY EXCLUSIVE):** `sector`, `sub_sector`, `industry`, `sub_industry` (kebab-case slugs).
- **Credit cost (DOCUMENTED):** **1 credit per 100 companies returned, rounded up.**
- **Order:** descending by `free_float`.
- **Use here:** separate "magnitude" weighting channel (D011 in `DECISION_LOG.md`).

### 2.6 `GET /v2/foreign-flow/{symbol}/`

- **Purpose:** daily net foreign-broker inflow (IDR) for one ticker over a date range.
- **Path param:** `symbol` (4 letters, optional `.JK`, case-insensitive).
- **Date window:** up to **90 days**.
- **Response:** `{symbol, start, end, data: [{date, net_foreign_inflow}]}`.
- **Sign convention (DOCUMENTED):** positive = net foreign buying; negative = net selling.
- **Domestic note (DOCUMENTED):** domestic flow is `−net_foreign_inflow` (closed market identity).
- **Error codes:** `404` if symbol not in broker data; `429` rate limit.
- **Credit cost (DOCUMENTED):** **1 credit per call**.
- **Use here:** Tier-3 enrichment only — invoked when a transition is flagged material, for the top driver per highlighted group.

### 2.7 `GET /v2/company/corporate-actions/{symbol}/`

- **Purpose:** full corporate-action history per ticker.
- **Response structure (DOCUMENTED):** `{symbol, corporate_actions: {agm[], bonus, warrant, dividend[], right_issue, stock_split[], upcoming_dividend}}`.
- **Dividend fields:** `ex_date`, `payment_date`, `dividend_yield`, `dividend_amount`.
- **Stock split fields:** `date`, `split_ratio`.
- **AGM fields:** `agm_date`, `agm_time`, `agm_place`, `agm_result`.
- **Credit cost (DOCUMENTED):** **1 credit per call**.
- **Error:** `404` if no data.
- **Use here:** corporate-action guardrail. Mark affected security with `caveat`; do not silently edit prices.

### 2.8 `GET /v2/suspensions/`

- **Purpose:** historical IDX stock suspensions.
- **Filters:** `symbol` (single), `start`, `end` (independent and optional).
- **Response fields:** `symbol`, `suspension_date`, `reason`, `pdf_url` (IDX notice).
- **Credit cost (DOCUMENTED):** **1 credit per call**.
- **Future `end` dates return `400`.**
- **Use here:** suspension filter in the universe eligibility check (excluded from current breadth denominator).

### 2.9 `GET /v2/company/report/{symbol}/`

- **Purpose:** per-company overview + valuation + future + financials + ratios.
- **Response (partial, DOCUMENTED):** `overview` (listing board, industry, sub_industry, sector, sub_sector, market_cap, market_cap_rank, listing_date, last_close_price, latest_close_date, daily_close_change, all_time_price{...}, esg_score, tags, indices, affiliates), `valuation` (forward_pe, intrinsic_value, historical_valuation[{pb, pe, ps, pcf, peg, year, ...}]), `future` (company_value_forecasts, company_growth_forecasts, analyst_rating_breakdown), `financials` (eps, historical_eps, ...).
- **Use here:** Tier 2 enrichment for group drilldown (subsector report style). Not auto-applied.
- **Credit cost:** `UNKNOWN / VERIFY` (not stated on the doc page).

### 2.10 Other endpoints of interest (NOT integrated this pass)

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

- **Authentication is uniform in the exercised routes:** the raw API key in the
  `Authorization` header authenticated the Sectors calls. No per-endpoint
  scoping was observed.
- **Pagination is consistent in the exercised list routes:** responses carried
  `results` plus pagination metadata. The current screener documentation allows
  `limit=200`; the close feed remains capped at 30.
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
| Actual account debit and remaining balance | response did not expose a usable balance/debit field | reconcile against the Sectors account dashboard |
| Unfiltered companies-form pricing | the public page prices structured and natural-language queries but does not state the unfiltered-form price | the provider uses `where=symbol IS NOT NULL` instead |
| Whether an empty close response for the current calendar date means “future” or “not published” | observed 200 empty vs documented future-date 400 | verify with a known future date and the provider response contract |
| Split/dividend adjustment behavior on historical closes | docs silent | pair a corporate-action call with public adjusted/raw history |
| Complete instrument classification | company responses exposed no explicit instrument-type field in the sampled live rows | add an authoritative field or issuer/instrument review before claiming a pure common-equity universe |

## 5. Endpoint summary table

| Endpoint | Method | Cost (doc'd) | Pagination | Date filter | Path filter | Used by engine |
| --- | --- | --- | --- | --- | --- | --- |
| `/v2/companies/` | GET | **1 structured / 3 natural-language** | offset/limit (max 200) | — | — | yes (security master + taxonomy) |
| `/v2/close/` | GET | **1/page** | offset/limit (max 30) | `date` | — | yes (latest-date discovery) |
| `/v2/daily/{symbol}/` | GET | **1/call** | none observed | `start`, `end` (≤90d) | `symbol` | yes (security history) |
| `/v2/index-daily/{index}/` | GET | **1/call** | none observed | `start`, `end` | `index` | yes (IHSG benchmark) |
| `/v2/free-float/` | GET | **1 / 100 co** | none observed | — | sector/sub_sector/industry/sub_industry | no (deferred weighting) |
| `/v2/foreign-flow/{symbol}/` | GET | **1** | none | `start`, `end` (≤90d) | `symbol` | no (deferred confirmation) |
| `/v2/company/corporate-actions/{symbol}/` | GET | **1** | none | — | `symbol` | no (deferred guardrail) |
| `/v2/suspensions/` | GET | **1** | offset/limit | `start`, `end` | `symbol` | yes (eligibility) |
| `/v2/company/report/{symbol}/` | GET | `UNKNOWN` | none | — | `symbol` | research only (Tier 2) |
