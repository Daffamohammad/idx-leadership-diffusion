# Sectors Refresh Budget (v2)

> **Status:** The Frontier Pass #2 budget uses the current Sectors v2
> per-endpoint cost model and is backed by the first live request ledger from
> 2026-08-28.
> The live artifact records 975 requests, 454 cache hits, and 226 estimated
> credits; account balance and actual debit remain unavailable.

## 1. Tiered refresh model

| Tier | Goal | Endpoints | Cost (doc'd) |
| --- | --- | --- | --- |
| 1 — Core market | latest close, structured security master/taxonomy, per-symbol history, IHSG, suspensions | `/v2/companies/`, `/v2/close/`, `/v2/daily/{symbol}/`, `/v2/index-daily/ihsg/`, `/v2/suspensions/` | 1/page (structured companies and close), 1/call (daily, IHSG, suspensions) |
| 2 — Selected enrichment | subsector report, fundamental screener, company report | `/v2/company/report/{symbol}/` | UNKNOWN |
| 3 — Targeted constituent | foreign flow, corporate actions, broker summary | `/v2/foreign-flow/{symbol}/`, `/v2/company/corporate-actions/{symbol}/` | 1 each |

## 2. Refresh strategies (per the v2 docs)

| Strategy | Endpoints | Estimated cost |
| --- | --- | --- |
| Latest-date live snapshot (cold, 962 symbols) | structured companies × 2, latest close page, daily history × 962, IHSG, suspensions | **975 baseline credits** |
| Exact historical `--as-of` (cold, 962 symbols) | latest close, full close × 33 pages, structured companies × 10 pages, daily history × 962, IHSG, suspensions | **1,008 baseline credits; preflight blocks it** |
| Targeted group drilldown | existing snapshot + selected Tier 3 calls | 1 credit per foreign-flow or corporate-action call |
| Foreign-flow enrichment (Tier 3, top driver per material transition) | foreign-flow | 1 credit / call |
| Fundamental confirmation (Tier 2, on demand) | company-report | UNKNOWN |

The totals are still estimates because:
* The live runner uses only documented structured screener queries
  (`where=...`), priced at 1 credit per page. The unfiltered screener form is
  not used because its price is not stated.
* `company-report` cost is `UNKNOWN / VERIFY`.
* A live balance read is not available; we cannot measure
  observed delta.

## 3. Observed credit economics

`scripts/credit_audit.py` reads the `RequestLedger` and produces
`data/normalized/credit_audit.json` with:

```text
{
  "by_endpoint": {"/v2/close/": {"requests": 32, "cache_hits": 0, ...}, ...},
  "by_refresh_kind": {"core_close": {...}, ...},
  "totals": {"requests": ..., "rows": ..., "estimated_credit_cost": ...}
}
```

When the ledger is empty (for an offline run), only the `by_refresh_kind`
buckets appear; `by_endpoint` is empty and `totals` is zero. This is
intentional — the rollup must not invent numbers (D012). The first live
snapshot ledger is preserved separately under `data/raw/sectors_live/`.

## 4. Tier separation in code

The `SectorsProvider` implements Tier 1 + Tier 3 capabilities. The
Tier 2 `company-report` capability is researched but not
auto-applied. The engine never auto-calls Tier 3 for the whole
market (D011); it is invoked only on demand when a transition is
flagged `material` (per `transitions._classify_materiality`).

## 5. Rate-limit response

`SectorsClient` serializes the live history calls at a conservative interval
and retries on `429` with bounded exponential/backoff delays. The Sectors
`RATE_LIMIT_EXCEEDED` body is typed
(`{"error": "RATE_LIMIT_EXCEEDED", "message": "..."}`) and the
client retries on it. The first live run recorded 429 responses in the
history diagnostics; the unit test
`test_sectors_client.py::test_retry_on_429` exercises the path with
a fake transport.

## 6. Cost-protection guardrails

* `SectorsClient` and `SectorsProvider` refuse live HTTP unless
  `allow_live=True`. The factory passes `allow_live=False` by
  default; the CLI scripts pass `--allow-live` to opt in.
* Every Sectors call flows through the `RequestLedger`; documented estimates
  and retry-inclusive budget reserves are recorded separately.
* The live snapshot runner performs a network-free preflight and defaults to a
  hard `--max-estimated-credits 1000` ceiling. Every HTTP attempt reserves
  before leaving the process, so retries cannot silently cross the ceiling.
