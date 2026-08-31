# IDX Leadership Diffusion

> A market-wide intelligence system that detects not only where
> leadership is moving across Indonesian equities, but whether that
> leadership is broadening, concentrating, or deteriorating beneath
> the index surface.

This repository contains both an offline-safe implementation and a
credentialed live Sectors path. The live path has been exercised against
the IDX universe and produces reproducible, versioned snapshots with
coverage, provenance, rate-limit, and data-gap metadata. Tavily is wired as
an optional qualitative context layer; it never supplies quantitative market
data.

The hackathon product is intentionally hybrid rather than pretending to be a
complete production terminal: the market-signal lane is backed by a persisted
real snapshot, the official IDX investor release is a real market-level lane,
foreign flow per company remains a bounded source-backed sample, and Konglo,
Themes, and research context are clearly presented as static or analyst-defined
research layers. The current section-by-section contract is documented in
[`docs/HYBRID_PRODUCT_MODEL.md`](docs/HYBRID_PRODUCT_MODEL.md).
The official IDX source and parser boundary are documented in
[`docs/IDX_STATISTICS_SOURCE.md`](docs/IDX_STATISTICS_SOURCE.md).
The taxonomy constituent and YTD rotation contract is documented in
[`docs/TAXONOMY_ROTATION_RUNBOOK.md`](docs/TAXONOMY_ROTATION_RUNBOOK.md).

**This project is an analytical market-intelligence prototype for
research and educational purposes. It does not provide investment
advice or personalized recommendations.**

## Sections

