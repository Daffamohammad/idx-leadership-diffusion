# Methodology Sensitivity

> **Status:** design + offline test. A live sensitivity study requires
> the real Sectors market-wide feed; this pass ships the **harness** and
> the **qualitative reasoning** that drove each decision.

## 1. What this document covers

For each methodology knob that has a defensible alternative, we record:

* the **baseline value** chosen in `config/methodology.yaml`
  (`method_version: methodology-v2`),
* the **alternatives considered**,
* the **rejection criterion** (turnover, instability, sign-confusion, etc.),
* the **evidence** (test names or, where a live study is required, the
  harness that must run).

## 2. Horizon sensitivity (5/20/60 vs alternatives)

| Horizon pair | Behavior on the fixture | Decision |
| --- | --- | --- |
| 5/20/60 (baseline) | financial acceleration visible; coverage good | **kept** |
| 10/20/60 | 10D obscures acceleration for thin groups | rejected |
| 20/60 only | drops the acceleration feature | rejected |
| 5/20 only | drops the medium-horizon confirmation | rejected |

Harness: `tests/test_relative_strength.py` exercises the 20D / 60D
math; `tests/test_states.py` exercises the acceleration feature.
Live stability study is queued (P3 in `NEXT_ITERATION.md`).

## 3. Group-size-aware diffusion (±10pp vs v2)

| Rule | Small-group (n=5) | Large-group (n=50) | Decision |
| --- | --- | --- | --- |
| ±10pp raw | one stock flip flips state | meaningful sector rotation | rejected for small groups |
| ±10pp + constituent floor (v2) | stays FRAGILE/STABLE | FIRM when rotation is real | **kept** |
| z-score over trailing 60D | too noisy on small fixture | too complex for v1 | rejected for v2 |

`tests/test_diffusion_group_size.py` covers the v2 behavior.

## 4. Concentration decomposition

| Approach | Sign-confusion safe? | Top-1 > 100% possible? | Decision |
| --- | --- | --- | --- |
| v1 absolute-move share | yes | no, but the value was reported as `top3 > 1.0` in pathological cases | replaced |
| v2 absolute-move share, capped at 1.0 | yes | **explicitly capped with reason** | **kept** |
| signed contribution share (no cap) | no (sign confusion on the small group) | yes (signed) | kept as a separate `top1_signed_share` metric, not as the primary |
| HHI | yes (uses absolute shares) | yes (≤ 1.0) | kept |

`tests/test_concentration_v2.py` exercises the v2 behavior including
the `top1 ≤ 1.0` cap.

## 5. Breadth metric set

| Metric | Default | Decision |
| --- | --- | --- |
| `positive_return_share` | yes | kept; trivial and fast |
| `benchmark_outperformance_share` | yes | kept; the canonical participation metric |
| `improvement_share` | yes | kept as a secondary confirmation |
| signed positive-return share | not exposed | not exposed in v2; raw counts are easier to interpret |

`tests/test_breadth.py` is unchanged.

## 6. State thresholds

| Threshold | Baseline | Decision |
| --- | --- | --- |
| `acceleration_threshold_pp` | `1.0` | kept (prov interpretable) |
| `excess_return_improving` | `0.0` | kept |
| `excess_return_leading` | `0.0` | kept |
| `broadening_threshold_pp` | `10.0` | kept as the v1 rule; v2 adds the constituent floor |
| `narrowing_threshold_pp` | `-10.0` | kept as the v1 rule; v2 adds the constituent floor |
| `min_group_size` | `5` (was 4) | increased from 4 to 5 to stabilize small subsectors |

## 7. Minimum eligibility

| Knob | Baseline | Decision |
| --- | --- | --- |
| `min_history_days` | 60 | kept (60 trading days = 3 months; robust) |
| `stale_trading_days` | 30 | kept (one month of inactivity) |
| `min_group_size` | 5 | raised from 4 |
| `min_coverage_pct` | 60% | kept |

## 8. State stability (churn test, queued)

The next pass should compute the **state transition rate** over a
multi-month history. If the rate is e.g. > 2 transitions per group per
month, the rule is too sensitive. The harness lives in
`tests/test_states.py` (boundary thresholds) but a live stability
study needs a Sectors market-wide history of at least 60 trading
days.

## 9. Backtest-forbidden guardrails

This document explicitly does **not** include any forward-return
diagnostic. Per the brief §29 and D005, parameter choices are made
on structural stability, not on realized returns. A descriptive
forward-return table may be added in the next pass (D017) but only as
a secondary diagnostic, with no headline claim.
