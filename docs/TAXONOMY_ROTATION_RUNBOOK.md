# Taxonomy, Constituent, and Rotation Runbook

Updated 2026-08-31. This is the operating contract for the hybrid hackathon
product. It keeps the market-signal lane useful while making the boundaries of
the analyst-defined research lenses explicit.

## Product contract

| Lane | Sections | Evidence contract |
| --- | --- | --- |
| Real snapshot | Overview, Sector heatmap, Leadership Map, Groups, Ticker Analysis, What Changed | Persisted market observations, benchmark, coverage, and data-quality status from the snapshot bundle. |
| Official IDX release | Overview and Methodology | IDX Digital Statistics investor-type table, parsed and reconciled at market level. |
| Source-backed sample | Foreign Flow | Bounded published top-buy / top-sell observations; not a full-universe signal. |
| Analyst-defined prototype | Konglo, Themes, and their constituent details | Membership comes from the checked-in configuration and carries membership type, confidence, source, and source date. Aggregate metrics are only calculated from persisted constituent observations. |
| Context only | Research Events and web research panels | Descriptive evidence; never used to create, confirm, or alter a quantitative signal. |

`DATA GAP`, partial coverage, and an unavailable comparable prior are product
states. They are not replaced with zeroes, a neutral phase, or a synthetic
price history.

## Official IDX source pipeline

The source roles are deliberately separated:

1. You.com/Tavily/search agent discovers official IDX URLs and release
   metadata.
2. The retriever stores a bounded artifact with source URL, release period,
   as-of date, retrieval time, parser version, hash, status, and coverage.
3. An HTML/JSON table parser reads numeric Digital Statistics tables.
4. LlamaParse is reserved for a PDF or release with layout that cannot be
   reliably read as a structured table.
5. Deterministic validation checks dates, units, totals, missing rows, numeric
   shape, reconciliation, and source completeness before promotion.
6. Only the validated artifact is allowed into a persisted snapshot.

Search snippets, crawl text, and an LLM summary are discovery/provenance
evidence, not numeric market evidence.

The registry lives in
`src/idx_leadership/providers/idx_statistics.py` and covers:

- [IDX Statistics](https://www.idx.co.id/id/data-pasar/laporan-statistik/statistik/)
  for Daily Statistics PDF discovery;
- [Daily Trading by Type of Investor](https://www.idx.co.id/id/data-pasar/laporan-statistik/digital-statistic/monthly/equity-trading-by-investor/table-daily-trading-by-type-of-investor)
  for monthly market-level foreign flow;
- [Daily IDX Indices](https://www.idx.co.id/id/data-pasar/laporan-statistik/digital-statistic/monthly/stock-price-index/daily-idx-indices)
  for benchmark/index observations;
- [Trading Summary by Industry](https://www.idx.co.id/id/data-pasar/laporan-statistik/digital-statistic/monthly/equity-trading-by-industry/trading-summary-by-industry-classification)
  for industry summary;
- [Digital Statistics](https://www.idx.co.id/id/data-pasar/laporan-statistik/digital-statistic/)
  for discovery and metadata; and
- [IDX Stock Summary](https://www.idx.co.id/en/market-data/trading-summary/stock-summary)
  for a bounded manual price fallback.

The manual stock fallback is display-only until its provider mode, universe
contract, benchmark, price basis, and date contract match the analytical
snapshot. One manual close is never combined with another provider's history to
produce a return.

For the paid Sectors path, run the network-free gate first:

```bash
.venv/bin/python -m scripts.refresh_and_export --full-live
.venv/bin/python -m scripts.build_market_snapshot --preflight-only
```

The wrapper must not write a snapshot, browser export, or index when a gate
fails. The credentialed command and current credit blocker are documented in
[`FULL_LIVE_RUNBOOK.md`](FULL_LIVE_RUNBOOK.md). Credentials stay in the local
environment and are never copied into source, logs, screenshots, or commits.

## YTD contract

YTD is the return from the last common trading session of the preceding year
to the latest common trading session at or before the snapshot date. For each
group, the eligible constituent returns are equal-weighted:

```text
group_return_ytd = mean(constituent_return_ytd)
excess_return_ytd = group_return_ytd - benchmark_return_ytd
```

The benchmark is IHSG with the same dates and price basis. The persisted
payload carries `return_ytd`, `benchmark_return_ytd`, `excess_return_ytd`, and
`ytd_start_date` at the security/group boundary. A missing prior-year baseline,
end observation, or benchmark produces `Data gap`; it is not imputed.

The group detail and Master Group Table use YTD as the primary comparison.
20D and 60D remain diagnostic windows.

## Rotation contract

Rotation is a separate view at `/map`, so the existing taxonomy map keeps its
leadership/breadth meaning. The current mapping is:

- relative strength = YTD excess return versus IHSG;
- relative momentum = 20D excess return minus 60D excess return;
- `Leading` = strength ≥ 0 and momentum ≥ 0;
- `Improving` = strength < 0 and momentum ≥ 0;
- `Weakening` = strength ≥ 0 and momentum < 0; and
- `Lagging` = strength < 0 and momentum < 0.

Null strength or momentum remains `Data gap` and is shown in the table/list but
is not plotted. Without a compatible prior snapshot, the UI shows the current
phase only and does not invent a transition trail.

## Canonical navigation

All taxonomy detail links use these routes:

```text
/explorer?taxonomy=SECTOR&group=<group_id>
/explorer?taxonomy=KONGLO&group=<group_id>
/explorer?taxonomy=THEMES&group=<group_id>
```

Heatmap tiles, map bubbles, rotation rows, the accessible group lists, and the
Theme browser support click, Enter, or Space. Theme and Konglo detail pages
show aggregate metrics, YTD/20D/60D fields, breadth, concentration,
contribution rows, persisted price history when available, and membership
provenance. `EXCLUDED` membership remains visible in the evidence table but is
not included in quantitative rows.

The legacy overview hash `#konglo=<group_id>` is redirected to the canonical
Konglo explorer route.

## Local launch and evidence

Start the existing local app with:

```bash
cd app/web
npm run dev -- --host 0.0.0.0 --port 5174
```

Open [http://127.0.0.1:5174/](http://127.0.0.1:5174/). Local typecheck,
production build, Python tests, and browser smoke checks are separate evidence
boundaries. Passing them does not prove live provider entitlement, credit debit,
deployment, or a successful full-universe refresh.

