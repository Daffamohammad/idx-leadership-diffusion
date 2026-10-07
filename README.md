# The Diffusion

> A Sectors-powered market-intelligence workspace that shows which Indonesian
> equity sectors lead, whether leadership is broadening, and which constituents
> drive the signal.

## Submission build · 8 October 2026

**Problem.** An index-level move can hide sharply different sector and stock
leadership. The Diffusion makes those differences inspectable with
source-bound prices, explicit contributor counts, and replayable calculations.

**Audience.** Market-intelligence reviewers and equity researchers who need to
inspect sector signals down to their contributing stocks and data limitations.

The primary workflow is `/sectors`: rank 11 sectors by 20-session excess return,
compare 60-session excess return with relative momentum, replay daily or weekly
observations, and inspect all 66 selected constituents. The tracked universe contains six
stocks per sector and was selected from a frozen 2 October 2026 market source.
It is retrospective, not historical point-in-time membership. Returns use raw
Sectors closes against native Sectors IHSG closes. Listed splits, rights issues,
bonuses, dividends, and other mechanical changes exclude a stock from the
affected window; missing prices stay missing, and signals require at least five
contributors. Each replay comparison uses the same eligible names at both
dates, while eligibility can change between date pairs.

The `/sectors` page reads released, hash-validated assets and makes no provider
calls when opened. `/sources` documents coverage and recording provenance; the earlier `/recorded-sample` URL redirects there. Broader IDX pages remain supporting context. The latest supported view has eleven 20D rankings and nine eligible 60D map points. Genuine stock YTD readings are dated separately; no sector currently meets the five-contributor YTD floor. The immutable
release, universe boundary, reproduction steps, rollback target, and current
verification evidence are documented in
[`docs/submission-release/README.md`](docs/submission-release/README.md).

## Offline reproduction

Resolve the active release ID from `app/web/public/releases/active.json`, then
rebuild and independently verify the primary analysis using only released
assets. No credentials or paid requests are required:

```bash
RELEASE_ID="$(.venv/bin/python -c 'import json; print(json.load(open("app/web/public/releases/active.json"))["active"]["release_id"])')"
RELEASE_DIR="app/web/public/releases/$RELEASE_ID"
.venv/bin/python scripts/build_sectors_analysis.py \
  --sample "$RELEASE_DIR/assets/context/sectors_recorded_sample.json" \
  --selection-market "$RELEASE_DIR/assets/context/sectors_selection_market.json" \
  --ytd-baseline "$RELEASE_DIR/assets/context/sectors_ytd_baseline.json" \
  --out /tmp/sectors_signal_analysis.json
.venv/bin/python scripts/verify_sectors_analysis_oracle.py \
  --sample "$RELEASE_DIR/assets/context/sectors_recorded_sample.json" \
  --analysis /tmp/sectors_signal_analysis.json \
  --ytd-baseline "$RELEASE_DIR/assets/context/sectors_ytd_baseline.json"
```

For the full offline regression suite and frontend checks, see
[`docs/submission-release/README.md`](docs/submission-release/README.md).

**This project is an analytical market-intelligence prototype for
research and educational purposes. It does not provide investment
advice or personalized recommendations.**

## Sections

