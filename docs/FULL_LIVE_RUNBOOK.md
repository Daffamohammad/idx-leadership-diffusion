# Full-live Sectors Runbook

Updated 2026-08-31. This is the canonical operator path for producing a
market-wide `SECTORS_LIVE` snapshot and browser export. It is intentionally
separate from the bounded validation path documented in
`LIVE_SECTORS_RUNBOOK.md`.

## Current evidence

The latest persisted Sectors snapshot is deliberately still partial:

| Field | Evidence |
| --- | --- |
| Snapshot | `data/snapshots/snap_sectors_2026-08-27/` |
| Provider mode | `SECTORS_LIVE` |
| Coverage | 500 used of 962 discovered; prefix sample |
| Quality | `READY_WITH_GAPS`; four securities below the 60-observation history floor |
| Comparable prior | Unavailable; no compatible second Sectors snapshot |
| Price basis | Native `close`; corporate-action adjustment semantics remain `UNKNOWN / VERIFY` |

The network-free full-live preflight currently returns `BLOCKED`: the
uncapped plan is 1,008 baseline credits (10 structured company pages, one
latest-date probe, 33 full close pages, 962 daily history calls, one native
IHSG call, and one suspensions call) against the hard 1,000-credit ceiling.
A later credentialed attempt was also stopped by provider transport failure;
it did not create a new snapshot, browser export, or index update.

## Safe preflight

These commands do not make paid Sectors requests:

```bash
.venv/bin/python -m scripts.refresh_and_export --full-live
.venv/bin/python -m scripts.build_market_snapshot --preflight-only
```

The first command returns a structured blocker report when the two explicit
operator acknowledgements are absent. The second command reports the current
universe size, page plan, credit reserve, and headroom without opening HTTP.

Do not bypass a `BLOCKED` result by lowering a displayed number or by
relabeling the existing 500-row snapshot as full coverage. A bounded run is a
separate diagnostic and remains visibly partial.

## Credentialed operator run

Only after the preflight is reviewed and the provider budget is known to fit
the hard ceiling, an operator may run:

```bash
.venv/bin/python -m scripts.refresh_and_export \
  --full-live \
  --as-of YYYY-MM-DD \
  --max-estimated-credits 1000 \
  --allow-live \
  --allow-credit-spend
```

`--full-live` removes the default 500-symbol and five-page caps. The API key
must exist only in the local environment (`SECTORS_API_KEY`); it must never
appear in a command transcript, source file, fixture, log, screenshot, or
commit. Do not pass `--with-tavily` unless its separate budget and scope have
also been approved.

## Mandatory gates

The strict child-builder gate runs before `SnapshotWriter`, export, or index
updates. Every failure returns a machine-readable `BLOCKED` report with a
status, cause, and next action.

| Gate | Required condition |
| --- | --- |
| Universe and pagination | Security-master and as-of close pagination are `COMPLETE`; no silent page cap |
| History | Every requested common-equity has the configured minimum history; failed, empty, duplicate, or insufficient rows block the run |
| Price basis | History, market close, and benchmark declare the same effective basis; no relabeling of a different basis |
| Benchmark | Native Sectors IHSG history is present, sourced from Sectors, and reaches the snapshot date |
| Enrichment | Security-master taxonomy has no missing required fields |
| Credit | Conservative baseline and retry reservations remain within the 1,000-credit client ceiling |

When a gate fails, request-ledger evidence may be retained for diagnosis, but
the snapshot directory, aggregate manifest, browser JSON export, and
`app/web/public/snapshots/index.json` are not changed.

## Comparable prior policy

The current snapshot may show levels, but it must not show a measured change
set until a second snapshot is compatible on provider mode, universe
contract, price basis, benchmark, methodology/version fields, and eligible
ticker set. A yfinance snapshot is never substituted as a comparable prior
for Sectors data. Until that second compatible Sectors snapshot exists, the
UI must keep `Change comparison unavailable` and the diffusion state
unconfirmed.

## Post-success checks

After a successful run, inspect the generated `coverage.json`, `quality.json`,
`data_warnings.json`, `comparability.json`, and `report.md`. Confirm that the
manifest and browser payload agree on provider mode, as-of date, price basis,
universe count, and data-quality status. The wrapper then exports the exact
snapshot and rebuilds the live browser index.

Launch and browser QA are local only for this handoff:

```text
http://127.0.0.1:5174/
```

A passing local test/build or browser smoke test does not prove provider
entitlement, credit debit, deployment, or a successful full-live refresh.
