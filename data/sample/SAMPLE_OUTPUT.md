# IDX Leadership Diffusion — Sample Output

> Generated from `tests/fixtures/` (10-ticker subset) via the
> `FixtureProvider` on **2026-07-31** and **2026-08-20**. These dates
> are illustrative; the fixture is a deterministic test bed, not live
> market data.

## Snapshot 1: as-of 2026-07-31

| Group | Leadership | Diffusion | Excess 20D | Breadth Outperforming |
| --- | --- | --- | --- | --- |
| Financials | UNCONFIRMED | UNCONFIRMED | 6.52% | 100% |
| Consumer   | UNCONFIRMED | UNCONFIRMED | 5.89% | 100% |
| Industrial | UNCONFIRMED | UNCONFIRMED | 4.84% | 100% |
| Telecom    | UNCONFIRMED | UNCONFIRMED | -0.79% | 67% |

* `leadership_state` is UNCONFIRMED on the first observation because
  no prior snapshot exists for the acceleration comparison.
* `diffusion_state` is UNCONFIRMED because `breadth_delta` is not
  defined without a previous observation.

## Snapshot 2: as-of 2026-08-20

| Group | Leadership | Diffusion | Excess 20D | Breadth Outperforming | Δ Breadth |
| --- | --- | --- | --- | --- | --- |
| Financials | WEAKENING | STABLE | 5.97% | 100% | 0.0pp |
| Consumer   | UNCONFIRMED | UNCONFIRMED | 5.45% | 100% | 0.0pp |
| Industrial | UNCONFIRMED | UNCONFIRMED | 4.50% | 100% | 0.0pp |
| Telecom    | UNCONFIRMED | UNCONFIRMED | -0.95% | 67% | 0.0pp |

* Financials moved from UNCONFIRMED → WEAKENING: `excess_return_20d`
  is positive (5.97%) but acceleration
  (`excess_5d - excess_60d`) fell below the threshold of 1.0pp.
  The model correctly flags the deceleration without overclaiming.
* Other groups remain UNCONFIRMED because the 5D / 60D horizons are
  not available in the fixture (only ~67 trading days of data).

## Change digest (2026-07-31 → 2026-08-20)

```text
new_leaders:      []
lost_leadership:  []
upgrades:         []
downgrades:       []
broadening:       []
narrowing:        []
stable:           [Financials, Consumer, Industrial, Telecom]
```

The current thresholds (±10pp breadth delta, ±1.5pp excess delta) treat
these as `STABLE`. This is correct under the provisional rules.

## Quality

```json
{
  "status": "READY",
  "coverage_pct": 100.0,
  "requested_securities": 10,
  "loaded_securities": 10,
  "usable_securities": 10,
  "failed_securities": 0,
  "benchmark_latest_date": "2026-08-20",
  "latest_common_date": "2026-05-20",
  "duplicate_ticker_date_rows": 0,
  "invalid_prices": 0,
  "stale": false
}
```

## How to reproduce

```bash
git clone <this repo>
cd idx-leadership-diffusion
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

python -m scripts.build_snapshot --provider fixture --as-of 2026-08-20
```

The snapshot is persisted under `data/snapshots/snap_2026-08-20/`
with `manifest.json`, `groups.parquet`, `transitions.parquet`,
`change_digest.json`, and `quality.json`.

## What this output is NOT

* Not a forecast. Not a signal. Not a ranking for trading.
* Not a backtest of the threshold choices.
* Not a guarantee that the same numbers will appear for the live IDX
  on these dates.
* Not authoritative Sectors taxonomy. See `docs/KNOWN_GAPS.md`.
