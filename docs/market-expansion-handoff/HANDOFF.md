# Whole-market expansion — implementation in progress

Target: all seven browser requests, end-of-day observations, whole-market
analytics, expanded sourced catalogs, and the full official ownership register.
This document records completed work and remaining acceptance gates; it does
not certify the whole feature set as complete.

## Source foundation

- `config/universe_market.yaml` is generated from the official October 2 Stock
  Summary and the previously captured August 27 classification registry.
  Classification dates remain explicit; no live Sectors requests were made.
- Official workbook: 963 securities; 962 stock codes requested for history.
  GOTOM is explicitly labelled as multiple-voting shares by the workbook and
  remains visible in listing evidence, outside the tradable stock-history lane.
- Official daily observations: 829 traded stocks, 332 advancers, 140 flat,
  357 decliners. Foreign Buy/Sell are share quantities, never rupiah estimates.
- Public-history acquisition: 962 requested, 921 downloaded, 41 unavailable,
  176,554 rows, 188 benchmark sessions. The existing refresh completeness gate
  returned exit 2; this is recorded rather than presented as a clean refresh.
- Official validation of fetched history: 920 latest prices matched exactly;
  FASW conflicted (Yahoo 5312.49707 versus official 5275). The raw panel and
  its FAIL report remain immutable. No quote was overwritten or reconstructed.
- `scripts/quarantine_public_panel.py` creates a separate derived panel excluding
  the entire conflicting history, retaining upstream hashes, acquisition counts,
  and the failed comparison. Independent validation must pass before publication.
- Derived panel: 920 observed securities, 41 acquisition failures, one validation
  quarantine. All 962 requested securities remain accounted for. Its manifest
  does not claim all-market history completeness.
- Snapshot builds accept an injected universe and separate ID prefix/root. New
  bundles bind universe and methodology hashes in addition to panel hashes.
  A changed input contract refuses reuse. Historical default bundles remain intact.
- The five candidate dates built successfully individually, but the chain gate
  correctly failed: September 4–25 share cohort hash `30ecd1cf05039569` (755
  eligible securities); October 2 has `240b98cb52d5a2d3` (760). Historical
  transitions must remain segmented. Do not publish this as one comparable chain.

Local artifacts (ignored, reproducible from the source cache):

- `data/raw/public/market_panel_2025-12-15_2026-10-02/`: original fetch.
- `data/normalized/market_panel_validation.json`: original FAIL report.
- `data/normalized/market_validated_panel_2026-10-02/`: quarantined replay input.
- `data/normalized/market_validated_panel_validation.json`: independent validation.
- `data/normalized/market_daily_2026-10-02.json`: official daily observations.
- `data/normalized/market_snapshots/`: separately versioned candidate chain.

## Product acceptance checklist

| Request | Current state | Required evidence before DONE |
|---|---|---|
| Readable labels | Catalog/detail raw IDs removed from visible copy | Browser verification; canonical links still work |
| Overview chart and movers | Source data prepared; UI pending | Raw benchmark history, daily breadth, clearly labelled stock movers, gated index attribution |
| Stock heatmap | Pending | Market/Konglo/Theme selection, Daily/Weekly, sizing, accessible missing-data list, drill-down |
| Konglo expansion | Pending | Dated documented memberships/control links, expanded price coverage, actual eligibility counts |
| Themes expansion | Pending | Explicit inclusion rules, sourced business activities, expanded members, no forced reference count |
| Foreign flow | Pending | Official daily net/cumulative rupiah chart, comparable period coverage, shares kept distinct |
| Ownership | Official releases inspected; ingestion/UI pending | Full register, names/shares/percentages, threshold-aware comparisons, documented control graph |

## Boundaries and remaining checks

- Active preview remains the previously validated 54-stock snapshot until the
  expanded export, UI, integrity checks, and browser checks are complete.
- Never compare old and expanded cohorts, forge hash parity, backdate ownership
  evidence, or label partial histories as a complete market panel.
- TradingView widgets list IDX end-of-day data and do not accept our own data.
  Use the installed chart library for custom groups and official foreign flow.
- Full regression suite and real fresh-clone run, typecheck/build, four viewport
  browser checks, source manifests, and working-tree drift checks remain delivery
  gates. Tests must not read ignored artifacts or write into served directories.
- Commit locally; no push or deployment. Quad remains retired; Sectors HOLD.

## Foundation verification

- Full working-tree suite: 796 passed, zero skipped; two existing deprecation
  warnings, working-tree guard silent.
- Frontend typecheck and build pass; existing Vite configuration/chunk advisories
  remain. No unrelated configuration refactor was performed.
- Independently revalidated derived panel: all benchmark, latest official-close,
  integrity, and population-accounting checks PASS. The original failed report
  and tracked validation fixture are preserved.
- Browser: Themes catalog checked at 1440/1368/768/390, no visible underscores
  or horizontal overflow. Opening Coal & energy retains its canonical group URL
  and renders the detail correctly. Broader feature QA remains pending.
