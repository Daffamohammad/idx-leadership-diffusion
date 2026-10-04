# Whole-market expansion — delivered locally

All seven browser requests are implemented. The preview at
`http://localhost:4173/overview` selects `snap_public_market_2026-10-02`, dated
2 October 2026. End-of-day observations remain explicit. No push or deployment.
Quad stays retired; Sectors remains HOLD. No paid calls or live Sectors calls
were made for this expansion.

## Delivered behavior

| Request | Delivered result |
|---|---|
| Readable labels | Human-readable catalog and detail labels; internal IDs and canonical URLs retained. No visible underscore codes in the six reviewed market pages. |
| Overview chart and movers | Real IHSG closes, chart-period controls, official daily breadth, and index-point contributions that reconcile to the session move. |
| Stock heatmap | Market / Konglo / Themes, official Daily and five-session Weekly returns, listed-share market-cap sizing, group selection, search, ticker drill-down and a paginated accessible table. |
| Konglo expansion | 22 curated corporate / named-holder portfolios, 64 memberships and 59 dated holding edges. Exact named positions of at least 20%, plus explicitly named listed parents; issuer-backed control is separately labelled. |
| Themes expansion | 102 business-activity groups with 962 memberships. Inclusion is an exact captured subindustry match, dated 27 August 2026. No inferred revenue exposure or forced reference-site count. |
| Foreign flow | 66 consecutive official daily observations, July 1–October 2. Initial 3M chart contains 65 sessions from July 2; 1M is also available. Daily net and within-period cumulative rupiah flow use separate axes. |
| Ownership | Full public 1% and 5% registers; Overview / Stocks / Investors / Groups / Changes, exact-name search, named corporate connections and separately dated issuer control statements. |

