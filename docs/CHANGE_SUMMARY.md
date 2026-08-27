# Change Summary

Single-line changelog across passes. Detailed audits live next to
the original `GROUNDWORK_AUDIT.md`, `FRONTIER_PASS_1_AUDIT.md`,
`FRONTIER_PASS_2_AUDIT.md`, and `OFFLINE_REFINEMENT_AUDIT.md`.

## Integration Freeze (2026-08-28)

* **Brief contract frozen at v1** in `src/idx_leadership/intelligence/contract.py`.
  Section order is `Market Read → Leadership → Broadening →
  Narrowing → Material Shifts → Contradictions → Selected Evidence
  → Screen Invalidation → Data Gaps`. Adding a section, renaming one,
  or reordering them is a contract-version-bump change.
* **Data gaps normalized** to a structured `DataGap` object with
  frozen `DataGapCategory` and `DataGapStatus` enums
  (`FUNDAMENTALS`, `FOREIGN_FLOW`, `BROKER_ACTIVITY`, `FREE_FLOAT`,
  `TAXONOMY`, `CORPORATE_ACTIONS`, `BENCHMARK`). The duplicate
  "foreign flow unavailable — Sectors live not connected" string is
  gone; each category appears at most once in the brief.
* **Contradictions section added** to the brief. A deterministic
  `ContradictionRecord` with `metric`, `label`, `severity`, and
  `evidence` is consumed by both the UI and the Markdown renderer.
  Bullets are deduplicated by `(group, metric)` and sorted with
  CRITICAL before WARNING.
* **Screen invalidation sub-section** added under Selected Evidence.
  The frozen `InvalidationCondition` carries `condition`, `metric`,
  `threshold`, and `rationale`; the brief always renders a
  deterministic intro line and one bullet per condition.
* **Intelligence contract version stamped** on `GroupEvidence` as
  `intelligence-v1`; the brief and the UI consume the same shape.
* **End-to-end demo regression** in `tests/test_e2e_demo.py`
  exercises the full source → snapshot → transition → intelligence →
  brief path and asserts the frozen contract.
* **Brief contract golden tests** in `tests/test_brief_contract.py`
  run the real `scripts.export_market_brief` subprocess against the
  demo fixture and assert the section order, the structured data gaps,
  the contradictions section, and the screen invalidation bullets.
* **Test count: 313 passing** (was 287; +26 from this freeze pass).
* No live Sectors data was claimed. No live Sectors call was made.

## Offline Refinement (2026-08-28)

* Fixed `_optional_enum` return path in `app/snapshot_adapter.py`;
  `diffusion_state_v2` now reaches `GroupSnapshot` from persisted
  rows. (Was the cause of one pre-existing test failure.)
* Aligned `transition_version` test in `tests/test_schema.py` with
  the current `transitions-v2` schema default. (Was the other
  pre-existing failure.)
* Added `--as-of` to `scripts/audit_price_basis.py` so the report
  records the requested as-of date, matching the runbook CLI.
* Added a deterministic synthetic-market harness
  (`tests/synthetic_market.py`) with seven scenarios A–G (Healthy,
  Narrow, Early Recovery, Deterioration, Noisy Micro, Missing Data,
  Corporate Action Shock) and 16 golden regression tests.
* Added a no-look-ahead regression on synthetic history
  (`tests/test_no_lookahead_synthetic.py`) covering persistence,
  materiality, and the intelligence contract.
* Added a group-size diffusion sensitivity script
  (`scripts/audit_group_size_diffusion.py`) and four
  guardrail tests across group sizes 3, 4, 5, 7, 10, 20, 40.
* Added negative-group and one-missing-stock concentration tests so
  the absolute-move / signed-attribution split is exercised at the
  boundary, not just on equal-magnitude happy paths.
* Added missing-data breadth tests (one missing, 50% missing, all
  missing, stale, new listing, mixed benchmark) directly under
  scenario F and in the existing `test_breadth.py`.
* Confirmed every existing live-key script and the live-key runbook
  remain in sync; the `LIVE_SECTORS_RUNBOOK.md` and
  `scripts/audit_price_basis.py` now share an explicit `--as-of`
  surface.
* No live Sectors data was claimed. No live Sectors call was made.
  Tests still pass offline.
