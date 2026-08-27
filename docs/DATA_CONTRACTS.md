# IDX Leadership Diffusion — Data Contracts

All schemas are defined in `src/idx_leadership/models/`. Pydantic v2
is used at the boundary; internal computation may use plain
dictionaries or DataFrames for performance.

Schema version: `schemas-v2`.

---

## Security master

| Field | Type | Nullable | Notes |
| --- | --- | --- | --- |
| `ticker` | str | no | Canonical ticker (e.g. `BBCA.JK`). PK. |
| `vendor_ticker` | str | no | Ticker as used by the provider. |
| `company_name` | str | yes | |
| `exchange` | str | yes | |
| `country` | str | yes | default "ID" |
| `sector` | str | yes | coarse label (prototype) |
| `subsector` | str | yes | coarse label (prototype) |
| `industry` | str | yes | not populated in prototype |
| `subindustry` | str | yes | not populated in prototype |
| `group_id` | str | yes | taxonomy key used for aggregation |
| `active` | bool | no | default true |
| `benchmark_flag` | bool | no | default false |
| `source` | enum | no | `yfinance` / `sectors` / `fixture` |
| `source_as_of` | date | yes | when this row was last refreshed |

**Primary key:** `ticker`. **Granularity:** one row per security.

---

## Price observation

| Field | Type | Nullable | Notes |
| --- | --- | --- | --- |
| `ticker` | str | no | |
| `date` | date | no | trading day |
| `close` | float | no | > 0 |
| `adjusted_close` | float | no | > 0 |
| `volume` | int | yes | ≥ 0 if present |
| `market_cap` | float | yes | ≥ 0 if present |
| `currency` | str | no | default "IDR" |
| `price_basis` | enum | no | `adjusted_close` or `close` |
| `source` | enum | no | |
| `source_timestamp` | date | yes | when the row was fetched |

**Primary key:** (`ticker`, `date`). **Granularity:** one row per
security per trading day.

**Invariants:**

- Both `close` and `adjusted_close` must be strictly positive.
- `volume` and `market_cap` are nullable; the prototype omits them.
- `price_basis` is the choice the analytical engine should respect;
  do not silently fall back across bases.

---

## Benchmark observation

| Field | Type | Nullable | Notes |
| --- | --- | --- | --- |
| `benchmark_id` | str | no | e.g. "IHSG" |
| `date` | date | no | |
| `close` | float | no | > 0 |
| `adjusted_close` | float | yes | > 0 |
| `price_basis` | enum | no | default `close` |
| `source` | enum | no | |

**Primary key:** (`benchmark_id`, `date`).

---

## Security feature snapshot

| Field | Type | Nullable | Notes |
| --- | --- | --- | --- |
| `snapshot_date` | date | no | |
| `ticker` | str | no | |
| `return_5d` | float | yes | percent |
| `return_20d` | float | yes | percent |
| `return_60d` | float | yes | percent |
| `benchmark_return_5d` | float | yes | percent |
| `benchmark_return_20d` | float | yes | percent |
| `benchmark_return_60d` | float | yes | percent |
| `excess_return_5d` | float | yes | percent |
| `excess_return_20d` | float | yes | percent |
| `excess_return_60d` | float | yes | percent |
| `relative_strength_level` | float | yes | equals `excess_return_20d` |
| `relative_strength_change` | float | yes | `excess_return_5d - excess_return_60d` |
| `volume_ratio` | float | yes | reserved |
| `trend_above_ma20` | bool | yes | reserved |
| `eligible` | enum | no | `ELIGIBLE` / `INELIGIBLE` / `UNCONFIRMED` |
| `eligibility_reason` | str | yes | |
| `feature_version` | str | no | |
| `price_basis` | enum | no | |

**Primary key:** (`snapshot_date`, `ticker`).

---

## Group snapshot

