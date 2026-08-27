# Known Gaps

As of 2026-08-28, the repository is offline-ready and the default suite makes
no network calls. No live Sectors validation is claimed.

## LIVE-BLOCKED

- **Sectors authentication and schema:** no `SECTORS_API_KEY` was available.
  The minimal validator, sanitization path, contract checks, and request ledger
  are offline-tested only.
- **Close basis:** raw versus adjusted semantics remain unresolved. See
  `SECTORS_BLOCKERS.md` and `SECTORS_PRICE_BASIS.md`.
- **IHSG source:** an authoritative Sectors benchmark history and its date/basis
  contract remain unverified. A public series or cross-sectional mean must not
  be substituted inside `SECTORS_LIVE`.
- **Observed credits:** endpoint calls/pages can be planned, but account balance
  and observed deltas remain `BALANCE UNAVAILABLE` until recorded.
- **Full-universe pagination and coverage:** live page counts, duplicates, null
  taxonomy, and terminal-page behavior are not proven.
- **Provider parity:** Sectors-shaped fixtures validate the comparison pipeline;
  they are not real public-vs-Sectors parity results.
- **Live state turnover:** churn, reversals, transition matrices, and durations
  have not been measured on Sectors market-wide history.
- **Enrichment:** free-float historical semantics, foreign-flow coverage, and
  corporate-action completeness remain live-blocked. Fundamentals and foreign
  flow stay `UNAVAILABLE` in the intelligence contract.

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
- Confirmation panels intentionally show
  `DATA GAP — SECTORS LIVE NOT CONNECTED`.
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

