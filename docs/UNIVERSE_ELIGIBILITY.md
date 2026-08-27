# Universe Eligibility

> **Status:** design + implementation shipped. Live numbers pending a
> real Sectors key; the eligibility module is exercised against a stub
> in `tests/test_market_universe.py`.

## 1. Eligibility rules

The market-wide candidate universe is filtered by the rules below.
Each rule produces a single `exclusion_reason` for transparency. The
order in the implementation is the same as the table — the first
triggering rule wins.

| # | Rule | Field checked | Default | Exclusion reason |
| --- | --- | --- | --- | --- |
| 1 | listing board must be in eligible set | `listing_board` | `("Main", "Development", "Acceleration")` | `listing_board` |
| 2 | taxonomy available | `sector`, `sub_sector` | non-null | `no_taxonomy` |
| 3 | sufficient history | `observed_days ≥ min_history_days` | `60` | `insufficient_history` |
| 4 | not recently suspended | `get_suspensions` window | `stale_trading_days × 2` lookback | `recently_suspended` |
| 5 | not stale-priced | `latest_trade_date ≤ as_of − stale_trading_days` | `30` | `stale_price` |

`EligibilityConfig` exposes all thresholds so future passes can
recalibrate without code changes.

## 2. Where the rules live

- `src/idx_leadership/providers/market_universe.py` — the
  `build_market_universe` function. Pure: it consumes a
  `SecurityMasterProvider` + `PriceCrossSectionProvider` +
  optional `EventProvider`. No vendor SDK in the call path.
- `tests/test_market_universe.py` — three tests covering the basic
  flow, the summary counter, and the suspension rule.

## 3. Outputs

`build_market_universe` returns a DataFrame with one row per
candidate ticker and these columns:

```text
ticker, sector, sub_sector, industry, sub_industry, listing_board,
observed_days, latest_trade_date, latest_close, has_history, eligible,
exclusion_reason
```

`eligibility_summary(df)` collapses it to:

```text
{
  "total": int,
  "eligible": int,
  "excluded": int,
  "by_reason": {"<reason>": <count>, …}
}
```

## 4. Behavioural expectations (real IDX, post-pass estimate)

| Reason | Expected share |
| --- | --- |
| `listing_board` | small (only tickers not on Main/Development/Acceleration) |
| `no_taxonomy` | < 1 % of the 942 listed (per Sectors docs example) |
| `insufficient_history` | newly-listed tickers; small |
| `recently_suspended` | ~5–10 in any 60-day window (per Sectors suspension count) |
| `stale_price` | delisted or halted names; small |

These are estimates based on the Sectors example counts (942 listed,
556 historical suspensions). The next pass will record the **real**
shares in this file.

## 5. Why equal-weight universe, not liquidity-filtered

The brief (§26) is explicit: equal-weight is for **participation**,
not for magnitude. The eligibility filter produces the **participation
universe**; a separate **magnitude universe** (liquidity-filtered) is a
future pass, not this one.
