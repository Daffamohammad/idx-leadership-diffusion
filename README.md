# IDX Leadership Diffusion

> A market-wide intelligence system that detects not only where
> leadership is moving across Indonesian equities, but whether that
> leadership is broadening, concentrating, or deteriorating beneath
> the index surface.

This is the current offline-ready implementation. It includes the
provider abstraction, a live-gated Sectors v2 client, versioned
methodology engines, snapshot/manifest/quality infrastructure, a
deterministic story-mode UI, a synthetic-market methodology harness
(scenarios A–G), and an offline pytest suite of 287 tests. No live
Sectors data is claimed in this environment because `SECTORS_API_KEY`
is not present.

**This project is an analytical market-intelligence prototype for
research and educational purposes. It does not provide investment
advice or personalized recommendations.**

## Sections

- [What works now](#what-works-now)
- [Prototype mode](#prototype-mode)
- [Demo mode](#demo-mode)
- [Sectors integration status](#sectors-integration-status)
- [How to validate live once a key arrives](#how-to-validate-live-once-a-key-arrives)
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
| Price-basis investigation (`audit_price_basis --as-of`) | shipped, fixture-blocked without a key | `scripts/audit_price_basis.py` |
| Sectors credit audit (`audit_sectors_credit`) | shipped, `BALANCE UNAVAILABLE` without observed balances | `scripts/audit_sectors_credit.py` |
| Provider parity (`compare_providers`) | shipped, fixture parity only | `scripts/compare_providers.py` |
| Refresh budget dry-run (`plan_sectors_refresh`) | shipped | `scripts/plan_sectors_refresh.py` |
| Markdown market brief export (`export_market_brief`) | shipped | `scripts/export_market_brief.py` |
| State turnover audit (`audit_state_turnover`) | shipped, JSON+CSV+MD | `scripts/audit_state_turnover.py` |
| 287 tests, all offline | shipped | `pytest tests` |

## Prototype mode

The prototype mode uses public market data via `yfinance` for the
prototype universe declared in `config/universe.yaml`. The
classification metadata in that file is **prototype metadata** and
is not authoritative Sectors taxonomy. Snapshots produced in this
mode are labelled `PUBLIC PROTOTYPE` in the UI.

```bash
python -m scripts.build_snapshot --provider fixture --as-of 2026-08-20
streamlit run app/streamlit_app.py
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
| `SECTORS_LIVE` mode | shipped, refuses without key or `--allow-credit-spend` | `src/idx_leadership/providers/factory.py` |
| Normalizers (taxonomy, close, free float, flow, corporate actions) | shipped, fixture-tested | `src/idx_leadership/providers/sectors_normalizers.py` |
| Contract drift tests | shipped, fixture-only | `tests/test_provider_contracts.py` |
| Sectors-shaped fixtures | shipped | `data/fixtures/sectors/` |
| Live market-wide snapshot | shipped, command ready, BLOCKED on key | `scripts/build_market_snapshot.py` |
| Live parity | shipped, command ready, BLOCKED on key | `scripts/compare_providers.py` |
| Live credit audit | shipped, command ready, `BALANCE UNAVAILABLE` without balances | `scripts/audit_sectors_credit.py` |
| Live price-basis audit | shipped, command ready, `SECTORS LIVE COMPARISON BLOCKED` without key | `scripts/audit_price_basis.py` |
| Blocker register | shipped | `docs/SECTORS_BLOCKERS.md` |
| Live runbook | shipped | `docs/LIVE_SECTORS_RUNBOOK.md` |

The blocker register lists every empirical question that requires a
credential. None of them are answered by offline scaffolding.

## How to validate live once a key arrives

```bash
# 1. Confirm key is present (env only; never log it).
test -n "${SECTORS_API_KEY:-}" && echo "key present" || echo "key missing"

# 2. Run the offline suite to confirm a clean baseline.
python -m pytest -q

# 3. Dry-run the bounded validator (no HTTP).
python -m scripts.validate_sectors_live --dry-run --as-of 2026-08-20

# 4. Bounded credentialed validation (one page per endpoint).
python -m scripts.validate_sectors_live \
  --live --allow-credit-spend --as-of 2026-08-20

# 5. Price-basis audit on a known corporate action.
python -m scripts.audit_price_basis \
  --ticker BBCA.JK --start 2021-10-01 --end 2021-10-29 \
  --corporate-action-date 2021-10-13 \
  --sectors-mode SECTORS_LIVE --live --allow-credit-spend \
  --as-of 2021-10-29

# 6. Market-wide snapshot only after the above are clean.
python -m scripts.build_market_snapshot --as-of 2026-08-20 --allow-live
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
python -m scripts.build_snapshot --provider fixture --as-of 2026-08-20

# Run the test suite (offline, 287 tests)
pytest

# Launch the exploratory UI
streamlit run app/streamlit_app.py
```

## Current scope

- Prototype universe of ~50 cross-sector IDX tickers (see `config/universe.yaml`).
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
python -m scripts.build_snapshot --provider fixture --as-of 2026-08-20

# Run the test suite
pytest

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
- Live Sectors values are unavailable until a key is supplied; the
  client is implemented and live calls are gated.
- No foreign flow, broker activity, fundamental, or news confirmation.
- Adjusted price is the only corporate-action guardrail.

See `docs/KNOWN_GAPS.md` for the full register.

## Sectors migration plan

The provider abstraction is the seam. `SectorsProvider` is implemented
against the Sectors v2 HTTP contract and refuses live calls by default.
When credentials are available:

- `config/providers.yaml` flipped to `enabled: true` for `sectors`
- run `scripts/refresh_sectors_core.py --allow-live` for the bounded
  Tier-1 refresh, then
  `scripts/build_market_snapshot.py --allow-live` for the snapshot
- Parity test (P0.5) run before cutover
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
