# Live Methodology Audit

> **Status:** Frontier Pass #2 live audit, exercised 2026-08-28. The first
> market-wide Sectors snapshot is reproducible and labeled
> `READY_WITH_GAPS`; unresolved items remain `UNKNOWN / VERIFY`.

## 1. Universe

| Component | Groundwork assumption | Live evidence | Decision | Version impact |
| --- | --- | --- | --- | --- |
| Universe | 50 names in `config/universe.yaml` | 962 Sectors company rows discovered; 500 used as an explicitly disclosed prefix sample; 265 policy-eligible | retain `universe.yaml` as a **fallback / dev-mode** source only | v1 → v2 (no change to universe file) |

## 2. Taxonomy

| Component | Groundwork assumption | Live evidence | Decision | Version impact |
| --- | --- | --- | --- | --- |
| Sector / subsector / industry / sub_industry | local coarse mapping | structured taxonomy complete for 500/500 used rows; 962 rows discovered upstream | Sectors taxonomy is authoritative for the live snapshot; subsector remains primary analytical level | `methodology.yaml::groups.primary_taxonomy_level = subsector` |

## 3. Benchmark

| Component | Groundwork assumption | Live evidence | Decision | Version impact |
| --- | --- | --- | --- | --- |
| IHSG | Yahoo `^JKSE` | Sectors `/v2/index-daily/ihsg/`, latest 2026-08-27 | use the native Sectors benchmark in `SECTORS_LIVE`; parity remains a separate validation check | no version bump |

## 4. Horizon

| Component | Groundwork assumption | Live evidence | Decision | Version impact |
| --- | --- | --- | --- | --- |
| 5D / 20D / 60D | baseline | executed from the live per-symbol history window | retain; live sensitivity report shows no changed states across comparable groups | no bump |

## 5. Breadth

| Component | Groundwork assumption | Live evidence | Decision | Version impact |
| --- | --- | --- | --- | --- |
| positive_return_share | yes | executed on eligible live rows | retain | no bump |
| benchmark_outperformance_share | yes | executed against native Sectors IHSG | retain | no bump |
| improvement_share | yes | executed where comparable history exists | retain | no bump |
| raw vs trading-eligible | not distinguished | raw 500 used rows; 265 eligible; exclusions are persisted | retain both views and the explicit exclusion reasons | no bump |

## 6. Diffusion

| Component | Groundwork assumption | Live evidence | Decision | Version impact |
| --- | --- | --- | --- | --- |
| v1 raw ±10pp | yes | v1 unstable for small groups (FP1 evidence) | replaced by v2 group-size-aware | v1 → v2 |
| v2 group-size-aware | new in FP1 | live diffusion has no comparable prior snapshot, so all diffusion states remain `UNCONFIRMED` | retain; v1 retained for back-compat via `to_v1_state` | n/a (already v2) |

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
* 386 offline tests pass after the live integration; the live snapshot remains
  `READY_WITH_GAPS` because of the disclosed prefix sample, unresolved
  price-basis semantics, and the absence of a comparable prior snapshot.
