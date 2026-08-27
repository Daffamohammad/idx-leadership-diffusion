# Sectors Price-Basis Investigation

> **Scope:** Determine whether the Sectors `/v2/close/` `close`
> field represents **raw close**, **corporate-action-adjusted close**,
> **total-return-adjusted price**, or **unknown**.
>
> **Live Sectors API key is not available in this environment**
> (per `FRONTIER_PASS_2_AUDIT.md` Gate 1). The empirical leg of the
> investigation is BLOCKED. This document records the methodology and
> what is currently known vs. UNKNOWN.

## 1. Documentation search

Searched `https://docs.sectors.app` for the following terms on
2026-08-27:

| Term | Endpoint | Result |
| --- | --- | --- |
| `close` | `/v2/close/` | described as *"daily closing price for every IDX ticker on a single trading day"*. No explicit statement of adjustment basis. |
| `adjusted_close` | (none) | **not in the documented Sectors v2 API surface**. |
| `split-adjusted` | (none) | not mentioned. |
| `dividend-adjusted` | (none) | not mentioned. |
| `total return` | (none) | not mentioned. |
| `unadjusted` | (none) | not mentioned. |

**Documentation result:** `UNSPECIFIED` — the docs do not state the
adjustment basis. The phrase *"daily closing price"* is ambiguous
and cannot be inferred to mean adjusted or unadjusted.

## 2. Code-side hints in the Sectors payload

The example payload for `/v2/close/`:

```json
{
  "symbol": "AADI.JK",
  "date": "2025-05-02",
  "close": 7150
}
```

contains only the field name `close`. There is **no accompanying
`adjusted_close` field**, which is a common pattern in adjusted
endpoints (yfinance, FRED, Tiingo all expose a separate
`Adj Close`). This absence is consistent with **raw close**, but it
is not a proof — adjusted endpoints also sometimes only return a
single field.

The `/v2/company/report/{symbol}/` endpoint includes
`all_time_price.ytd_low`, `52_w_low`, `90_d_high`, etc., which are
*point-in-time* statistics. Whether these are computed on a
split-adjusted basis is **also UNSPECIFIED**.

## 3. Empirical investigation

The empirical leg requires:

1. Identify an Indonesian ticker with a known recent split.
2. Pull the Sectors `close` series across the split date.
3. Compare to the corporate-action record from
   `GET /v2/company/corporate-actions/{symbol}/`.
4. If the ratio of pre-split to post-split prices equals the
   `split_ratio`, **CONFIRMED RAW CLOSE**.
5. If the ratio is exactly 1.0, **CONFIRMED ADJUSTED CLOSE**.
6. Otherwise, classify by the magnitude of the ratio deviation.

| Ticker candidate | Event date | Action |
| --- | --- | --- |
| BBCA.JK | 2021-10-13 | stock split, ratio 5:1 (per Sectors docs example) |
| BMRI.JK | TBD | investigate |
| TLKM.JK | TBD | investigate |

**Status:** **BLOCKED** — no live key. The script to run this audit
will land as `scripts/audit_close_basis.py` (queued; see
`FRONTIER_PASS_2_AUDIT.md`).

## 4. Defensive defaults (until resolved)

The engine's behaviour while this is unresolved:

| Layer | Default | Why |
| --- | --- | --- |
| `SectorsProvider.get_full_universe_close` | `close` and `adjusted_close` are duplicated to the **raw** value. | Avoid claiming adjustment that is not documented. |
| `compute_excess_returns` | uses `adjusted_close` column. | Same value as `close` until basis is confirmed. |
| `SectorsProvider.get_corporate_actions` | exposed; `GroupEvidence.data_gaps` mentions "Sectors `close` basis UNKNOWN". | Honest documentation in the evidence object. |
| `GroupSnapshot.relative_strength_level` | computed from current `adjusted_close` only. | No silent editing. |

The duplication is the simplest correct behaviour: the canonical
column contract is preserved and downstream code does not need to
branch on provider. If a future pass proves the basis is adjusted,
the `close` → `adjusted_close` mapping is removed in a single
one-line change and a new `method_version: methodology-v3` is
created (D017).

## 5. Conclusion

| Statement | Status |
| --- | --- |
| Sectors `close` is the **raw** close | **LIKELY — MEDIUM CONFIDENCE** (no `adjusted_close` field; the docs example is sparse but unadjusted) |
| Sectors `close` is **split-adjusted** | UNLIKELY — would normally be accompanied by an `adjusted_close` field |
| Sectors `close` is **dividend-adjusted / total return** | UNLIKELY — would be explicitly named |
| Sectors `close` is the official IDX close | UNKNOWN |

**Empirical proof is BLOCKED until a live key is available.**

## 6. Revisit

* The next pass with a key should run
  `scripts/audit_close_basis.py` on BBCA.JK across the
  2021-10-13 split.
* The Sectors API contract may also change in future versions;
  re-audit annually or when `/v2/close/` payload changes.
