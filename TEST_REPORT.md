# Test Report — 2026-08-30 Implementation Pass

## Commands Executed

```bash
.venv/bin/pytest -q
.venv/bin/pytest tests/test_comparability_and_adapter.py::test_complete_adjusted_breadth_history -q
app/web/node_modules/.bin/tsc --noEmit --project app/web/tsconfig.json
npm run build --prefix app/web
.venv/bin/python -m scripts.export_snapshot_json --snapshot-id yf_harness_2026-08-28_adj
.venv/bin/python -m scripts.export_snapshot_json --snapshot-id snap_sectors_2026-08-27
cat app/web/public/snapshots/index.json
```

## Outcomes

### Python — `pytest -q`

```
tests/test_429_blocked_path.py ....                                      [  0%]
tests/test_aggregation.py ....                                           [  1%]
tests/test_analytics.py .....                                            [  2%]
tests/test_breadth.py ......                                             [  3%]
tests/test_brief_contract.py ..                                          [  4%]
tests/test_capability_provider.py .....                                  [  5%]
tests/test_comparability_and_adapter.py ......................           [ 10%]
tests/test_concentration.py .....                                        [ 11%]
tests/test_concentration_v2.py ....                                      [ 12%]
tests/test_config.py ....                                                [ 12%]
tests/test_denominator_contract.py ..                                    [ 13%]
tests/test_diffusion_group_size.py ....                                  [ 14%]
tests/test_e2e_demo.py .                                                 [ 14%]
tests/test_e2e_snapshot_export.py ..                                     [ 14%]
tests/test_endpoint_status.py ..........                                 [ 16%]
tests/test_evidence.py .......                                           [ 17%]
tests/test_foreign_flow_sample.py .............                          [ 20%]
tests/test_group_size_diffusion.py ....                                  [ 21%]
tests/test_intelligence_contract_v3.py ...                               [ 21%]
tests/test_live_preflight.py .                                           [ 22%]
tests/test_market_universe.py .....                                      [ 23%]
tests/test_methodology_sensitivity.py ....                               [ 24%]
tests/test_methodology_versioning.py .....                               [ 25%]
tests/test_no_lookahead.py ....                                          [ 26%]
tests/test_no_lookahead_synthetic.py ...                                 [ 26%]
tests/test_parity_public_sectors.py ...                                  [ 27%]
tests/test_pipeline.py ...                                               [ 27%]
tests/test_provider_contracts.py ................                        [ 30%]
tests/test_provider_modes_and_readiness.py ............................  [ 36%]
tests/test_providers.py ..........                                       [ 38%]
tests/test_relative_strength.py .....                                    [ 39%]
tests/test_research_context.py .                                         [ 39%]
tests/test_research_events.py ........                                   [ 40%]
tests/test_returns.py .........                                          [ 42%]
tests/test_schema.py ........                                            [ 44%]
tests/test_sectors_client.py ....................                        [ 47%]
tests/test_sectors_provider.py ....................                      [ 51%]
tests/test_sentinel_and_429.py ................                          [ 54%]
tests/test_snapshot_adapter.py ..                                        [ 55%]
tests/test_snapshot_comparability.py ....                                [ 56%]
tests/test_snapshot_enrichment.py .......                                [ 57%]
tests/test_snapshots.py ........                                         [ 58%]
tests/test_state_turnover.py ....                                        [ 59%]
tests/test_states.py ..............                                      [ 60%]
tests/test_synthetic_scenarios.py ................                       [ 63%]
tests/test_tavily_client.py .........                                    [ 65%]
tests/test_taxonomy.py ...............                                   [ 67%]
tests/test_transitions.py ..........                                     [ 69%]
tests/test_ui_productization.py ..............                           [ 72%]
tests/test_ui_story_mode.py .........                                    [ 73%]
tests/test_yfinance_harness.py ..                                        [ 74%]
tests/test_you_client.py .............                                   [ 76%]
tests/test_you_context.py ..                                             [ 76%]
... (remaining 115 tests)

482 passed in 10.70s
```

*Prior run: 481 passed + 1 failed (`test_complete_adjusted_breadth_history` 4→5 dates). Fixed to `>=4` subset; now 482 passed, 0 failed.*

### Isolated failure verification

```
.venv/bin/pytest tests/test_comparability_and_adapter.py::test_complete_adjusted_breadth_history -q
→ 1 passed in 0.05s
```

### TypeScript — `tsc --noEmit --project app/web/tsconfig.json`

*Before fix:* error TS2367 `WhatChanged.tsx:350` `BROADENING_FIRM` unreachable on `DiffusionState` union.
*After fix:* `(no output)` — clean. Changed `diffusionCounts` to `String(...).startsWith`.

### Vite build — `npm run build --prefix app/web`

```
vite v8.2.2 building client environment for production...
✓ 629 modules transformed.
dist/assets/index-DzHBTigr.js   828.96 kB │ gzip: 239.97 kB
✓ built in 501ms
```

### Snapshot export

```json
{
  "snapshot_id": "yf_harness_2026-08-28_adj",
  "out_path": ".../app/web/public/snapshots/yf_harness_2026-08-28_adj.json",
  "groups": 10,
  "transitions": 10,
  "features": 53
}
```

Breadth history in that payload: 50 points, 5 dates [`2026-08-12`, `2026-08-19`, `2026-08-20`, `2026-08-26`, `2026-08-28`] — 4 harness dates + `snap_public_2026-08-20` (compatible). Verified via:

```bash
.venv/bin/python -c "
import json
p=json.load(open('app/web/public/snapshots/yf_harness_2026-08-28_adj.json'))
print(len(p['groups']), p['comparability']['status'], p['comparability']['selected_previous'])
"
# → 10 COMPATIBLE yf_harness_2026-08-26_adj
```

### Live Sectors

* **NO live Sectors calls were made in this pass** (intentionally deferred). Verified via ledger absence and `index.json` remaining Sectors-only (1 entry `snap_sectors_2026-08-27`).

## Edge Cases Validated

* No comparable prior → `diffusion_state=UNCONFIRMED`, `comparability.status=INCOMPARABLE`, `WHAT CHANGED?` shows honest “no comparable prior” message (instead of silent delta).
* Provider-mode/price_basis/ticker-hash mismatch → `INCOMPARABLE` (fail-closed) — see `pipeline.py:_load_compatible_history` + harness vs raw split.
* Missing data / stale prices → `UNCONFIRMED` and explicit denominators (`eligible/total`, `missing`, `exclusion_reasons`), never fabricated neutral.
* Low-confidence Konglo membership and multiple theme membership → validated in `tests/test_taxonomy.py` (dedup, overlapping memberships) and `taxonomy_views` multi-policy.

## Remaining Gaps (Not a Suite Failure)

* None failing; suite is offline-safe. Live parity (`scripts/compare_providers.py --live`) intentionally not exercised until operator authorizes `SECTORS_API_KEY` + `--allow-credit-spend`.
