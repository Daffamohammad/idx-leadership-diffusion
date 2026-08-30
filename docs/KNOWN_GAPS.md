# Known Gaps

As of 2026-08-28, the repository is offline-ready and the default suite makes
no network calls. A first live Sectors snapshot was exercised and is labeled
`READY_WITH_GAPS`; unresolved items below remain explicit.

## LIVE-BLOCKED

- **Sectors authentication and schema:** authentication, sanitization, contract
  checks, request ledger, and market-wide ingestion were exercised. The
  provider still rate-limited 295 of 962 per-symbol history requests.
- **Close basis:** raw versus adjusted semantics remain unresolved. See
  `SECTORS_BLOCKERS.md` and `SECTORS_PRICE_BASIS.md`.
- **IHSG source:** the native Sectors `/v2/index-daily/ihsg/` series was used and
  aligned through 2026-08-27; its broader price-basis contract remains open.
- **Observed credits:** the live ledger records 975 requests, 454 cache hits,
  and 226 estimated credits; account balance and actual debit remain
  `BALANCE UNAVAILABLE`.
- **Full-universe pagination and coverage:** 962 company rows, complete
  taxonomy, and zero duplicate rows were observed. The provider now keeps the
  documented pagination boundaries separate: `limit=200` for structured
  company screener pages and `limit=30` for full-universe close pages.
- **Provider parity:** three live close spot-checks matched; market-wide return
  parity and adjusted-price parity remain unmeasured.
- **Live state turnover:** churn, reversals, transition matrices, and durations
  have not been measured on Sectors market-wide history.
- **Enrichment:** free-float historical semantics, structured foreign-flow
  coverage, and corporate-action completeness remain open. The bounded
  `scripts.enrich_tavily_context` command can attach first-party qualitative
  sources for foreign flow, fundamentals, and events without calling Sectors.
  Those sources are shown as `READY_WITH_GAPS` / `CONTEXT ONLY`; they do not
  populate the frozen `ConfirmationEvidence` fields or create numeric
  confirmation metrics. A category with no attached source remains a web
  `DATA GAP`, while the frozen backend contract retains `UNAVAILABLE` for
  absent confirmation fields.

## METHODOLOGY

- Leadership remains a transparent 2D descriptive state based on primary
  excess return and short-versus-medium acceleration. It is not a forecast.
- The 5/20/60 baseline survives constrained offline sensitivity on stability,
  interpretability, churn, and coverage; it was not selected on forward return.
- Group-size-aware diffusion remains provisional. Synthetic group sizes prove
  boundary behavior but cannot establish live IDX calibration. The offline
  grid is in `data/normalized/methodology/group_size_diffusion.json` and
  ships via `scripts/audit_group_size_diffusion.py`.
- Minimum group size 5 is a structural guardrail. Small groups remain
  `UNCONFIRMED` or `FRAGILE` rather than being promoted by a one-name move.
- Materiality is rules-based and threshold-sensitive. A categorical state change
  alone is not material; breadth, relative-strength, or rank corroboration is
  required. The no-look-ahead regression in
  `tests/test_no_lookahead_synthetic.py` locks this property.
- Absolute concentration and signed attribution answer different questions.
  Signed attribution is undefined when its denominator is unstable. The
  negative-group and one-missing-stock cases in
  `tests/test_synthetic_scenarios.py` exercise the boundary.
- Equal-weight remains the core participation view. No cap/free-float weighting
  is silently substituted.
- A deterministic synthetic-market harness
  (`tests/synthetic_market.py`, scenarios A–G) is now the regression wall
  for boundary behaviour. It is not a live calibration; it is a guardrail
  that every methodology change must revisit.

## DATA

- Public prototype taxonomy is non-authoritative and the configured universe is
  not full IDX.
- The legacy 10-name canonical fixture does not cover the 54-name prototype
  universe and is unsuitable as a product demo under the minimum group-size
  rule. It remains a unit-test fixture.
- Historical survivorship/delisting is only partially modeled.
- Public adjusted-price quality is not validated across full IDX.
- Mixed benchmark dates, stale observations, zero eligible names, and missing
  constituents fail or surface explicit denominator/data-gap fields; they are
  not imputed.

## PRODUCT

- The Streamlit product is desktop-first. 1440px and 1280px are the supported
  demo targets; mobile optimization is deliberately limited.
- Demo mode is deterministic and clearly labeled `DEMO FIXTURE`; its values are
  synthetic and must not be quoted as market observations.
- Confirmation panels distinguish quantitative `DATA GAP` from optional
  qualitative Tavily `CONTEXT ONLY` sources. A source link does not imply that
  the selected group has been confirmed.
- Historical map tails and group charts depend on comparable snapshot history;
  incompatible provider/method/universe/taxonomy versions are excluded.
- The UI is an analytical inspection surface, not a trading terminal, portfolio
  optimizer, chatbot, or recommendation engine.

## LOW PRIORITY

- Concurrent snapshot writers are not supported.
- There is no background scheduler or alerting service.
- Fine-grained industry/sub-industry views remain optional because many groups
  are too small for stable diffusion.
- Property-based testing and a formal static type-checker can be added later;
  the current gate uses focused regression tests, `compileall`, and the existing
  project toolchain.
- HTML export is secondary to the deterministic Markdown brief.
