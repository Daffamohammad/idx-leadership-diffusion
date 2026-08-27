# IDX Leadership Diffusion — Methodology

> All numerical thresholds live in `config/methodology.yaml`. No magic
> numbers in code. This document states the formulas; values are
> versioned and configurable. The current configuration is
> `methodology-v2` / `features-v2`; v1 snapshots remain readable.

## 1. Universe

Offline/prototype runs use a **subset of IDX** declared in
`config/universe.yaml`. The subset is intentionally cross-sector and
reviewable. It is **not** the full IDX. Group-level conclusions drawn
from this universe are partial by definition.

| Field | Source | Versioning |
| --- | --- | --- |
| `universe` | `config/universe.yaml` | `universe_version` |
| Taxonomy mapping | `config/universe.yaml` (sectors/sub_sectors) | `taxonomy_version` |
| Benchmark | `^JKSE` (Yahoo) | benchmark_id = "IHSG" in canonical schema |

The taxonomy is **prototype metadata**, not authoritative Sectors
taxonomy. Missing values remain explicit; nothing is fabricated.

## 2. Benchmark

The primary benchmark is the IHSG (Yahoo: `^JKSE`). The pipeline uses
`close` for benchmark return calculations and `adjusted_close` for
securities.

## 3. Price basis

- Securities: **adjusted_close** (dividends/splits adjusted).
- Benchmark: **close** (raw index level).

Documented in the `PriceObservation.price_basis` and
`BenchmarkObservation.price_basis` fields. The pipeline also records
the `methodology.yaml.price_basis` selection.

## 4. Horizons

```text
short   = 5   trading days
primary = 20  trading days
medium  = 60  trading days
```

These are configurable. The pipeline is not coupled to a specific
calendar history; the Sectors full-universe-close provider can supply
the same cross-sections at these horizons when live access is enabled.

## 5. Return calculation

For a security with `n` trading days of history ending at as-of date
`d`:

```text
return_h = (P[d] / P[d-h] - 1) * 100       # percent
```

- `P` is the chosen price basis (`adjusted_close` by default).
- `h` is in trading days.
- If history is insufficient, return is `None`.
- If the start price is ≤ 0, return is `None` (invalid price guard).
- As-of resolution uses the latest observation ≤ as-of within
  `as_of_tolerance_days` (default 7 calendar days).

## 6. Relative performance

```text
excess_return_h = return_h - benchmark_return_h
```

`excess_return_h` is signed (positive = outperforming benchmark).

For groups:

```text
group_excess_return = mean(excess_return_h over eligible constituents)
```

**Equal-weight by default.** The concentration module accepts a
weighting interface for future free-float or market-cap weighting, but
the current prototype does not weight.

## 7. Group aggregation

- For each group, compute equal-weight group return and excess return
  at each horizon.
- Breadth is computed across the group's eligible constituents.
- Concentration decomposes the group's absolute price move.
- A group is **eligible** if it has ≥ `groups.minimum_constituents`
  (default 5 in methodology v2) and ≥ `groups.minimum_coverage_pct`
  (default 60%)
  constituents with non-null returns.
- Ineligible groups return `UNCONFIRMED` and are excluded from ranks.

## 8. Breadth

Per group, three primitives are computed:

| Metric | Definition | Unit |
| --- | --- | --- |
| `positive_return_share` | % constituents with `return_20d > 0` | 0-100 |
| `benchmark_outperformance_share` | % constituents with `excess_return_20d > 0` | 0-100 |
| `improvement_share` | % constituents where `excess_return_5d > excess_return_60d` | 0-100 |

Each result exposes `usable_constituents`, `total_constituents`,
`missing_constituents` so denominator semantics are explicit.

## 9. Diffusion state (methodology v2)

The v2 state is a function of the **breadth delta** versus the previous
observation plus a group-size-aware constituent floor. Let
`implied_constituent_change = abs(breadth_delta) × group_size / 100` and
`floor = max(minimum_constituents, ceil(constituent_fraction × group_size))`.

```text
if not eligible or breadth_delta is None: UNCONFIRMED
elif breadth_delta >= broadening_threshold_pp:
    BROADENING_FIRM if implied_constituent_change >= floor
    else BROADENING_FRAGILE
elif breadth_delta <= narrowing_threshold_pp:
    NARROWING_FIRM if implied_constituent_change >= floor
    else NARROWING_FRAGILE
else: STABLE
```

Default thresholds are `±10 pp`, the constituent fraction is `0.10`,
and the minimum floor is `2`; all are configurable. New snapshots store
the v2 state in `diffusion_state_v2` and also store the collapsed v1
projection in `diffusion_state` for compatibility with older readers.

This is a **provisional, descriptive rule**, not a statistical test.
Threshold edges are tested in `tests/test_states.py`.

