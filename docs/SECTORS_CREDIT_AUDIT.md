# Sectors Credit Audit

> **Approach:** documented endpoint costs were compared with the sanitized
> request ledger from the first credentialed market-wide run on 2026-08-28.
> The client records estimates only; the account balance and actual debit were
> not exposed.
>
> **Balance inspection:** no programmatic balance endpoint was found in the docs.
> The Sectors Insider upgrade page is gated; balance is visible only to the
> authenticated user inside `sectors.app`. The live artifact therefore keeps
> `credit_balance: UNAVAILABLE`.

## 1. Per-endpoint credit costs (DOCUMENTED)

| Endpoint | Cost per call | Source |
| --- | --- | --- |
| `/v2/close/` | **1 credit per page** | docs.sectors.app "Daily Full-Universe Close" |
| `/v2/free-float/` | **1 credit per 100 companies returned, rounded up** | docs.sectors.app "Free Float Market Analysis" |
| `/v2/foreign-flow/{symbol}/` | **1 credit** | docs.sectors.app "Daily Net Foreign Inflow" |
| `/v2/company/corporate-actions/{symbol}/` | **1 credit** | docs.sectors.app "Corporate Actions" |
| `/v2/suspensions/` | **1 credit** | docs.sectors.app "Stock Suspensions" |
| `/v2/companies/` structured `where` | **1 credit per page** | docs.sectors.app "Companies Screener" |
| `/v2/companies/` natural-language `q` | **3 credits per page** | docs.sectors.app "Companies Screener" |
| `/v2/companies/` unfiltered form | `UNKNOWN / VERIFY` | not used by the live provider |
| `/v2/company/report/{symbol}/` | `UNKNOWN / VERIFY` | not stated on the page |

## 2. Refresh budget (estimated from docs)

A standard **latest-date market refresh** consists of:

| Step | Endpoint | Cost (est.) | Notes |
| --- | --- | --- | --- |
| Structured security master + taxonomy | `/v2/companies/` | **10 credits** (2 × ceil(962 / 200)) | identity pass plus complete-taxonomy pass |
| Latest-date discovery | `/v2/close/` | **1 credit** | one page is enough to read the market date |
| Per-symbol history | `/v2/daily/{symbol}/` | **962 credits** (upper bound) | one bounded 90-day call per discovered symbol |
| Native benchmark | `/v2/index-daily/ihsg/` | **1 credit** | one 90-day call |
| Suspensions | `/v2/suspensions/` | **1 credit** | one bounded eligibility call in the current contract |
| **Cold baseline total** | | **975 credits** | before cache reuse; 25-credit retry headroom remains under the 1,000 ceiling |

An exact historical `--as-of` request also walks the paginated full-universe
close feed. For 962 companies that adds **33 credits** (`ceil(962 / 30)`), so
the cold baseline becomes **1,008 credits** and is blocked by the runner's
preflight rather than allowed to start.

| Step | Endpoint | Cost (est.) | Notes |
| --- | --- | --- | --- |
| Foreign flow (per highlighted driver) | `/v2/foreign-flow/{symbol}/` | **1 credit** | called only for top driver of a material transition |
| Corporate actions (per highlighted driver) | `/v2/company/corporate-actions/{symbol}/` | **1 credit** | called only when return anomaly detected |
| **Tier-3 per-driver total** | | **≤ 2 credits / driver** | |

Targeted Tier-3 enrichment is additive to the core baseline: one selected
driver costs up to **2 credits** when both foreign flow and corporate actions
are requested. The live snapshot runner does not call these endpoints for the
whole market, and the client blocks any request that would cross its hard
1,000-credit ceiling.

## 3. Observed-vs-estimated

| | Estimated | Observed |
| --- | --- | --- |
| Starting balance | n/a | UNKNOWN (not exposed to the client) |
| Ending balance after full refresh | n/a | UNKNOWN |
| Observed delta | n/a | UNKNOWN |
| Confidence | high for structured screener, daily, index-daily, close, and suspensions costs | n/a |
| Notes | The ledger keeps documented estimates, retry reserves, and observed debit separate | Earlier run recorded 975 requests, 454 cache hits, and 226 documented estimated credits |

## 4. Conclusion

- The Sectors credit model is **endpoint-based, not request-based** (e.g.
  `/v2/close/` is per-page, `/v2/free-float/` is per-100-tickers).
- **Pagination matters for cost.** Use `limit=200` for structured companies
  pages and `limit=30` for the close feed, each matching its current documented
  maximum.
- **Tier-3 enrichment is the safest cost lever** because each call is bounded to
  1–2 credits and is gated by a Tier-1 material transition flag.
- **Balance read is not available programmatically**; the live artifact reports
  `credit_balance: UNAVAILABLE` and keeps documented estimates separate from
  actual account debit.

## 5. UNKNOWN / VERIFY items

- `/v2/companies/` unfiltered-form credit cost (the provider avoids this form)
- `/v2/company/report/{symbol}/` per-call credit cost
- Total credits remaining on the user's account (no programmatic endpoint found)
