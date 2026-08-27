# Sectors Refresh Budget (v2)

> **Status:** The Frontier Pass #2 budget is the same per-endpoint
> cost as Frontier Pass #1 (per the Sectors v2 docs), now wrapped
> behind a `scripts/credit_audit.py` rollup that consumes the
> `RequestLedger`. Live observed values land in
> `data/normalized/credit_audit.json` once a key is available.
>
> **Live Sectors key is not present in this environment.** The
> rollup is exercised against an empty ledger (no entries) and
> reports structure only; no numbers are invented.

## 1. Tiered refresh model (unchanged)

| Tier | Goal | Endpoints | Cost (doc'd) |
| --- | --- | --- | --- |
| 1 — Core market | full-universe close, security master, taxonomy, IHSG, free-float, suspensions | `/v2/companies/`, `/v2/close/`, `/v2/free-float/`, `/v2/suspensions/` | 1/page (close), 1/100 co (free-float), 1 (suspensions), UNKNOWN (companies) |
| 2 — Selected enrichment | subsector report, fundamental screener, company report | `/v2/company/report/{symbol}/` | UNKNOWN |
| 3 — Targeted constituent | foreign flow, corporate actions, broker summary | `/v2/foreign-flow/{symbol}/`, `/v2/company/corporate-actions/{symbol}/` | 1 each |

## 2. Refresh strategies (per the v2 docs)

| Strategy | Endpoints | Estimated cost |
| --- | --- | --- |
| Core daily refresh (Tier 1) | companies, close, suspensions, free-float | ~70 credits + UNKNOWN (companies) |
| Weekly history extension (Tier 1) | close (re-pull last 30d for transitions) | +30 × 1/page = 30 credits |
| Single-group drilldown (Tier 1 + Tier 3 top-3) | one snapshot + 3 × 1 (foreign) + 3 × 1 (corporate) | ~70 + 6 credits |
| Foreign-flow enrichment (Tier 3, top driver per material transition) | foreign-flow | 1 credit / call |
| Fundamental confirmation (Tier 2, on demand) | company-report | UNKNOWN |

The totals are still estimates because:
* `companies` cost is `UNKNOWN / VERIFY` (see D020 in
  `DECISION_LOG.md`).
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

When the ledger is empty (no live runs), only the `by_refresh_kind`
buckets appear; `by_endpoint` is empty and `totals` is zero. This is
intentional — the rollup must not invent numbers (D012).

## 4. Tier separation in code

The `SectorsProvider` implements Tier 1 + Tier 3 capabilities. The
Tier 2 `company-report` capability is researched but not
auto-applied. The engine never auto-calls Tier 3 for the whole
market (D011); it is invoked only on demand when a transition is
flagged `material` (per `transitions._classify_materiality`).

## 5. Rate-limit response

`SectorsClient` retries on `429` with linear backoff (default 1.5s,
max 2 retries). The Sectors `RATE_LIMIT_EXCEEDED` body is typed
(`{"error": "RATE_LIMIT_EXCEEDED", "message": "..."}`) and the
client retries on it. Without a live key we cannot measure
observed RTT or actual retry behavior, but the unit test
`test_sectors_client.py::test_retry_on_429` exercises the path with
a fake transport.

## 6. Cost-protection guardrails (unchanged)

* `SectorsClient` and `SectorsProvider` refuse live HTTP unless
  `allow_live=True`. The factory passes `allow_live=False` by
  default; the CLI scripts pass `--allow-live` to opt in.
* Every Sectors call flows through the `RequestLedger`; per-call
  `estimated_credit_cost` is recorded. `scripts/credit_audit.py`
  rolls the ledger up; future passes will add a daily balance
  read when Sectors exposes one.