- [What works now](#what-works-now)
- [Hybrid product model](#hybrid-product-model)
- [Prototype mode](#prototype-mode)
- [Demo mode](#demo-mode)
- [Sectors integration status](#sectors-integration-status)
- [Live Sectors + Tavily refresh](#live-sectors--tavily-refresh)
- [Foreign-flow discovery and sample calculation](#foreign-flow-discovery-and-sample-calculation)
- [Architecture](#architecture)
- [Methodology](#method-overview)
- [Known limitations](#known-limitations)

## What this is

A clean Python 3.10+ package that:

1. fetches public market data (yfinance) for a prototype IDX universe,
2. normalizes to canonical schemas (Pydantic),
3. computes per-security features (returns, excess returns),
4. aggregates to groups (equal-weight), breadth, and concentration,
5. classifies leadership and group-size-aware diffusion states (provisional, parameter-driven),
6. detects transitions and material change,
7. persists durable point-in-time snapshots with provenance,
8. exposes a thin Streamlit UI for inspection,
9. ships a deterministic synthetic-market harness (`tests/synthetic_market.py`,
   scenarios A–G) and a group-size diffusion grid
 (`scripts/audit_group_size_diffusion.py`) as offline guardrails.

## Hybrid product model

The product separates evidence by what a reviewer can reasonably trust in the
current build:

| Product lane | Sections | Contract |
| --- | --- | --- |
| Real snapshot | Overview, Sector heatmap, Leadership Map, Groups, Ticker Analysis, What Changed | Persisted market observations and explicit coverage metadata; the current snapshot remains partial and has no comparable prior. |
| Official release | Overview, Methodology | Official IDX July 2026 daily investor-type table, parsed and reconciled across 23 trading days into market-level net foreign flow. |
| Source-backed sample | Foreign Flow | Real reported observations from a bounded top-list sample; not a full-universe signal. |
| Static research lens | Konglo Map, Themes Map, Group Explorer for those taxonomies, Themes Explorer | Analyst-defined membership configuration; aggregate metrics may reuse the current snapshot, but the taxonomy is not official IDX data. |
| Static context | Research Events and optional web-context panels | Persisted descriptive context; never used to create or change quantitative signals. |

This is a deliberate hackathon delivery choice. A repository-local rubric does
not require full IDX coverage or production deployment; the external event
rules remain the final authority. The UI labels each lane so a static research
prototype is not mistaken for live data.

## What works now

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
| `/` | `PublicHome` | marketing copy (no data dependency) |
| `/overview` | `MarketOverview` | real Sector heatmap plus official IDX market-level release, bounded sample, and static context sections |
| `/what-changed` | `WhatChanged` | real current snapshot; prior comparison is shown only when compatible history exists |
| `/map` | `LeadershipMap` | YTD excess-return rotation mapping and table; 20D/60D momentum remain diagnostics and null YTD values stay `Data gap` |
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
  --allow-live --allow-credit-spend --max-estimated-credits 1000 \
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

Fundamentals remain a data gap. Unsupported quantitative views render a
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

`src/idx_leadership/providers/idx_statistics.py` parses the two released HTML
tables, aligns dates, derives `domestic sells to foreign − foreign sells to
domestic`, and fails closed when totals do not reconcile. The offline-safe
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
sample evidence only and is explicitly disabled from leadership, diffusion,
and confirmation calculations. No network request is made and the Sectors
API is not called by this command.

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

## Sectors integration status

| Surface | Status | Reference |
| --- | --- | --- |
| Client + capability protocols | shipped | `src/idx_leadership/providers/sectors_*.py` |
| `SECTORS_LIVE` mode | exercised; explicit key and credit-spend gates remain | `src/idx_leadership/providers/factory.py` |
| Normalizers (taxonomy, close, free float, flow, corporate actions) | shipped, fixture-tested | `src/idx_leadership/providers/sectors_normalizers.py` |
| Contract drift tests | shipped, fixture-only | `tests/test_provider_contracts.py` |
| Sectors-shaped fixtures | shipped | `data/fixtures/sectors/` |
| Live market-wide snapshot | exercised; `READY_WITH_GAPS` at 99.2% requested-history coverage for 500 used of 962 discovered rows; 265 policy-eligible | `scripts/build_market_snapshot.py` |
| Live parity | exercised; 3/3 close spot-checks matched | `scripts/compare_providers.py` |
| Live credit audit | shipped, command ready, `BALANCE UNAVAILABLE` without balances | `scripts/audit_sectors_credit.py` |
| Live price-basis audit | still open; raw/adjusted semantics remain `UNKNOWN / VERIFY` | `scripts/audit_price_basis.py` |
| Blocker register | shipped | `docs/SECTORS_BLOCKERS.md` |
| Live runbook | shipped | `docs/LIVE_SECTORS_RUNBOOK.md` |

The blocker register remains useful for unresolved provider questions, but
the live bundle and its sanitized validation artifacts are now the evidence
for the exercised path. Do not treat demo or public prototype payloads as
live market observations.

## Live Sectors + Tavily refresh

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

# 6. Market-wide live snapshot. Preflight is the paid-run gate; the client
#    hard-stops before any request that would exceed 1,000 Sectors credits.
.venv/bin/python -m scripts.build_market_snapshot \
  --allow-live --allow-credit-spend --max-estimated-credits 1000 \
  --history-workers 1 --with-tavily

# 7. Export only the live snapshot for the SPA's default index.
.venv/bin/python -m scripts.export_snapshot_json --snapshot-id snap_sectors_YYYY-MM-DD
.venv/bin/python -m scripts.build_snapshot_index --provider-mode SECTORS_LIVE
```

The runbook (`docs/LIVE_SECTORS_RUNBOOK.md`) covers the same flow with
failure handling, rollback, and quarantine.

## Quick start

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

## Current scope

- Live Sectors security master of 962 discovered IDX company rows in the
  exercised 2026-08-27 snapshot; the browser payload uses a disclosed 500-row
  prefix sample, with 265 policy-eligible securities and 496/500 usable
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

## Quick start

```bash
git clone <this repo>
cd idx-leadership-diffusion
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

# Build a snapshot from the public-data prototype
.venv/bin/python -m scripts.build_snapshot --provider public --as-of 2026-08-20

# Run the test suite
.venv/bin/pytest -q

# Launch the exploratory UI
streamlit run app/streamlit_app.py
```

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

- Prototype universe is not full IDX.
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

## Sectors operating model

The provider abstraction is the seam. `SectorsProvider` is implemented
against the Sectors v2 HTTP contract and refuses live calls by default.
When credentials are available:

- `config/providers.yaml` flipped to `enabled: true` for `sectors`
- run the bounded validator, then
  `scripts/build_market_snapshot.py --allow-live --allow-credit-spend`
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
