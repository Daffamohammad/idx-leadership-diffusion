# Live Sectors Runbook

This runbook covers the credentialed Sectors path. A bounded contract
validation and a market-wide refresh were exercised on 2026-08-28. The
market-wide bundle is reproducible but currently `READY_WITH_GAPS` because
the provider rate-limited part of the per-symbol history batch; the gap is
preserved in the snapshot and diagnostics.

For the current deterministic market-wide workflow, use
[`FULL_LIVE_RUNBOOK.md`](FULL_LIVE_RUNBOOK.md) first. It is the canonical
path for the uncapped `refresh_and_export --full-live` gate and records the
current 962-company / 1,008-credit preflight blocker. The bounded commands
below remain useful for contract diagnostics and must not be presented as
full IDX coverage.

## Before the live run

1. Work from a real Git checkout and confirm the intended branch:

   ```bash
   git status --short --branch
   ```

   Keep unrelated worktree changes intact; live outputs and ledgers are
   separate from source files.

2. Load the credentials from the local environment without writing them to
   source, logs, shell arguments, fixtures, or reports:

   ```bash
   test -n "${SECTORS_API_KEY:-}" && echo "Sectors key present" || echo "Sectors key missing"
   test -n "${TAVILY_API_KEY:-}" && echo "Tavily key present" || echo "Tavily key missing"
   ```

3. Record the account credit balance manually if the Sectors account page
   exposes it. There is no confirmed programmatic balance endpoint.

4. Confirm that these locations are writable and excluded from publication:

   ```text
   data/raw/sectors_validation/
   data/cache/
   data/normalized/
   data/snapshots/
   ```

5. Run the offline suite before spending a credit:

   ```bash
   .venv/bin/pytest -q
   .venv/bin/python -m compileall -q src app scripts
   ```

## Dry-run call plan

The default is non-live and spends no credits:

```bash
.venv/bin/python -m scripts.validate_sectors_live --dry-run --max-pages 1
.venv/bin/python -m scripts.build_market_snapshot --preflight-only
.venv/bin/python -m scripts.plan_sectors_refresh --universe-size 950 --page-size 200
```

The refresh planner estimates HTTP calls, pages, and cache hits. It does not
invent a credit cost.

The snapshot preflight is the paid-run gate. It uses the latest persisted live
universe when available, prices structured screener pages at one credit, and
blocks a baseline above the hard 1,000-credit ceiling before constructing a
live client. Retries reserve again at the client boundary and are stopped when
the same ceiling is reached.

## Minimal credentialed validation

Run exactly one page per core endpoint first:

```bash
.venv/bin/python -m scripts.validate_sectors_live \
  --live \
  --allow-credit-spend \
  --max-pages 1 \
  --as-of YYYY-MM-DD
```

Expected bounded checks:

1. authenticated `companies` response;
2. taxonomy fields on returned companies;
3. one page of the requested market close;
4. an IHSG/benchmark row if it appears in the bounded payload;
5. required-key, type, identifier, granularity, and date validation;
6. sanitized response fixtures;
7. a request ledger;
8. a machine-readable validation report.

Do not mark the benchmark check as passed merely because a close page was
valid. If IHSG is not present in the pages fetched, its status remains
`NOT_FOUND_IN_FETCHED_PAGES`; the separate market-wide runner independently
validated and used the native IHSG history endpoint.

Use `--force-refresh` only when a cached response must be bypassed and the
additional request is intentional. Raising `--max-pages` expands the possible
credit spend and requires a new dry-run review.

## Validate the captured artifacts

Before reusing a sanitized payload as a fixture, confirm:

- [ ] key available only in the process environment;
- [ ] auth works;
- [ ] raw response saved under the private raw-data path;
- [ ] secrets and headers stripped from sanitized fixtures;
- [ ] schema matches or explicitly supersedes fixture assumptions;
- [ ] pagination metadata and an empty terminal page are understood;
- [ ] market date equals the requested date;
- [ ] benchmark date is independently checked;
- [ ] request ledger contains each non-cached request;
- [ ] before/after credits are observed where possible;
- [ ] normalized identifiers and dates validate;
- [ ] no live payload is labeled `SECTORS_FIXTURE` or `PUBLIC_PROTOTYPE`.

