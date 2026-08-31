# IDX Statistics Source Contract

## Decision

The IDX statistics surfaces are usable, but they are two different source
shapes and must not be treated as one undifferentiated search result:

| Surface | What it provides | Parser | Product status |
| --- | --- | --- | --- |
| [Statistics index](https://www.idx.co.id/id/data-pasar/laporan-statistik/statistik/) | Dated Daily Statistics PDF links | `parse_idx_statistics_listing_html` | Link discovery is implemented |
| [July 2026 daily trading by type of investor](https://www.idx.co.id/id/data-pasar/laporan-statistik/digital-statistic/monthly/equity-trading-by-investor/table-daily-trading-by-type-of-investor?filter=eyJ5ZWFyIjoiMjAyNiIsIm1vbnRoIjoiNyIsInF1YXJ0ZXIiOjAsInR5cGUiOiJtb250aGx5In0%3D) | 23 daily rows in Foreign Selling and Domestic Selling tables | `parse_idx_monthly_investor_html` | Integrated as real market-level release |
| Daily Statistics PDF contents | Daily tiles such as Today/YTD net foreign and Market PER/PBV | `scripts.refresh_idx_daily_statistics` + `llama_parse` reduction | Optional LlamaCloud ingest; promoted only after deterministic checks |

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

The PDF index parser only discovers PDF links. PDF values are ingested by an
explicit, bounded LlamaParse command and reduced to a small target-metrics
schema. Markdown is not treated as a database: the reducer checks the release
date, IHSG arithmetic, the four Net Foreign values and units, and both
fundamental values before writing an artifact. A raw LlamaParse response is an
optional ignored audit sidecar, not a browser payload.

The current target schema is intentionally limited to the cards required by
the product. Top-stock, index, and recapitulation tables remain available in
the raw parse sidecar for later, separately validated adapters; they are not
silently promoted into signals.

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

## LlamaParse PDF ingest

The LlamaCloud SDK is optional so offline tests and the browser do not depend
on it. Install it only for the credentialed ingest command:

```bash
.venv/bin/pip install -e '.[llama]'
```

Set `LLAMA_CLOUD_API_KEY` in the ignored local `.env` file or the shell
environment. Do not paste the key into chat, source, logs, or a commit. The
command requires two explicit acknowledgements because the public PDF is sent
to a third-party service and the request consumes account credits:

```bash
.venv/bin/python -m scripts.refresh_idx_daily_statistics \
  --pdf-file /path/to/ds_260828.pdf \
  --target-pages 1 \
  --allow-cloud-upload \
  --allow-credit-spend \
  --max-estimated-credits 20000 \
  --public-output app/web/public/idx/idx_daily_statistics_latest.json \
  --raw-output data/raw/llamaparse/ds_260828.response.json \
  --markdown-output data/raw/llamaparse/ds_260828.md
```

The default target is page 1 because the market cards are on the first page.
Use an explicit bounded range such as `1-8` when the complete PDF output is
needed. The client-side estimate is a guardrail, not a guarantee of billing;
the response's usage block is retained when the provider returns it. A failed
parse or failed reconciliation writes no normalized or public artifact.

The SDK currently follows the LlamaParse v2 flow: upload a file (or provide
an official IDX PDF URL), create a bounded Parse job, request markdown/items/
metadata/usage, and reduce the result locally. The request also asks for
spatial text and granular line/cell boxes so a future adapter can ground
values to the PDF without changing the current contract.
