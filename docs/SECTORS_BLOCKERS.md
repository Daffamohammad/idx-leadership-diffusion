# Sectors Blocker Register

These items require credentialed Sectors evidence. Offline fixtures can prove
normalization and failure behavior, but cannot resolve the empirical question.

## Close adjustment basis

- **Issue:** `/v2/close/` does not document whether `close` is raw,
  split-adjusted, dividend-adjusted, or total-return adjusted.
- **Why it matters:** every return, excess-return, leadership, diffusion, and
  concentration result depends on consistent price semantics.
- **Current evidence:** documentation is silent; offline fixture behavior is
  labeled synthetic.
- **Live test required:** `scripts.audit_price_basis` across a confirmed split
  and corporate-action payload.
- **Expected resolution:** classify the basis, version the feature method, and
  retain the other price series as a diagnostic.
- **Affected module:** Sectors normalizer, returns, parity, methodology.

## Benchmark identity and history

- **Issue:** an authoritative, sufficiently long IHSG history is not yet
  validated from the live contract.
- **Why it matters:** a close-page mean or public-source fallback would corrupt
  a `SECTORS_LIVE` excess-return claim.
- **Current evidence:** the bounded validator can only report whether an IHSG
  row appears in fetched pages.
- **Live test required:** identify the official endpoint/symbol, fetch all
  horizons, and verify market-date alignment.
- **Expected resolution:** one canonical Sectors benchmark series with an
  explicit identifier and price basis.
- **Affected module:** Sectors provider, relative strength, live snapshot.

## Full-universe pagination

- **Issue:** live total count, terminal-page behavior, duplicate symbols, and
  pagination consistency remain unobserved.
- **Why it matters:** partial pages bias coverage and breadth.
- **Current evidence:** multi-page and empty-page behavior is exercised with
  Sectors-shaped fixtures only.
- **Live test required:** bounded expansion with page count, unique identifiers,
  empty terminal page, and ledger reconciliation.
- **Expected resolution:** exact rows/pages plus an explicit partial-coverage
  failure state.
- **Affected module:** Sectors client, contract validator, universe builder.

## Observed credit economics

- **Issue:** account balance and the actual cost of endpoints with undocumented
  pricing are unknown.
- **Why it matters:** a market-wide history can consume materially more calls
  than a single close cross-section.
- **Current evidence:** call/page/cache planning exists; no cost is inferred.
- **Live test required:** manual before/after balances reconciled to the request
  ledger.
- **Expected resolution:** observed deltas by request category or an explicit
  `BALANCE UNAVAILABLE` record.
- **Affected module:** request ledger, credit audit, refresh policy.

## Taxonomy nulls and identifier stability

- **Issue:** live coverage and stability of sector, sub-sector, industry, and
  sub-industry fields are unknown.
- **Why it matters:** taxonomy changes can make snapshots incomparable or
  create artificial group transitions.
- **Current evidence:** missing, null, extra, and duplicate fixture cases are
  covered offline.
- **Live test required:** profile nulls/duplicates and compare taxonomy versions
  across two live dates.
- **Expected resolution:** authoritative primary group level and a versioned
  mapping artifact.
- **Affected module:** security master, taxonomy, snapshot comparability.

## Free-float historical semantics

- **Issue:** point-in-time availability, effective date, and restatement
  behavior of free float are unverified.
- **Why it matters:** current values must not be applied retrospectively.
- **Current evidence:** endpoint shape and units are documentation-derived;
  equal-weight remains the core participation view.
- **Live test required:** capture values and source dates across at least two
  observations, including a known ownership change if available.
- **Expected resolution:** keep or reject free float as a separately versioned
  magnitude view.
- **Affected module:** enrichment, weighting diagnostics, provenance.

## Foreign-flow coverage

- **Issue:** ticker coverage, missing-day semantics, and date alignment are
  unknown market-wide.
- **Why it matters:** confirmation cannot be inferred from sparse or stale flow.
- **Current evidence:** response normalization is fixture-tested; the UI says
  `DATA GAP — SECTORS LIVE NOT CONNECTED`.
- **Live test required:** a small, pre-declared sample across liquid and less
  liquid names with missingness reported.
- **Expected resolution:** an optional confirmation field or continued data gap;
  never a composite score.
- **Affected module:** confirmation contract, group explorer.

## Corporate-action completeness

- **Issue:** event coverage and dates have not been reconciled to close-series
  discontinuities.
- **Why it matters:** a single split can resemble extreme leadership and high
  concentration.
- **Current evidence:** the fixture harness includes corporate-action metadata.
- **Live test required:** compare event payloads with known IDX actions and
  return discontinuities.
- **Expected resolution:** annotation/blocking rules, not silent price edits.
- **Affected module:** price-basis audit, data quality, evidence.

## Live provider parity and turnover

- **Issue:** public-vs-Sectors parity and state churn on real market-wide history
  have not been measured.
- **Why it matters:** offline stability cannot establish live source parity or
  live state persistence.
- **Current evidence:** deterministic fixture and synthetic harnesses validate
  algorithms only. The group-size diffusion grid
  (`scripts/audit_group_size_diffusion.py`) covers the offline floor; the
  synthetic-market harness (`tests/synthetic_market.py`, scenarios A–G) covers
  leadership, diffusion, concentration, contradiction, and persistence
  boundaries.
- **Live test required:** aligned history, parity classifications, leadership and
  diffusion transition matrices, reversal rates, and duration statistics.
- **Expected resolution:** retain the simpler baseline unless live structural
  evidence supports a versioned change.
- **Affected module:** parity, state-turnover audit, methodology sensitivity.