## 10. Concentration (methodology v2)

The default convention is **absolute-move decomposition**:

1. Compute per-constituent `return_20d` in percent (or the configured
   primary horizon).
2. Sort constituents by `abs(return_20d)` descending.
3. Report:
   - `top1_contribution_share = abs(ret_1) / sum(abs(ret_i))`
   - `top3_contribution_share = sum(top 3 abs share)`
   - `top5_contribution_share = sum(top 5 abs share)`
   - `hhi_contribution = sum(share_i^2)`
   - `top1_signed_share` and `top3_signed_share` for signed attribution

This avoids the **sign-confusion trap** when the group return is
positive but most constituents are flat or negative (in that case,
`top1_contribution_share` correctly reports the dominant driver).

When the group move is exactly zero, all share metrics return `None`
(rather than dividing by zero). The signed contribution table is
exposed separately as a per-ticker diagnostic for drill-down.

The v2 convention is named `convention="absolute_move_v2"` on the
`ConcentrationMetrics` model. The legacy `absolute_move` engine remains
available for direct v1 callers.

## 11. Leadership states

Provisional 4-state model (+ UNCONFIRMED):

```text
acceleration = excess_return_5d - excess_return_60d     (in pp)

if not eligible or any input is None: UNCONFIRMED
elif excess_return_20d > 0 and acceleration >=  threshold: LEADING
elif excess_return_20d <= 0 and acceleration >=  threshold: IMPROVING
elif excess_return_20d <= 0 and acceleration <   threshold: LAGGING
else: WEAKENING
```

Default `acceleration_threshold_pp = 1.0`. Configurable.

The relationship is a **2D classification**, not an ordinal scale; we
do not treat "LEADING → WEAKENING" as the same distance as
"IMPROVING → LAGGING". Transitions are explicit categorical changes.

## 12. Transitions

`compute_transition(current, previous)` produces a `TransitionEvent`:

- `leadership_transition` = `"<prev> -> <curr>"` if state changed
- `diffusion_transition` = `"<prev> -> <curr>"` if state changed
- `diffusion_transition_v2` and the corresponding v2 previous/current
  fields are emitted when both snapshots carry `diffusion_state_v2`
- `breadth_delta` = current.breadth_delta (from prior observation)
- `relative_strength_delta` = current.relative_strength - previous
- `rank_delta` = previous.leadership_rank - current.leadership_rank
  (positive = improvement)
- `materiality_label` and `materiality_reason` are filled by a
  priority-ordered classifier.

Materiality priority:

1. NEW_LEADER: non-leading → LEADING
2. LOSS_OF_LEADERSHIP: leading/improving → not-leading
3. BROADENING: diffusion → BROADENING
4. NARROWING: diffusion → NARROWING
5. IMPROVING (no new leader): non-improving → IMPROVING
6. DETERIORATING: leading/improving → weakening/lagging
7. BROADENING / NARROWING by absolute breadth delta threshold
8. IMPROVING / DETERIORATING by excess-return delta threshold
9. STABLE otherwise

The default absolute thresholds are `±10pp` for breadth delta and
`±1.5pp` for excess return delta, both configurable.

## 13. Missing data behavior

- Missing security observation → ticker excluded from group aggregation.
- Missing benchmark observation → snapshot status `STALE` or `FAILED`.
- Group with insufficient constituents → `UNCONFIRMED`.
- Group with insufficient history → no group return; `UNCONFIRMED`.
- Negative or zero prices → rejected; treated as missing.
- As-of date older than the latest available observation by more
  than `as_of_tolerance_days` (default 7 days) → snapshot status `STALE`.

The codebase never silently fills, replaces with neutral, or imputes
missing values.

## 14. Limitations

- Equal-weight only; no market-cap or free-float weighting.
- Equal-weight; no cap-weight; no risk-adjusted weighting.
- Public prototype only. The Sectors v2 client/provider is implemented,
  but live calls remain explicitly gated and require credentials.
- No corporate-action guardrail beyond adjusted_close.
- No fundamental, flow, broker, filing, or news confirmation.
- Prototype universe ≠ full IDX.
- 5/20/60 day horizons; the engine cannot answer short-term (1D)
  tactical questions reliably from this prototype.
- Snapshots are written in serial; concurrent runs are not supported.

## 15. Future Sectors-native enrichment

For a credentialed Sectors run:

- Full-universe daily close replaces the prototype universe.
- IHSG benchmark should come from Sectors index endpoint (the public
  `^JKSE` should be cross-checked but not relied on for production).
- Free-float weights remain available through
  `CapabilityProvider.get_free_float` as a separate magnitude channel.
- Subsector reports unlock qualitative corroboration in evidence.
- Foreign flow, broker activity, fundamentals, and corporate actions
  become material confirmation layers.
