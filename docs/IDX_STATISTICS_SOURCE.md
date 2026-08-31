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

## Search → crawl/retrieve → LlamaParse PDF ingest

The LlamaCloud SDK is optional so offline tests and the browser do not depend
on it. Install it only for the credentialed ingest command:

```bash
.venv/bin/pip install -e '.[llama]'
```

Set `LLAMA_CLOUD_API_KEY` in the ignored local `.env` file or the shell
environment. Do not paste the key into chat, source, logs, or a commit. The
staged command below requires explicit acknowledgements for both the search
agent and the LlamaCloud upload because each is an external service boundary:

```bash
.venv/bin/python -m scripts.refresh_idx_daily_statistics \
  --discover-latest --as-of 2026-08-28 \
  --search-provider auto \
  --allow-search-live --allow-search-credit-spend \
  --target-pages 1-9 \
  --allow-cloud-upload \
  --allow-credit-spend \
  --max-estimated-credits 20000 \
  --public-output app/web/public/idx/idx_daily_statistics_latest.json \
  --raw-output data/raw/llamaparse/ds_260828.response.json \
  --markdown-output data/raw/llamaparse/ds_260828.md \
  --discovery-output data/raw/idx_daily_statistics/ds_260828.discovery.json
```

The production path is explicit: the search agent discovers the release,
Tavily crawls the official statistics index (or You.com uses its bounded
contents retrieval), the project downloads and verifies the PDF locally, and
only then uploads the local file to LlamaParse. Search/crawl text is discovery
evidence only and never becomes a numeric metric.

The default target is `1-2` because the current release places the IHSG card
on parsed page 1 and the Net Foreign/Fundamental cards on parsed page 2. Use
`1-9` for the complete current PDF. The client-side estimate is a guardrail,
not a guarantee of billing; the response's usage block is retained when the
provider returns it. A failed search, retrieval, parse, or reconciliation
writes no normalized or public artifact. The retrieved PDF and discovery
sidecar remain ignored raw audit files.

When the IDX page exposes the PDF only after a browser session completes its
JS/Cloudflare challenge, save that official download locally and use the
explicit browser handoff. Search and crawl still run first; the handoff only
supplies the asset URL and local bytes that the dynamic page hid from the
agent APIs:

```bash
.venv/bin/python -m scripts.refresh_idx_daily_statistics \
  --discover-latest --as-of 2026-08-28 --search-provider you \
  --allow-search-live --allow-search-credit-spend \
  --resolved-pdf-url https://www.idx.co.id/Media/liskz5kp/ds_260828.pdf \
  --retrieved-pdf-file /path/to/browser/ds_260828.pdf \
  --target-pages 1-9 --allow-cloud-upload --allow-credit-spend
```

The handoff is accepted only when the URL is an HTTPS IDX PDF with a
date-matching release identifier and the local file begins with the PDF magic
header. No search snippet or crawl text is promoted to a metric.

If a LlamaParse job completes but the local reducer needs a layout fix, use
`--reuse-job-id` with the same discovery/provenance arguments. This performs a
read-only `parsing.get`, re-runs the reducer, and writes the artifact without
creating or billing a second parse job:

```bash
.venv/bin/python -m scripts.refresh_idx_daily_statistics \
  --discover-latest --as-of 2026-08-28 --search-provider you \
  --allow-search-live --allow-search-credit-spend \
  --resolved-pdf-url https://www.idx.co.id/Media/liskz5kp/ds_260828.pdf \
  --retrieved-pdf-file data/raw/idx_daily_statistics/ds_260828.pdf \
  --reuse-job-id pjb-<completed-job-id> --target-pages 1-9 \
  --public-output app/web/public/idx/idx_daily_statistics_latest.json
```

The SDK currently follows the LlamaParse v2 flow: upload the locally retrieved
file, create a bounded Parse job, request markdown/items/metadata/usage, and
reduce the result locally. The request also asks for spatial text and
granular line/cell boxes so a future adapter can ground values to the PDF
without changing the current contract. Direct `--source-url` remains a
backward-compatible diagnostic path, but it may fail when LlamaCloud cannot
fetch IDX directly; the staged pipeline uses local retrieval to avoid that
anti-bot boundary.
