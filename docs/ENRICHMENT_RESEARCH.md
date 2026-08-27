# Enrichment Research (Free Float, Fundamentals, Foreign Flow, Broker)

> **Status:** research + capability wiring only. **No ML / LLM /
> blending into a composite score** is added. Each layer is
> investigated independently with the documented Sectors contract.

## 1. Free float

| Question | Answer (from docs) | Decision |
| --- | --- | --- |
| Endpoint | `GET /v2/free-float/` | wired into `SectorsProvider.get_free_float` |
| Definition | `share_percentage` of the `Public` entry in the major-shareholders list | documented; treated as authoritative for this pass |
| Coverage | IDX-wide (the docs example lists 942 companies) | expected ~98% |
| Cost | 1 credit / 100 companies | see `SECTORS_REFRESH_BUDGET.md` |
| Use here | separate **magnitude weighting** channel (D011) | kept out of the default equal-weight group return |

**Decision:** keep equal-weight as the **default group return**
(because the brief §26 says "do not remove equal-weight analysis")
and expose free-float as a parallel magnitude view. The engine does
not collapse them.

## 2. Fundamentals (company reports)

| Question | Answer | Decision |
| --- | --- | --- |
| Endpoint | `GET /v2/company/report/{symbol}/` | researched; not auto-applied |
| What's inside | `overview`, `valuation` (pe, pb, ps, pcf, peg, peer averages, intrinsic_value), `future` (analyst forecasts, growth), `financials` (eps, historical_eps) | — |
| Cost | UNKNOWN / VERIFY | — |
| Group-level signal | dominated by price leadership on current data | not auto-integrated |
| Use here | Tier 2 enrichment on demand (drilldown only) | not in the default snapshot |

**Decision:** fundamentals are available but not auto-applied. A
group-level fundamental confirmation would need (a) per-company
calls, which is expensive at 942 companies; (b) a defensible
group-level signal (e.g. "% of constituents with positive
`yoy_quarter_revenue_growth`") which the engine does not yet
implement.

## 3. Foreign flow

| Question | Answer (from docs) | Decision |
| --- | --- | --- |
| Endpoint | `GET /v2/foreign-flow/{symbol}/` | wired into `SectorsProvider.get_foreign_flow` |
| Date window | up to **90 days** | enforced by the client (`max_rows=90` cap) |
| Sign convention | positive = net foreign buying | documented |
| Closed-market identity | domestic = `-net_foreign_inflow` | noted in `SECTORS_API_AUDIT.md` |
| Cost | **1 credit** per call | per docs |
| Use here | Tier 3 only — invoked when a transition is `material`, for the top driver of the highlighted group | implemented |

**Decision:** targeted only. The closed-market identity means a
market-wide flow rollup is fully derivable from per-symbol flow, so
a future pass could expose a market-wide flow if the credit budget
permits.

## 4. Broker activity

| Endpoint | Status |
| --- | --- |
| `/v2/indonesia/brokers/broker-activity-by-code` | researched; not wired |
| `/v2/indonesia/brokers/broker-activity-top` | researched; not wired |
| `/v2/indonesia/brokers/broker-registry` | researched; not wired |
| `/v2/indonesia/brokers/broker-summary-by-symbol` | researched; not wired |
| `/v2/indonesia/brokers/broker-summary-top` | researched; not wired |

**Decision:** broker cohorts and broker accumulation/distribution
are deferred. The brief §43 requires a real lift above foreign flow
to justify integration; on the fixture and per the documented
Sectors payload, broker data is richer but **redundant** with
foreign flow at the group level. Future passes can add
`SectorsProvider.get_broker_summary(symbol)` if the drilldown
requires it.

## 5. Corporate actions

| Question | Answer | Decision |
| --- | --- | --- |
| Endpoint | `GET /v2/company/corporate-actions/{symbol}/` | wired into `SectorsProvider.get_corporate_actions` |
| What's inside | `agm[]`, `dividend[]`, `stock_split[]`, `right_issue`, `warrant`, `bonus`, `upcoming_dividend` | documented |
| Use here | corporate-action guardrail; flag affected rows with `caveat` | implemented (D018) |

**Decision:** guardrail only. The Sectors price is treated as raw
(G011) until a corporate-action audit proves the basis. The
guardrail **annotates** rather than edits.

## 6. Suspensions

Wired through `SectorsProvider.get_suspensions`. The eligibility
filter uses it (rule 4 in `UNIVERSE_ELIGIBILITY.md`). No
silently-zero fallback (D012).

## 7. What was deliberately NOT added

| Item | Reason |
| --- | --- |
| Composite conviction score (e.g. "Smart Money Index") | violates D004 (no opaque conviction score) |
| LLM commentary | violates §59 — future narration consumes `GroupEvidence` objects |
| ML / clustering / HMM | violates §84 |
| Mining / commodities enrichment | brief §10 marks optional; no product justification in this pass |
| Macro / FX dashboard | outside the product scope (§58) |
| Real-time alerts | outside the product scope (§58) |