## Credit audit

If balances are available, provide both values. Otherwise the command remains
successful and reports `BALANCE UNAVAILABLE`:

```bash
.venv/bin/python -m scripts.audit_sectors_credit \
  --ledger data/raw/sectors_validation/<run>/request_ledger.jsonl \
  --request-category ALL \
  --before-balance <value> \
  --after-balance <value>
```

Never infer an observed credit delta from the documented endpoint cost.

## Price-basis investigation

Start with a known corporate-action window and preserve public raw and adjusted
series separately:

```bash
.venv/bin/python -m scripts.audit_price_basis \
  --ticker BBCA.JK \
  --start 2021-10-01 \
  --end 2021-10-29 \
  --corporate-action-date 2021-10-13 \
  --sectors-mode SECTORS_LIVE \
  --live \
  --allow-credit-spend \
  --max-pages 1
```

The bounded run is expected to leave the benchmark status as
`NOT_FOUND_IN_FETCHED_PAGES` when only one close page is requested; the
market-wide runner separately calls the native IHSG history endpoint.

## Market-wide expansion

Proceed only after the minimal report is reviewed, the date/identifier
contracts match, the benchmark source is resolved, and the call plan is
accepted.

1. Expand security master and taxonomy pagination deliberately.
2. Fetch enough dated close cross-sections for all configured horizons plus
   the required start observation.
3. Fetch a real benchmark history; do not substitute a cross-sectional mean or
   Yahoo series inside a `SECTORS_LIVE` snapshot.
4. Build the eligible universe and inspect exclusion reasons.
5. Write the Sectors snapshot with `provider_mode=SECTORS_LIVE`.
6. Confirm market date, benchmark date, universe/taxonomy/method versions,
   coverage, and per-layer data-quality states in the manifest.

The market-wide command is:

```bash
.venv/bin/python -m scripts.build_market_snapshot \
  --allow-live --allow-credit-spend --max-estimated-credits 1000 \
  --history-workers 1 --with-tavily
```

Run the no-network preflight immediately before it. Do not add an exact
historical `--as-of` on a cold full-universe run unless the preflight returns
`READY`; at the current 962-company universe that path is estimated at 1,008
credits and is intentionally blocked.

Treat it as a second-stage command. Its output is not accepted merely because
the process exits successfully; the validation report and manifest gates still
apply.

## Provider parity

Run parity only when both sources contain true histories for the same tickers
and dates:

```bash
.venv/bin/python -m scripts.compare_providers \
  --sectors-mode SECTORS_LIVE \
  --live \
  --allow-credit-spend \
  --as-of YYYY-MM-DD
```

Review every `UNEXPLAINED`, `MAPPING`, `CORPORATE_ACTION`, and `PRICE_BASIS`
row. Fixture parity proves the pipeline only; it is never a live parity result.

## Failure handling

- `401/403`: stop. Verify the credential outside logs; do not retry in a loop.
- `429`: stop expansion, retain the ledger, and review the account/rate limit.
- contract drift: preserve the sanitized payload, add a failing fixture test,
  then update the normalizer and schema intentionally.
- unexpected date: reject the page; do not coerce it to the requested date.
- missing benchmark: keep the snapshot blocked.
- partial pagination: label coverage partial; do not publish market-wide states.
- suspect corporate action: annotate and block the affected return comparison;
  never silently rewrite prices.

## Rollback and quarantine

After a successful run, export the exact live snapshot and advertise only
that mode to the SPA:

```bash
.venv/bin/python -m scripts.export_snapshot_json \
  --snapshot-id snap_sectors_YYYY-MM-DD
.venv/bin/python -m scripts.build_snapshot_index --provider-mode SECTORS_LIVE
```

Provider selection is explicit, so rollback means selecting
`PUBLIC_PROTOTYPE`, `SECTORS_FIXTURE`, or `DEMO_FIXTURE` and restarting the UI.
Do not relabel a failed live artifact. Move suspect live outputs to a bounded
quarantine directory, preserve the request ledger/report, and leave the last
validated snapshot untouched. No methodology downgrade or historical snapshot
rewrite is required.