- [Submission build](#submission-build--8-october-2026)
- [Offline reproduction](#offline-reproduction)
- [Supporting implementation and research tools](#supporting-implementation-and-research-tools)
- [Earlier broad-universe product model](#earlier-broad-universe-product-model-historical)
- [Prototype mode](#prototype-mode)
- [Demo mode](#demo-mode)
- [Earlier Sectors-wide integration audit](#earlier-sectors-wide-integration-audit)
- [Earlier broad-universe live refresh](#earlier-broad-universe-live-refresh)
- [Foreign-flow discovery and sample calculation](#foreign-flow-discovery-and-sample-calculation)
- [Architecture](#architecture)
- [Methodology](#method-overview)
- [Known limitations](#known-limitations)

## Supporting implementation and research tools

The repository also contains earlier broad-universe prototypes, snapshot
builders, a Streamlit inspection surface, and qualitative context integrations.
Those remain available as supporting research tools; they are not the primary
submission workflow. Shared calculation code and offline synthetic-market
tests provide additional regression coverage.

## Earlier broad-universe product model (historical)

The earlier product model separated evidence by what a reviewer could reasonably trust:

| Product lane | Sections | Contract |
| --- | --- | --- |
| Real snapshot | Overview, Sector heatmap, Leadership Map, Groups, Ticker Analysis, What Changed | Full accessible listing registry plus bounded persisted market observations; the analytical history sample remains bounded and has no comparable prior. |
| Official release | Overview, Methodology | Official IDX July 2026 daily investor-type table, parsed and reconciled across 23 trading days into market-level net foreign flow. |
| Source-backed sample | Foreign Flow | Real reported observations from a bounded top-list sample; not a full-universe signal. |
| Static research lens | Konglo Map, Themes Map, Group Explorer for those taxonomies, Themes Explorer | Analyst-defined membership configuration; aggregate metrics may reuse the current snapshot, but the taxonomy is not official IDX data. |
| Static context | Research Events and optional web-context panels | Persisted descriptive context; never used to create or change quantitative signals. |

This table describes a historical prototype design. The active submission workflow and evidence boundary are described above and in the current release notes.

## Supporting implementation inventory

| Capability | Status | Evidence |
| --- | --- | --- |
| Provider abstraction (YFinance / Sectors v2 / Fixture) | shipped | `src/idx_leadership/providers/*` |
| Live-gated `SectorsClient` (auth, retry, pagination, cache, ledger) | shipped | `src/idx_leadership/providers/sectors_client.py` |
| Live-gated `SectorsProvider` (security master, taxonomy, full-universe close, foreign flow, free float, corporate actions) | shipped | `src/idx_leadership/providers/sectors.py` |
| Methodology v3 (leadership, diffusion, concentration, persistence, contradictions, invalidation) | shipped | `src/idx_leadership/{signals,features,analytics}/*` |
| Snapshot / manifest / quality / comparability | shipped | `src/idx_leadership/data/*` |
| Streamlit product (Overview, Leadership Map, Group Explorer, Method / Quality) | shipped | `app/streamlit_app.py` |
| Story-mode UI (deterministic, no LLM) | shipped | `app/story_mode.py` |
| Synthetic-market harness (7 scenarios, 16 golden tests) | shipped | `tests/synthetic_market.py`, `tests/test_synthetic_scenarios.py` |
| Group-size diffusion grid (3, 4, 5, 7, 10, 20, 40) | shipped | `scripts/audit_group_size_diffusion.py` |
| No-look-ahead regression on synthetic history | shipped | `tests/test_no_lookahead_synthetic.py` |
| Live-key validation command (`validate_sectors_live`) | shipped, dry-run by default | `scripts/validate_sectors_live.py` |
| Price-basis investigation (`audit_price_basis --as-of`) | shipped; live semantics remain `UNKNOWN / VERIFY` | `scripts/audit_price_basis.py` |
| Sectors credit audit (`audit_sectors_credit`) | shipped, `BALANCE UNAVAILABLE` without observed balances | `scripts/audit_sectors_credit.py` |
| Provider parity (`compare_providers`) | shipped, live 3-ticker spot-check exercised | `scripts/compare_providers.py` |
| Refresh budget dry-run (`plan_sectors_refresh`) | shipped | `scripts/plan_sectors_refresh.py` |
| Markdown market brief export (`export_market_brief`) | shipped | `scripts/export_market_brief.py` |
| State turnover audit (`audit_state_turnover`) | shipped, JSON+CSV+MD | `scripts/audit_state_turnover.py` |
| Offline test suite | shipped; live availability not required | `.venv/bin/pytest -q` |
| React SPA (Figma design port), snapshot-driven | shipped | `app/web/`, `scripts/export_snapshot_json.py`, `scripts/build_snapshot_index.py` |

## React SPA (Figma design port)

A Vite/React/TypeScript port of the Figma design prototype lives in
`app/web/`. Both the Streamlit UI and SPA are read-only product surfaces
that consume JSON/parquet exported from the snapshot bundle; neither opens
provider connections while rendering.

### Pages

| Route | Page | Data source |
| --- | --- | --- |
| `/` | redirects to `/sectors` | primary Sectors workflow |
| `/sectors` | `SectorsDashboard` | immutable Sectors sample, frozen selection source, and signal-analysis assets |
| `/overview` | `MarketOverview` | real Sector heatmap plus official IDX market-level release, bounded sample, and static context sections |
| `/what-changed` | `WhatChanged` | real current snapshot; prior comparison is shown only when compatible history exists |
| `/map` | `LeadershipMap` | YTD excess-return rotation mapping and table; 20D/60D momentum remain diagnostics and null YTD values stay `Not available` |
| `/maps/konglo` | `TaxonomyMapPage` | static analyst-defined membership lens with current-snapshot aggregates |
| `/maps/themes` | `TaxonomyMapPage` | static analyst-defined membership lens with current-snapshot aggregates |
| `/explorer` | `GroupExplorer` | real `features` joined to `security_master` per `group_id` |
| `/themes` | `ThemesExplorer` | static analyst-defined theme lens with current-snapshot aggregates |
| `/groups` | `MasterGroupTable` | real group cross-section from the snapshot |
| `/methodology` | `Methodology` | real `manifest`, `quality`, coverage, warnings, plus static method cards |

The map uses an explicitly labeled current-breadth view when the snapshot has
no comparable prior. Breadth-delta diffusion and trajectory views remain
unavailable until compatible history is persisted; no prior or delta is
fabricated. Prototype snapshots may include persisted per-group breadth
history, while the canonical live snapshot currently does not. Foreign flow
Per-ticker/group foreign-flow confirmation and fundamentals remain explicit data
gaps and never become fabricated neutral values; the official IDX market-level
release is shown in its own evidence lane. Unsupported views render a one-line
reason rather than a blank chart.

### Run it

```bash
# 1. Build or refresh a snapshot. The live path is explicitly opt-in.
.venv/bin/python -m scripts.build_market_snapshot \
  --allow-live --allow-credit-spend --max-symbols 250 \
  --max-http-requests 400 --max-estimated-credits 1000 \
  --with-tavily --history-workers 1

# 2. Export the live snapshot and make it the SPA default.
.venv/bin/python -m scripts.export_snapshot_json \
  --snapshot-id snap_sectors_YYYY-MM-DD
.venv/bin/python -m scripts.build_snapshot_index --provider-mode SECTORS_LIVE

# 3. Install + start the SPA.
cd app/web
npm install
npm run dev   # http://127.0.0.1:5174 (when launched with --port 5174)
```

The output of step 2 lands in `app/web/public/snapshots/` and is served
as static assets at `/snapshots/<id>.json`. The SPA auto-discovers the
latest advertised snapshot via `/snapshots/index.json`; the provider-mode
filter prevents a newer public prototype from silently replacing a live
Sectors view. Override with `VITE_SNAPSHOT_ID` when intentionally reviewing
another payload.

### What is real vs static or bounded

Real (driven by the snapshot bundle):

- group-level leadership / diffusion state, 20D / 60D excess returns,
  breadth, concentration
- leadership transitions (`prev` / `current`)
- per-group constituent table built from `features.parquet` joined to
  `security_master` on `group_id`
- sidebar as-of, data-status chip, snapshot id in the header
- Data Status and Provenance tables on the Methodology page
- official IDX July 2026 investor-type release: 23 daily market-level rows,
  reconciled net foreign totals, and source provenance

Static or bounded layers (explicitly labeled, never presented as live signals):

- per-group breadth / performance time series (available when a snapshot
  contains persisted comparable observations)
- leadership trail lines on the map (same reason)
- per-ticker/group foreign-flow confirmation (not emitted by the official
  market-level release)
- foreign-flow top-list sample with source provenance
- Konglo and Themes analyst-defined membership lenses
- qualitative research events and web context

Fundamentals remain unavailable. Unsupported quantitative views render a
one-line reason rather than a fabricated neutral value.

An existing snapshot can receive a bounded, first-party Tavily research
context pass without rebuilding or calling Sectors:

```bash
.venv/bin/python -m scripts.enrich_tavily_context \
  --snapshot-id snap_sectors_2026-08-27 \
  --allow-live --allow-credit-spend --with-crawl
```

This searches three official-source categories and optionally crawls a small
IDX path set. The result is stored in `tavily_context.json` and displayed as
`READY WITH GAPS` / `CONTEXT ONLY`. It is qualitative provenance only: the
pass does not create per-ticker metrics or change leadership, breadth,
diffusion, or confirmation values. The command has an explicit request and
The You.com web-search and research APIs are wired as a parallel bounded
context layer.  Run a single command to attach both search evidence and a
multi-step research synthesis to an existing snapshot:

```bash
.venv/bin/python -m scripts.enrich_you_context \
  --snapshot-id snap_sectors_2026-08-27 \
  --allow-live --allow-credit-spend --with-research --max-credit-budget 10
```

The command never calls the Sectors provider and never creates per-ticker
metrics.  The result is stored in `you_context.json` and rendered on the
Methodology page alongside the Tavily panel; both layers carry
`quantitative_use: false` and remain qualitative provenance only.

## Foreign-flow discovery and sample calculation

The official IDX Digital Statistics page is the quantitative source for the
market-level investor release shown on Overview and Methodology:

- [IDX statistics index](https://www.idx.co.id/id/data-pasar/laporan-statistik/statistik/)
  lists the dated Daily Statistics releases.
- [July 2026 daily trading by type of investor](https://www.idx.co.id/id/data-pasar/laporan-statistik/digital-statistic/monthly/equity-trading-by-investor/table-daily-trading-by-type-of-investor?filter=eyJ5ZWFyIjoiMjAyNiIsIm1vbnRoIjoiNyIsInF1YXJ0ZXIiOjAsInR5cGUiOiJtb250aGx5In0%3D)
  renders the 23 trading-day rows used by the product.

`src/idx_leadership/providers/idx_statistics.py` is the deterministic reducer
for the two directly retrieved first-party HTML tables, aligns dates, derives
`domestic_to_foreign - foreign_to_domestic`, and fails closed when totals do
not reconcile. The page is dynamic, but its completed cached release is not
downgraded; dynamic-page discovery and search snippets remain separate and
non-quantitative. The offline-safe
refresh command is:

```bash
.venv/bin/python -m scripts.refresh_idx_statistics \
  --year 2026 --month 7 \
  --html-file /path/to/saved/official-idx-table.html \
  --output /path/to/idx_investor_trading_2026-07.json
```

The checked-in web artifact is
`app/web/public/idx/idx_investor_trading_2026-07.json`. Direct CLI retrieval
may be blocked by IDX anti-bot controls in a local environment; the parser is
therefore tested offline and the artifact retains the exact official URL and
reconciliation metadata. Search agents are used for discovery only and are
not a numeric extraction path.

The optional LlamaParse PDF lane now follows the complete staged path:
search-agent discovery, bounded official-index crawl/retrieval, local PDF
verification, LlamaParse upload, and deterministic reduction to the Daily
Statistics cards. Search/crawl text remains discovery-only and is never used
as a quantitative value. Install the optional SDK and run the bounded command
only after reviewing both provider acknowledgements; see
[`docs/IDX_STATISTICS_SOURCE.md`](docs/IDX_STATISTICS_SOURCE.md) for the exact
command and the 20,000-credit client-side ceiling.

The repository also contains a bounded foreign-flow methodology harness. The
discovery record in `data/fixtures/foreign_flow_discovery.json` documents the
official release and the two dated secondary reports used for a small company
sample. No stable full-universe daily per-ticker ownership-flow feed has been
established.

The numeric input is intentionally manual and auditable:
`data/fixtures/foreign_flow_sample.csv` contains two market-wide observations
and published top-buy/top-sell company rows. Company rows remain net-only;
missing buy/sell components are never inferred. The calculator uses pandas to
validate the input, preserve reported market net values, flag rounding
variance in rounded market components, and map only tickers present in the
persisted security master:

```bash
.venv/bin/python scripts/calculate_foreign_flow_sample.py
```

The deterministic result is written to
`data/derived/foreign_flow_sample.json` with `READY_WITH_GAPS` status. It is
reported descriptive sample evidence only: IDNFinancials/secondary rows keep
their source values and provenance but are emitted with `quantitative_use=false`.
The sample is explicitly disabled from leadership, diffusion, and confirmation
calculations. No network request is made and the Sectors API is not called by
this command.

## Prototype mode

The prototype mode uses public market data via `yfinance` for the
prototype universe declared in `config/universe.yaml`. The
classification metadata in that file is **prototype metadata** and
is not authoritative Sectors taxonomy. Snapshots produced in this
mode are labelled `PUBLIC PROTOTYPE` in the UI.

```bash
.venv/bin/python -m scripts.build_snapshot --provider public --as-of 2026-08-20
streamlit run app/streamlit_app.py
```

The public prototype uses Yahoo Finance through the provider boundary. It is
kept as a separate fallback for reproducible return, breadth, concentration,
leadership, and diffusion comparisons; it is not a full IDX universe and its
local taxonomy is not authoritative. To refresh it and feed the React preview:

```bash
.venv/bin/python -m scripts.build_snapshot --provider public --as-of 2026-08-20
.venv/bin/python -m scripts.export_snapshot_json --latest
.venv/bin/python -m scripts.build_snapshot_index
```

## Demo mode

The Streamlit source selector always lists the demo fixture first
(`data/fixtures/demo_market.json`). The demo fixture tells a coherent
Oil & Gas / Coal / Healthcare / Basic Materials story on every run;
it is labelled `DEMO FIXTURE` everywhere it appears and is the
recommended artefact for screenshots, demos, and the sidebar
markdown export. Demo values are deterministic synthetic data and
must not be quoted as market observations.

## Earlier Sectors-wide integration audit

This table records the broad-universe provider path exercised in August 2026.
It is supporting tooling evidence and does not describe the active 66-stock
submission release.

| Surface | Status | Reference |
| --- | --- | --- |
| Client + capability protocols | shipped | `src/idx_leadership/providers/sectors_*.py` |
| `SECTORS_LIVE` mode | exercised; explicit key and credit-spend gates remain | `src/idx_leadership/providers/factory.py` |
| Normalizers (taxonomy, close, free float, flow, corporate actions) | shipped, fixture-tested | `src/idx_leadership/providers/sectors_normalizers.py` |
| Contract drift tests | shipped, fixture-only | `tests/test_provider_contracts.py` |
| Sectors-shaped fixtures | shipped | `data/fixtures/sectors/` |
| Live market-wide snapshot | exercised; 962-row accessible listing registry, 500-name bounded history sample, `READY_WITH_GAPS` at 99.2% requested-history coverage, 265 policy-eligible | `scripts/build_market_snapshot.py` |
| Live parity | exercised; 3/3 close spot-checks matched | `scripts/compare_providers.py` |
| Live credit audit | shipped, command ready, `BALANCE UNAVAILABLE` without balances | `scripts/audit_sectors_credit.py` |
| Live price-basis audit | still open; raw/adjusted semantics remain `UNKNOWN / VERIFY` | `scripts/audit_price_basis.py` |
| Blocker register | shipped | `docs/SECTORS_BLOCKERS.md` |
| Live runbook | shipped | `docs/LIVE_SECTORS_RUNBOOK.md` |

The blocker register remains useful for unresolved provider questions, but
the live bundle and its sanitized validation artifacts are now the evidence
for the exercised path. Do not treat demo or public prototype payloads as
live market observations.

## Earlier broad-universe live refresh

The commands below belong to the earlier broad-universe research workflow.
They are not required to run or reproduce the active submission workflow;
use the offline release instructions above for that build.

```bash
# 1. Confirm keys are present (env only; never log them).
test -n "${SECTORS_API_KEY:-}" && echo "Sectors key present" || echo "Sectors key missing"
test -n "${TAVILY_API_KEY:-}" && echo "Tavily key present" || echo "Tavily key missing"

# 2. Run the offline suite to confirm a clean baseline.
.venv/bin/pytest -q

# 3. Dry-run the bounded validator (no HTTP).
.venv/bin/python -m scripts.validate_sectors_live --dry-run --as-of YYYY-MM-DD

# 4. Bounded credentialed validation (one page per endpoint).
.venv/bin/python -m scripts.validate_sectors_live \
  --live --allow-credit-spend --max-pages 1 --as-of YYYY-MM-DD

# 5. Optional price-basis audit on a known corporate action.
.venv/bin/python -m scripts.audit_price_basis \
  --ticker BBCA.JK --start 2021-10-01 --end 2021-10-29 \
  --corporate-action-date 2021-10-13 \
  --sectors-mode SECTORS_LIVE --live --allow-credit-spend \
  --as-of 2021-10-29

# 6. Bounded live snapshot. The full accessible master is listed, while
#    daily history is limited to 250 selected names and 400 attempts.
.venv/bin/python -m scripts.build_market_snapshot \
  --allow-live --allow-credit-spend --max-symbols 250 \
  --max-http-requests 400 --max-estimated-credits 1000 \
  --history-workers 1 --with-tavily

# 7. Export only the live snapshot for the SPA's default index.
.venv/bin/python -m scripts.export_snapshot_json --snapshot-id snap_sectors_YYYY-MM-DD
.venv/bin/python -m scripts.build_snapshot_index --provider-mode SECTORS_LIVE
```

The runbook (`docs/LIVE_SECTORS_RUNBOOK.md`) covers the same flow with
failure handling, rollback, and quarantine.

## Prototype quick start (historical)

```bash
git clone <this repo>
cd idx-leadership-diffusion
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

# Build a snapshot from the public-data prototype
.venv/bin/python -m scripts.build_snapshot --provider public --as-of 2026-08-20

# Run the test suite (offline; live availability is not required)
.venv/bin/pytest -q

# Launch the exploratory UI
streamlit run app/streamlit_app.py
```

## Historical prototype scope (August 2026)

- Live Sectors discovery produced 962 unique company rows in the exercised
  2026-08-27 snapshot. The browser payload now exposes all 962 rows through a
  dedicated listing registry, while market features use a disclosed 500-name
  bounded sample with 265 policy-eligible securities and 496/500 usable
  requested histories (99.2%).
- 5D / 20D / 60D horizons.
- Equal-weight group aggregation.
- 4-state provisional leadership model + UNCONFIRMED.
- Methodology v2 group-size-aware diffusion: `BROADENING_FIRM`,
  `BROADENING_FRAGILE`, `STABLE`, `NARROWING_FRAGILE`,
  `NARROWING_FIRM`, and `UNCONFIRMED` (with a v1 compatibility projection).
- Concentration v2 with capped absolute shares, signed attribution shares,
  and HHI.
- Materiality classifier with explicit priority order.
- Offline pytest suite; all tests use fixtures, no network needed.

## Architecture

```
Provider  →  Raw cache  →  Normalization  →  Canonical data
        →  Feature engine  →  Group aggregation
        →  Leadership / Diffusion  →  Transitions
        →  Evidence objects  →  Snapshot / Manifest  →  UI
```

See `docs/ARCHITECTURE.md` for the full description.

## Prototype data

The prototype mode uses public market data via `yfinance` for the
prototype universe declared in `config/universe.yaml`. The
classification metadata in that file is **prototype metadata** and
is not authoritative Sectors taxonomy.

The Sectors v2 client and provider implement the documented core,
taxonomy, free-float, flow, suspension, and corporate-action
capabilities. Live HTTP is explicitly opt-in (`--allow-live`) and
requires `SECTORS_API_KEY`.

For test runs and offline iteration, use the bundled `FixtureProvider`
which reads from `tests/fixtures/`:

```bash
python -m scripts.build_snapshot --provider fixture --as-of 2026-08-20
```

## Method overview

- **Returns:** `(P[d] / P[d-h] - 1) * 100` per security at 5/20/60D.
- **Excess return:** `return_h - benchmark_return_h` (benchmark = IHSG).
- **Breadth:** % constituents with positive / outperforming / improving
  return. Denominators are explicit (`usable_constituents` /
  `total_constituents`).
- **Diffusion state:** methodology v2 uses breadth delta plus a
  group-size constituent floor to distinguish firm versus fragile
  broadening/narrowing. The legacy three-state value is retained as a
  compatibility projection.
- **Leadership state:** `LEADING` / `IMPROVING` / `LAGGING` /
  `WEAKENING` based on a 2D classification of
  `(excess_return_20d, acceleration)`. Acceleration = `excess_5d -
  excess_60d`. Default threshold `1.0pp`.
- **Concentration:** v2 absolute-move decomposition with `top1`,
  `top3`, `top5`, signed attribution shares, and HHI. Shares are
  explicitly bounded and carry a convention label.
- **Transitions:** explicit categorical diffs; materiality classifier
  with documented priority.

See `docs/METHODOLOGY.md` for the full specification.

## Data limitations

- The 962-row live registry is the provider-accessible universe for this
  snapshot; it is not a claim that every IDX instrument or historical listing
  outside that provider feed is represented.
- Equal-weight only; no market-cap or free-float weighting.
- Live Sectors history is intentionally partial when the provider rate-limits
  a request batch. The current snapshot is labeled `READY_WITH_GAPS`, not
  silently filled or downgraded to demo data.
- The official IDX investor-type release is integrated for market-level net
  foreign flow. Per-ticker/group foreign-flow confirmation, broker activity,
  fundamentals, and news metrics remain unavailable. Optional Tavily sources
  are context only and are not a substitute for normalized observations.
- Sectors close adjustment semantics remain `UNKNOWN / VERIFY`; the live
  path surfaces the raw-close caveat rather than claiming adjusted prices.

See `docs/KNOWN_GAPS.md` for the full register.

## Supporting live-provider operating model

The provider abstraction is the seam. `SectorsProvider` is implemented
against the Sectors v2 HTTP contract and refuses live calls by default.
When credentials are available:

- `config/providers.yaml` flipped to `enabled: true` for `sectors`
- run the bounded validator, then
  `scripts/build_market_snapshot.py --allow-live --allow-credit-spend`
  (bounded by default: 250 history symbols / 400 HTTP attempts)
- run the live provider-parity spot-check before using the snapshot
- Snapshots remain readable forever; no migration of historical
  data is required

See `docs/SECTORS_INTEGRATION_PLAN.md` and
`docs/NEXT_ITERATION.md` (P0 list).

## Tests

```bash
pytest
```

The suite covers:

- Returns (exact math, missing data, as-of resolution, invalid prices)
- Relative performance (benchmark alignment, missing benchmark)
- Breadth (numerator/denominator, zero eligible, threshold edges)
- Concentration (equal shares, dominant constituent, zero group move)
- States (all 4 leadership quadrants + UNCONFIRMED, diffusion boundary
  thresholds)
- Transitions (all buckets + no previous)
- Aggregation (group construction, ranking, history)
- Snapshot safety (atomic write, manifest, no look-ahead)
- Provider normalization (fixture + Sectors v2 contract tests)

All default tests are offline: 0 network, 0 credentials.

## Repository structure

```text
idx-leadership-diffusion/
├── app/                      Streamlit UI (read-only)
├── config/                   universe, methodology, providers
├── data/                     raw, normalized, snapshots, cache, fixtures
├── docs/                     ARCHITECTURE, METHODOLOGY, DATA_CONTRACTS,
│                             DECISION_LOG, KNOWN_GAPS,
│                             SECTORS_INTEGRATION_PLAN, NEXT_ITERATION
├── scripts/                  CLI entry points
├── src/idx_leadership/       the package
│   ├── providers/            YFinance, Sectors v2, Fixture
│   ├── models/               Pydantic schemas
│   ├── data/                 cache, snapshots, quality, manifests
│   ├── features/             returns, relative strength, breadth, concentration
│   ├── aggregation/          group snapshots + ranking
│   ├── signals/              leadership, diffusion, transitions, change digest
│   ├── evidence/             evidence objects
│   ├── pipeline.py           end-to-end orchestrator
│   └── utils/                config, logging, dates, errors
└── tests/                    Offline pytest suite + fixtures
```

## Disclaimer

This project is an analytical market-intelligence prototype for
research and educational purposes. It does not provide investment
advice or personalized recommendations.
