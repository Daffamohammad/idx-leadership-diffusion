# IDX Statistics Source Contract

## Decision

The IDX statistics surfaces are usable, but they are two different source
shapes and must not be treated as one undifferentiated search result:

| Surface | What it provides | Parser | Product status |
| --- | --- | --- | --- |
| [Statistics index](https://www.idx.co.id/id/data-pasar/laporan-statistik/statistik/) | Dated Daily Statistics PDF links | `parse_idx_statistics_listing_html` | Link discovery is implemented |
| [July 2026 daily trading by type of investor](https://www.idx.co.id/id/data-pasar/laporan-statistik/digital-statistic/monthly/equity-trading-by-investor/table-daily-trading-by-type-of-investor?filter=eyJ5ZWFyIjoiMjAyNiIsIm1vbnRoIjoiNyIsInF1YXJ0ZXIiOjAsInR5cGUiOiJtb250aGx5In0%3D) | 23 daily rows in Foreign Selling and Domestic Selling tables | `parse_idx_monthly_investor_html` | Integrated as real market-level release |
| Daily Statistics PDF contents | Daily tiles such as Today/YTD net foreign and Market PER/PBV | Dedicated PDF parser required | Static/unavailable until a PDF fixture and parser pass |

## Why a parser is required

The search agent can discover the official URL and help identify the relevant
release. It is not a reliable numeric extraction layer. The monthly page has
structured HTML tables, so the parser:

1. selects both cross-investor tables by their published headers;
2. parses and aligns every trading date;
3. derives market-level net foreign flow as domestic sells to foreign minus
   foreign sells to domestic;
4. reconciles the daily sums with each official Total row; and
5. fails closed without writing an artifact when a table, date, or total is
   incomplete.

The PDF index parser only discovers PDF links. It does not infer PDF values,
and screenshot text is not persisted as data. This keeps the screenshot-style
fundamental cards separate until their source layout has a regression fixture.

## Current artifact

The validated July release is pinned at
`app/web/public/idx/idx_investor_trading_2026-07.json`. It contains:

- 23 trading-day rows;
- reconciled cross-investor components and net foreign totals;
- the exact official URL and parser provenance; and
- an explicit limitation that the release is market-level, not per-ticker or
  per-group ownership flow.

The web application loads this artifact as an optional evidence lane. If it is
missing, the core snapshot still loads and the release section says that the
official release is unavailable; it never falls back to search snippets or
values from the screenshot.

## Refresh

Use the offline path when a rendered HTML page has been saved locally:

```bash
.venv/bin/python -m scripts.refresh_idx_statistics \
  --year 2026 --month 7 \
  --html-file /path/to/official-idx-table.html \
  --output /path/to/idx_investor_trading_2026-07.json
```

The live path uses the official IDX URL directly and does not accept a search
provider as a fallback. A local HTTP 403, DNS failure, or incomplete response
is a blocker report—not permission to substitute another dataset.