The installed Recharts library renders custom data. A TradingView logo on a
reference site does not establish that its data is a free widget. The official
[widget FAQ](https://www.tradingview.com/widget-docs/faq/data/) says widgets
cannot receive our own data; custom IDX foreign flow and portfolio membership
therefore use our sourced assets. No new frontend dependency was added.
The `official` Python extra declares the XLSX/PDF parsers required for ingestion;
regression tests do not require those optional parsers.

## Source and integrity evidence

`SOURCE_MANIFEST.json` binds served asset hashes, source workbook/PDF hashes,
raw FAIL and derived PASS reports, and independent benchmark comparisons.
`BROWSER_QA.json` records the final 24 route/viewport observations and observed
resource URLs. Both are tracked and available in a clean clone.

- Official October 2 Stock Summary: 963 securities, 962 common-stock codes and
  GOTOM multiple-voting shares. The latter remains in listing evidence, outside
  the stock-history request lane. Daily breadth is 332 up / 140 flat / 357 down
  among 829 traded stocks. Untraded unchanged quotes are labelled explicitly.
- Public history: 962 requested, 921 downloaded, 41 acquisition failures.
  The original refresh returned exit 2. It is not reported as complete.
  FASW's Yahoo close (5312.49707) conflicted with the official close (5275).
  Its entire history is quarantined in a separate derived panel. Raw prices
  and the original FAIL report were preserved; no price was substituted.
- Derived panel: 920 histories, 176,357 price rows, 188 benchmark sessions,
  41 failures and one quarantine. Latest closes for all 920 retained stocks
  match the official workbook exactly. The separate validator returns PASS.
- Benchmark: the workbook validates 164 sessions; the 66 downloaded daily PDFs
  overlap that period and extend coverage to all 188 distinct benchmark dates.
  Maximum PDF difference is 0.000230469 index points, within the 0.01 tolerance.
  Three PDFs have no separately extracted printed close; their official
  previous level plus printed change is checked instead. Their dates are named
  in the source manifest rather than replaced by zero.
- Index attribution: 918 positive official index-share weights; zero weights
  remain zero, not missing. The fixed-share calculation reconciles within
  0.001 index points. Missing prices/weights or a failed reconciliation suppress
  point attribution. This calculation is certified for this session only.
- Whole-market sector policy: 760 eligible candidates; 202 excluded (201 board
  exclusions, one insufficient-history exclusion). There are 758 acquired
  eligible constituents and 757 fully observed eligible feature rows. Display
  coverage and signal-policy eligibility are separate.
- Expanded catalog calculations bind the same eligible ticker-set hash
  `240b98cb52d5a2d3` and five-member confirmation floor. All memberships remain
  visible even if price history or signal eligibility is absent. Themes have
  758 return-eligible memberships; Konglo has 61 across 64 memberships.
- Weekly stock returns require every one of six session closes: 920 available,
  42 unavailable. Official Daily observations exist for all 962 stock codes.
  FASW's official daily quote is usable while its quarantined weekly history
  remains unavailable.
- Foreign Buy/Sell workbook columns are share quantities. They are never
  multiplied by a closing price to manufacture rupiah flow. The chart uses the
  official PDF NET FOREIGN card, covering regular, cash and negotiated markets.
  This scope can differ from a reference site's market-flow scope.
- Foreign PDFs are rounded to 0.01 billion IDR. Consecutive YTD changes agree
  within the three-value rounding tolerance. All 23 July and 19 August sessions
  also match exact official monthly rupiah totals within 5 million IDR.
  The 3M period sums to −8.36947T IDR; 1M sums to −13.78606T IDR. Longer periods
  remain disabled until all constituent sessions are validated.

## Ownership interpretation

- 1% register: September 30, 7,154 positions across 961 issuers, 5,166 distinct
  published names. Previous release: August 31, 7,158 rows. Names are not unique
  SID identities. Same-name ambiguities are excluded from monthly matching.
- 5% register: October 1, 1,915 investor blocks across 840 issuers, with dated
  September 30 comparative columns. Published combined investor totals are used
  once per block, never summed again for each custody account. Addresses and
  account identifiers are not exported.
- 76 blocks contain custody-account cells that do not reconcile to the published
  investor total. Their published totals are retained and each block is flagged,
  with a global explanation in the 5% view. No scale correction is invented.
- The 1% release labels foreign positions `F`; the 5% release uses `A`. Both
  render as Foreign, while original source codes remain in evidence.
- 1,837 comparable-name disclosure changes: 500 entries, 504 exits, 389 increases,
  419 decreases and 25 percentage changes. An entry/exit can be a threshold
  crossing; undisclosed shares stay null. No purchase/sale is inferred.
  A 1e-9 percentage-point tolerance removes Excel floating-point representation
  noise without erasing real reported percentage changes.
- Holding percentage is not voting-right percentage or legal control. Exactly
  two connection claims have separate issuer control evidence: Barito Pacific
  → Chandra Asri (March 31, 2026 issuer statement), and Dwimuria → BCA
  (December 31, 2025 issuer ownership statement). BCA's issuer-named ultimate
  controllers are shown with the source date, separate from September holdings.
- The portfolios are a documented holdings lens, not a complete beneficial-owner
  registry. Shared directors, similar names and an ownership percentage alone
  never establish an edge or control claim.
- The referenced free-float site is a separate March 2026 screening. It does not
  supply these full named-holder registers or establish current free float.

## Historical boundaries

The two earlier curated snapshots remain indexed and byte-identical, including
`SECTORS_LIVE` evidence and the validated 54-stock public bundle. The expanded
cohort receives a new ID; it is never substituted for those historical bundles.

The four September candidate snapshots have a 755-stock cohort hash
`30ecd1cf05039569`; October 2 has 760 stocks and a different hash. They are not
one comparable chain. Their current-market-cap metadata also does not certify
point-in-time historical weights. Those candidates are not published as a
validated whole-market trajectory. Current expanded rotation Daily/Weekly
trails remain unavailable, while the earlier 54-stock bundle's real trails
are preserved. Heatmap Daily/Weekly stock returns are independently available.

Ownership evidence dated September 30 cannot be backdated into September 25
portfolios. Current catalog diffusion has no comparable prior; confirmation,
leadership, diffusion and concentration remain distinct gates. Small groups
remain UNCONFIRMED even when descriptive returns and members are displayed.

## Operator runbook

Install the repository normally with `dev` and, for source ingestion, `official`
extras. New UI playback uses tracked exports and needs no raw cache. Source
rebuilds require the actual official downloads and price panel. Download official
files through permitted interfaces; retain hashes and acquisition failures.
No WAF bypass, paid provider call or Sectors request is part of this runbook.

1. Prepare `config/universe_market.yaml` and the official daily observation JSON
   with `prepare_market_universe.py`, passing the official workbook, captured
   classification bundle, as-of and both output paths.
2. Fetch the separately rooted public panel. Preserve its original refresh and
   validator verdicts. Use `quarantine_public_panel.py` only for isolated,
   date-aligned official quote conflicts; independently validate the new panel
   with `validate_public_panel.py --no-publish-fixture`. Never overwrite the
   previously committed small-panel validation fixture with this cohort.
3. Build only the new current snapshot with `build_snapshot_chain.py`, the
   validated panel, `--universe config/universe_market.yaml`, separate prefix
   `--snapshot-prefix snap_public_market`, `--asofs 2026-10-02`, and separate
   snapshot root. Re-fetching changes provenance; reuse must fail with exit 2.
   Rebuild the intended chain with `--force-rebuild`, never hand-delete bundles
   to conceal the input-contract mismatch.
4. Normalize current, prior and 5% workbooks with `export_ownership.py`; supply
   each dated source URL and each release/comparative date explicitly. Generate
   catalogs and holding edges using `prepare_market_catalogs.py` with the tracked
   exact-holder rules. The inputs are hash-bound in generated configurations.
5. Export official flow using `export_foreign_history.py`: `--pdf-root`, actual
   `--source-list`, `--benchmark`, `--monthly` comparison JSON files and `--out`.
   The source list is reconstructible from the 66 URLs in `SOURCE_MANIFEST.json`.
   Missing sessions or YTD discontinuities refuse export.
6. Export market observations with `export_market_workspace.py`, passing daily,
   validated panel, its current PASS report, matching snapshot directory,
   universe and ownership edges. It independently replays the eligibility hash
   and checks current panel hashes and official date alignment.
7. Bind taxonomy views to that workspace:

   ```sh
   python scripts/build_taxonomy_views.py \
     --snapshot-root data/normalized/market_snapshots \
     --snapshot-id snap_public_market_2026-10-02 \
     --config-dir config/market_expansion --universe config/universe_market.yaml \
     --eligibility-workspace data/normalized/market_workspace_2026-10-02.json \
     --foreign-flow /tmp/no-foreign-sample.json --out-dir data/derived/taxonomy_views
   ```

8. Publish the three workspace inputs with `publish_market_workspace.py`.
   Schemas, dates, continuity, ownership dates and nonfinite values are gated
   before writes. Asset files are replaced individually; index is replaced last.
   The frontend verifies asset SHA-256, snapshot identity and release dates.
   An old-index/new-file race fails closed instead of displaying wrong evidence.
9. Export with `export_snapshot_json.py --taxonomy-config-dir
   config/market_expansion --compact` and the separate snapshot root/ID. Compact
   JSON avoids about 15 MB of whitespace; the expanded bundle still contains
   roughly 25 MB of real ticker history. Use the guarded index curator with
   explicit IDs for the three intended entries; rejected IDs must leave the
   existing index byte-identical.
10. Verify full tests, typecheck/build, source hashes, browser interactions at
    four viewport widths, and a real clean clone before committing locally.
    Tests generate source fixtures under `tmp_path`; tracked export integration
    tests read only committed payloads. No test writes to served directories.

## Verification

- Working-tree suite: **811 passed, zero skipped**, two existing Sectors
  deprecation warnings. Working-tree guard silent.
- Frontend typecheck and build pass. The pre-existing Vite configuration/chunk
  advisories remain; no unrelated build-configuration refactor was performed.
- Browser: six market routes × 1440/1368/768/390 = 24 loaded page checks;
  zero body overflow, visible underscore codes, console warnings/errors or
  observed Sectors resources. Filters, Weekly unavailable values, theme and
  portfolio selection, ticker drill-down, period gates, ownership register
  toggles and the dated control graph were exercised, beyond screenshot checks.
- Screenshots are saved in the task's visualization directory: overview,
  heatmap, foreign flow, ownership and the mobile ownership graph.
- Actual clone of local implementation commit `6752b4b`: **811 passed, zero
  skipped**, exit 0, two existing warnings, 25.22 seconds. Its Git tree remained
  clean afterward. The raw directory contained only tracked `.gitkeep`; no
  ignored source cache, built snapshot input, or frontend `node_modules` was
  present. Package import and `project_root()` both resolved inside the clone,
  preventing contamination by the original editable installation.

The implementation is committed locally as `6752b4b`, following the source
foundation `6cb2e11`. This verification record is a documentation-only follow-up.

To reproduce from the repository root, choose a fresh temporary directory and
use the existing test environment with the clone's source path explicitly:

```sh
verification_python="$PWD/.venv/bin/python"
git clone --no-hardlinks . /tmp/idx-market-verification
cd /tmp/idx-market-verification
PYTHONPATH="$PWD/src:$PWD" "$verification_python" -c \
  'from idx_leadership.utils import project_root; print(project_root())'
PYTHONPATH="$PWD/src:$PWD" "$verification_python" -m pytest -q
git status --porcelain
```

The printed project root must be the new clone, and the final status must be
empty. Do not claim a clean-clone pass if imports point back to the original
checkout. Source ingestion is a separate check requiring the official caches
and optional parsers; UI playback and regression tests use tracked artifacts.
