# Groundwork Audit

Self-audit before delivery. Each row links to evidence in the
repository.

| Area | Implemented | Evidence | Known limitation | Next improvement |
| --- | --- | --- | --- | --- |
| Provider abstraction | yes | `src/idx_leadership/providers/base.py`, three concrete providers (YFinance, Sectors stub, Fixture) | Sectors is a stub | P0.1 in `NEXT_ITERATION.md` |
| Price data | yes (public + fixture) | `YFinanceProvider`, `FixtureProvider`; raw cache at `data/cache/`; canonical DataFrames | No Sectors data yet | P0.2 |
| Taxonomy | partial (prototype) | `config/universe.yaml` (prototype metadata); `FixtureProvider.get_group_taxonomy` | Not authoritative Sectors | P0.3 |
| Benchmark | yes (Yahoo `^JKSE` + fixture) | `YFinanceProvider.get_benchmark_history`; fixture `benchmark.csv` | Yahoo data quality for IDX not validated at scale | P0.4 |
| Snapshots | yes | `src/idx_leadership/data/snapshots.py`; atomic per-file writes; `manifest.json` | Single-process lock not implemented | P3 operational work |
| Returns | yes | `src/idx_leadership/features/returns.py` + 11 tests | Holidays handled via trading-day walk; no native holiday calendar | Add IDX holiday calendar |
| Breadth | yes | `src/idx_leadership/features/breadth.py` + 6 tests; explicit denominators | No z-score baseline | P3.1 |
| Diffusion | yes | `src/idx_leadership/signals/diffusion.py` + 7 tests; configurable thresholds | Raw delta only; default ±10pp | P3.1 (z-score) |
| Concentration | yes | `src/idx_leadership/features/concentration.py` + 5 tests; absolute-move convention | Equal-weight only | P0.8 free-float |
| States (leadership) | yes | `src/idx_leadership/signals/leadership.py` + 8 tests; 4-state + UNCONFIRMED | Provisional thresholds; 2D classifier | P1.2 calibration |
| Transitions | yes | `src/idx_leadership/signals/transitions.py` + 9 tests; explicit categorical diffs | Materiality priority order is hand-tuned | P1.2 |
| Change digest | yes | `src/idx_leadership/signals/change_digest.py` + 1 test; machine-readable buckets | No LLM narration | P1.4 |
| Evidence objects | yes | `src/idx_leadership/evidence/builder.py` + 4 tests; structured output | Contradiction detector limited to 2 heuristics | Add more |
| Tests | yes | 92 tests across 14 files; all fixtures, no network | No property-based tests yet | Add hypothesis tests |
| Reproducibility | yes | `pyproject.toml`, `pytest`, `streamlit run`; documented commands | Single-process; not concurrent-safe | Document constraints |
| UI | yes (thin) | `app/streamlit_app.py`; 4 tabs (Overview, What Changed, Group Explorer, Method/Quality) | Plain Streamlit; no charts beyond tables | Add 1-2 simple charts |
| Documentation | yes | ARCHITECTURE, METHODOLOGY, DATA_CONTRACTS, DECISION_LOG (D001-D010), KNOWN_GAPS, SECTORS_INTEGRATION_PLAN, NEXT_ITERATION (P0-P3) | None major | Maintain on each change |
| Sectors readiness | yes (interface + stub + plan) | `SectorsProvider` + `SECTORS_INTEGRATION_PLAN.md` + 9 P0 items in `NEXT_ITERATION.md` | No live call yet | P0.1 → P0.9 |
| Point-in-time safety | yes | `tests/test_no_lookahead.py` (3 tests) covering as-of stability | None | Add more historical windows |
| Request ledger | yes | `src/idx_leadership/providers/ledger.py`; secrets redacted | Credit model not implemented | P0.7 |
| Coverage metrics | yes | `assess_quality`; fields: requested, loaded, usable, failed, benchmark_latest, latest_common, dupes, invalids, stale | No group-level coverage | Add |
| CLI | yes | 5 scripts: `refresh_public_data`, `build_snapshot`, `build_history`, `validate_data`, `export_diagnostics` | No scheduler / cron | Add |
| Configuration | yes | `config/{universe,methodology,providers}.yaml`; all thresholds in config | None | Maintain |
| Data preservation | yes | `RawCache` (TTL, JSON); per-snapshot directory; `data/normalized/diagnostics.csv` | No archive of raw API responses across versions | Add a `data/raw/<provider>/<asof>/` archive |
| Error handling | yes | Typed exceptions (`ProviderError`, `DataQualityError`, ...); UI degrades gracefully | None major | Add per-class retry policies |
| Logging | yes | `idx_leadership.utils.get_logger` / `log_event`; structured key=value; secret-redaction | None | Add log levels per module |
| Security basics | yes | Safe YAML loading; path-safe writes; no eval / no shell | None | Add Sentry/OTel later |
| Performance | acceptable | Single-threaded; fixtures run in <1s; pipeline ~0.5s for 10-ticker snapshot | No memoization across snapshots | Acceptable for groundwork |

## Acceptance criteria status

From the brief, section 71:

- [x] **Architecture:** analytical code does not directly depend on
      yfinance; provider abstraction exists; Sectors integration
      boundary is clear. ✓
- [x] **Data:** public prototype data can be fetched; raw/cache
      layer exists; normalization produces canonical tables;
      provenance is retained. ✓
- [x] **Analytics:** returns, relative perf, group aggregation,
      breadth, diffusion, concentration, provisional leadership,
      transitions, change digest. ✓
- [x] **History:** dated snapshots; previous/current comparison;
      future observations do not alter past snapshots (no-lookahead
      test passes). ✓
- [x] **Testing:** 92-test suite passes; no live API; no-lookahead
      test exists. ✓
- [x] **UI:** Overview, What Changed, Group Explorer, Method/Quality
      all work. ✓
- [x] **Documentation:** all required docs present. ✓

## Failure conditions (section 72) status

- [x] Not mostly a Streamlit dashboard — UI is one tab among many
      docs and ~2500 LoC of analytical code.
- [x] No analytical logic inside UI code (UI reads snapshot
      artifacts only).
- [x] yfinance schema does not leak — only `providers/public.py`
      imports yfinance; analytics consumes canonical DataFrames.
- [x] Tests do not require internet (FixtureProvider only).
- [x] Breadth denominator is exposed (`usable_constituents`,
      `total_constituents`, `missing_constituents`).
- [x] State thresholds are in `config/methodology.yaml`; not magic
      numbers in code.
- [x] Missing data is not silently neutralized; `UNCONFIRMED` and
      `None` are returned.
- [x] No code reused from the previous rotation project (clean-room).
- [x] README states that the prototype is partial, not full IDX.
- [x] Sectors integration has a clear plan, not a vague description.
- [x] NEXT_ITERATION is concrete with Problem / Why / Files /
      Validation / Risk per item.
- [x] Data provenance in every snapshot (manifest.json + versions).
- [x] Calculations reproducible via documented commands.
