# Public-vs-Sectors Provider Parity Report

> **Status:** scaffolding only. **A live Sectors API key is not
> available in this environment**, so a true public-vs-Sectors
> comparison could not be run. This document records the parity
> harness, the classification rules, and what the next pass must do
> when a key is available.
>
> The harness is implemented in
> `tests/test_parity_public_sectors.py` and is exercised against a
> stub Sectors response. The harness classifies differences into
> the seven buckets below; any future live run will populate the
> observed-deltas table automatically.

## 1. Parity harness design

For each ticker in a controlled overlap subset (e.g. the 10 Financials
names in the prototype), compute:

```text
delta_pct(t, h) = |public_adjusted_close(t, h) - sectors_close(t, h)|
                                    / public_adjusted_close(t, h) × 100
```

for horizons `h ∈ {5, 20, 60}` and aggregate:

* mean absolute delta
* max delta
* fraction of (ticker, date) pairs where `delta_pct > 0.5`
* fraction of pairs where `delta_pct > 2.0`

## 2. Difference classification

Each row is classified into one of:

| Bucket | Trigger |
| --- | --- |
| expected source difference | `delta_pct < 0.1` (rounding only) |
| price-basis difference | `0.1 ≤ delta_pct < 2.0` and persistent across horizons |
| date alignment difference | row appears on one side only on a small set of days |
| ticker mapping issue | symbol mismatch (e.g. `BBCA` vs `BBCA.JK`) |
| corporate action | one side has an obvious split/dividend adjustment the other lacks |
| provider defect | one side returns clearly out-of-range values |
| unknown | none of the above; flagged for manual review |

## 3. Live-run requirements

A live Sectors call is required to populate observed numbers. The
harness will:

1. Pull a fixture 10-ticker overlap from the public source.
2. Call `SectorsClient(...).paginate("/v2/close/", {"date": ...})` for
   the same 10 tickers and date range.
3. Compute the four aggregates above per horizon.
4. Write the resulting CSV to `data/normalized/parity_<as_of>.csv`.
5. Append a summary to `docs/PROVIDER_PARITY_REPORT.md` (a CI bot can
   do this automatically).

## 4. Stub-run evidence (this pass)

The `test_parity_no_diff_when_prices_match` test exercises the
harness with identical inputs and expects a 0.0pp delta; the
`test_parity_detects_basis_difference` test injects a 2% basis
difference and expects the harness to detect it. Both pass.

```text
$ pytest tests/test_parity_public_sectors.py -v
3 passed in 0.01s
```

## 5. What the next pass must do

1. Set `SECTORS_API_KEY` in `.env`.
2. Run `python -m scripts.compare_providers --as-of 2026-08-20` (to
   be created in the next pass; this pass ships only the test
   harness).
3. Read the resulting CSV; the `price-basis` bucket is the most
   important signal: a persistent ~2% difference is consistent with
   the Sectors `close` being **raw** while yfinance is
   **split-adjusted** (see G011 in `KNOWN_GAPS.md`).
4. If a corporate-action divergence surfaces, the engine should
   promote the v2 concentration/leadership pipeline to use
   `SectorsProvider.get_corporate_actions(symbol)` to **annotate**
   the row (per the brief §44), not silently edit the price.

## 6. Hypothesised outcomes (until live)

Based on the docs:

* **Date alignment** — Sectors `/v2/close/` defaults to the most
  recent trading day; both providers are expected to agree to the
  day. *UNKNOWN / VERIFY*.
* **Ticker mapping** — Sectors returns symbols *without* `.JK` in
  the JSON; the engine normalizer appends `.JK` (`_to_symbol`). If
  yfinance ever returns `BBCA` without `.JK`, the same normalization
  must be applied there.
* **Price basis** — Sectors `close` is **raw** in the documented
  examples; yfinance `Adj Close` is split/dividend-adjusted. **The
  expected difference is the cumulative dividend yield of the
  horizon (e.g. ~1–2% for 20D in normal Indonesian banking
  names).**
