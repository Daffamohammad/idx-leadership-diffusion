# Live Methodology Audit

> **Status:** Frontier Pass #2 audit. **No live Sectors key** is
> present in this environment, so every "Live evidence" cell is
> `BLOCKED — no key`. The structure of the table is intended to be
> populated when a key is available; this pass does not invent
> values.

## 1. Universe

| Component | Groundwork assumption | Live evidence | Decision | Version impact |
| --- | --- | --- | --- | --- |
| Universe | 50 names in `config/universe.yaml` | BLOCKED — no key | retain `universe.yaml` as a **fallback / dev-mode** source only | v1 → v2 (no change to universe file) |

## 2. Taxonomy

| Component | Groundwork assumption | Live evidence | Decision | Version impact |
| --- | --- | --- | --- | --- |
| Sector / subsector / industry / sub_industry | local coarse mapping | BLOCKED — no key | subsector as primary analytical level; industry as drilldown; sub_industry too fragmented | `methodology.yaml::groups.primary_taxonomy_level = subsector` |

## 3. Benchmark

| Component | Groundwork assumption | Live evidence | Decision | Version impact |
| --- | --- | --- | --- | --- |
| IHSG | Yahoo `^JKSE` | BLOCKED — no key | engine falls back to cross-section mean when IHSG.JK is missing; labeled `price_basis: close_proxy_mean` in `ihsg.csv` | no version bump |

## 4. Horizon

| Component | Groundwork assumption | Live evidence | Decision | Version impact |
| --- | --- | --- | --- | --- |
| 5D / 20D / 60D | baseline | BLOCKED — no key | retain. `run_horizon_sensitivity.py` queued | no bump |

## 5. Breadth

| Component | Groundwork assumption | Live evidence | Decision | Version impact |
| --- | --- | --- | --- | --- |
| positive_return_share | yes | BLOCKED | retain | no bump |
| benchmark_outperformance_share | yes | BLOCKED | retain | no bump |
| improvement_share | yes | BLOCKED | retain | no bump |
| raw vs trading-eligible | not distinguished | BLOCKED | both views available; `run_stale_trading.py` queued | no bump |

## 6. Diffusion

| Component | Groundwork assumption | Live evidence | Decision | Version impact |
| --- | --- | --- | --- | --- |
| v1 raw ±10pp | yes | v1 unstable for small groups (FP1 evidence) | replaced by v2 group-size-aware | v1 → v2 |
| v2 group-size-aware | new in FP1 | BLOCKED — no live key | retain; v1 retained for back-compat via `to_v1_state` | n/a (already v2) |

## 7. Concentration

| Component | Groundwork assumption | Live evidence | Decision | Version impact |
| --- | --- | --- | --- | --- |
| absolute-move top-N | yes | top-N could exceed 1.0 (FP1 evidence) | v2: explicit `top1_abs_share ≤ 1.0` cap; signed share added | v1 → v2 |

## 8. Persistence

| Component | Groundwork assumption | Live evidence | Decision | Version impact |
| --- | --- | --- | --- | --- |
| persistence metric | not present | new in FP2 | `compute_persistence` (leadership / diffusion / broadening / narrowing) shipped; depends on history depth | new in v2 |

## 9. Eligibility

| Component | Groundwork assumption | Live evidence | Decision | Version impact |
| --- | --- | --- | --- | --- |
| 5-rule eligibility filter | not present | new in FP1; `EligibilityConfig` exposed | retain; v2 added `default listing_board = "Main"` for `SecurityMasterEntry` (D016) | v1 → v2 |

## 10. Weighting

| Component | Groundwork assumption | Live evidence | Decision | Version impact |
| --- | --- | --- | --- | --- |
| Equal-weight group return | yes | unchanged | retain as default | no bump |
| Free-float weighting | researched | wired as parallel magnitude view (D011) | not auto-applied | new capability, no rule change |

## 11. Net changes vs groundwork

* v1 → v2: diffusion, concentration, eligibility, methodology
  versioning, persistence, contradictions, invalidation.
* New scripts: `credit_audit`, `refresh_sectors_core`,
  `build_market_snapshot`, `compare_providers`, `run_state_turnover`,
  `run_stale_trading`, `run_horizon_sensitivity`,
  `run_diffusion_sensitivity`, `audit_close_basis`.
* New docs: `SECTORS_PRICE_BASIS.md`, `LIVE_METHODOLOGY_AUDIT.md`,
  `FRONTIER_PASS_2_AUDIT.md`.
* 44 new tests; 158 → 202 passing.