| Field | Type | Nullable | Notes |
| --- | --- | --- | --- |
| `snapshot_date` | date | no | |
| `taxonomy_level` | str | no | default "sector" |
| `group_id` | str | no | PK part |
| `group_name` | str | yes | |
| `constituent_count` | int | no | ≥ 0 |
| `eligible_count` | int | no | ≥ 0 |
| `missing_count` | int | no | ≥ 0 |
| `group_return_equal_weight` | float | yes | percent |
| `group_excess_return` | float | yes | percent |
| `group_excess_return_5d` | float | yes | percent |
| `group_excess_return_20d` | float | yes | percent |
| `group_excess_return_60d` | float | yes | percent |
| `breadth_positive` | float | yes | 0-100 |
| `breadth_outperforming` | float | yes | 0-100 |
| `breadth_delta` | float | yes | pp |
| `concentration` | ConcentrationMetrics | no | nested |
| `leadership_state` | enum | no | |
| `diffusion_state` | enum | no | |
| `diffusion_state_v2` | enum | yes | Group-size-aware v2 state; v1 field remains for compatibility. |
| `leadership_rank` | int | yes | ≥ 1 |
| `change_rank` | int | yes | ≥ 1 |
| `method_version` | str | no | |
| `feature_version` | str | no | |
| `last_materiality` | enum | no | |

**ConcentrationMetrics nested schema:**

| Field | Type | Nullable | Notes |
| --- | --- | --- | --- |
| `top1_contribution_share` | float | yes | 0-1 |
| `top3_contribution_share` | float | yes | 0-1 |
| `top5_contribution_share` | float | yes | 0-1 |
| `top1_signed_share` | float | yes | Signed attribution for the largest absolute contributor. |
| `top3_signed_share` | float | yes | Signed attribution for the top three absolute contributors. |
| `hhi_contribution` | float | yes | 0-1 |
| `contributor_count` | int | no | ≥ 0 |
| `convention` | str | no | `absolute_move_v2` for new snapshots; `absolute_move` for v1. |

**Primary key:** (`snapshot_date`, `group_id`).

---

## Transition event

| Field | Type | Nullable | Notes |
| --- | --- | --- | --- |
| `current_date` | date | no | |
| `previous_date` | date | yes | null for first observation |
| `taxonomy_level` | str | no | default "sector" |
| `group_id` | str | no | |
| `previous_leadership_state` | enum | no | |
| `current_leadership_state` | enum | no | |
| `previous_diffusion_state` | enum | no | |
| `current_diffusion_state` | enum | no | |
| `previous_diffusion_state_v2` | enum | yes | Rich v2 previous state when available. |
| `current_diffusion_state_v2` | enum | yes | Rich v2 current state when available. |
| `leadership_transition` | str | yes | `"PREV -> CURR"` |
| `diffusion_transition` | str | yes | `"PREV -> CURR"` |
| `diffusion_transition_v2` | str | yes | `"PREV -> CURR"` for v2 states. |
| `breadth_delta` | float | yes | |
| `relative_strength_delta` | float | yes | |
| `rank_delta` | int | yes | positive = improved |
| `materiality_label` | enum | no | |
| `materiality_reason` | str | yes | |
| `transition_version` | str | no | |

**Primary key:** (`current_date`, `group_id`).

---

## Evidence object

```json
{
  "group_id": "Financials",
  "as_of": "2026-08-20",
  "leadership_state": "LEADING",
  "diffusion_state": "BROADENING",
  "diffusion_state_v2": "BROADENING_FIRM",
  "evidence": [
    {"metric": "excess_return_20d", "value": 3.5, "unit": "%", "direction": "positive"}
  ],
  "contradictions": [],
  "data_gaps": [
    "foreign flow not integrated",
    "fundamental confirmation not integrated"
  ],
  "method_version": "methodology-v2"
}
```

This is the **unit of output** for any narration layer. The
`build_group_evidence` function emits one of these per group.

---

## Manifest

A snapshot includes a per-snapshot `manifest.json`:

```json
{
  "snapshot_id": "snap_2026-08-20",
  "snapshot_date": "2026-08-20",
  "as_of": "2026-08-20",
  "provider": "yfinance",
  "universe_version": "prototype-v1",
  "taxonomy_version": "prototype-v1",
  "method_version": "methodology-v2",
  "feature_version": "features-v2",
  "coverage_status": "READY",
  "coverage_pct": 100.0,
  "created_at": "2026-08-27"
}
```

The aggregated manifest at `data/snapshots/manifest.json` collects
all per-snapshot entries.

---

## Snapshot directory layout

```text
data/snapshots/<snapshot_id>/
├── manifest.json
├── change_digest.json
├── quality.json
├── prices.csv
├── prices.parquet
├── benchmark.csv
├── benchmark.parquet
├── features.parquet
├── groups.parquet
├── transitions.parquet
└── security_master.json
```
