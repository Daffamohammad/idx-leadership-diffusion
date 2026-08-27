# Sectors Credit Audit

> **Approach:** credit costs were taken **directly from the official Sectors v2 docs**
> (the per-endpoint prose states "Costs N API credit(s)"). No live call was issued
> during this pass because no API key was available in the environment.
>
> **Balance inspection:** no programmatic balance endpoint was found in the docs.
> The Sectors Insider upgrade page is gated; balance is visible only to the
> authenticated user inside `sectors.app`. A direct probe is queued for the next
> pass when a key is available.

## 1. Per-endpoint credit costs (DOCUMENTED)

| Endpoint | Cost per call | Source |
| --- | --- | --- |
| `/v2/close/` | **1 credit per page** | docs.sectors.app "Daily Full-Universe Close" |
| `/v2/free-float/` | **1 credit per 100 companies returned, rounded up** | docs.sectors.app "Free Float Market Analysis" |
| `/v2/foreign-flow/{symbol}/` | **1 credit** | docs.sectors.app "Daily Net Foreign Inflow" |
| `/v2/company/corporate-actions/{symbol}/` | **1 credit** | docs.sectors.app "Corporate Actions" |
| `/v2/suspensions/` | **1 credit** | docs.sectors.app "Stock Suspensions" |
| `/v2/companies/` | `UNKNOWN / VERIFY` | not stated on the page |
| `/v2/company/report/{symbol}/` | `UNKNOWN / VERIFY` | not stated on the page |

## 2. Refresh budget (estimated from docs)

A standard **market-wide refresh** for one as-of date consists of:

| Step | Endpoint | Cost (est.) | Notes |
| --- | --- | --- | --- |
| Security master + taxonomy | `/v2/companies/` | UNKNOWN — assumed ≤ 1/page × 32 pages ≈ 32 | will be recorded in ledger on first run |
| Full-universe close | `/v2/close/` | **~32 credits** (942 tickers / 30 per page) | 1 trading day |
| Free float | `/v2/free-float/` | **~10 credits** (1 per 100 of ~942) | one-time daily cache |
| Suspensions | `/v2/suspensions/` | **~28 credits** (556 / 20 per page) | incremental |
| **Tier-1 daily total** | | **~102 credits + companies** | dominated by close + suspensions |

| Step | Endpoint | Cost (est.) | Notes |
| --- | --- | --- | --- |
| Foreign flow (per highlighted driver) | `/v2/foreign-flow/{symbol}/` | **1 credit** | called only for top driver of a material transition |
| Corporate actions (per highlighted driver) | `/v2/company/corporate-actions/{symbol}/` | **1 credit** | called only when return anomaly detected |
| **Tier-3 per-driver total** | | **≤ 2 credits / driver** | |

A typical end-to-end refresh that includes both Tier 1 + Tier 3 for **one**
highlighted group (top 3 drivers) is **~108 credits + the `companies` page cost**.

## 3. Observed-vs-estimated

| | Estimated | Observed |
| --- | --- | --- |
| Starting balance | n/a | UNKNOWN (key not present) |
| Ending balance after full refresh | n/a | UNKNOWN |
| Observed delta | n/a | UNKNOWN |
| Confidence | low for `companies` (no doc'd cost) | n/a |
| Notes | A first-run probe with a key will populate the ledger and the audit table | First refresh must be guarded with `--dry-run` for safety |

## 4. Conclusion

- The Sectors credit model is **endpoint-based, not request-based** (e.g.
  `/v2/close/` is per-page, `/v2/free-float/` is per-100-tickers).
- **Pagination matters for cost.** Always use the maximum `limit=30` to minimize
  total pages.
- **Tier-3 enrichment is the safest cost lever** because each call is bounded to
  1–2 credits and is gated by a Tier-1 material transition flag.
- **Balance read is not available programmatically**; we must rely on the
  `RequestLedger.actual_credit_cost` field once observed and trust the documented
  per-call cost until then.

## 5. UNKNOWN / VERIFY items

- `/v2/companies/` per-call credit cost
- `/v2/company/report/{symbol}/` per-call credit cost
- Total credits remaining on the user's account (no programmatic endpoint found)
