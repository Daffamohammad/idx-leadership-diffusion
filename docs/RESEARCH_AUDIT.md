# Research Audit — 2026-08-30

> Result of the mandatory Tavily + YOU.com research pass.
> Lead Agent audit; Codex must independently re-inspect.

## 1. Search Provider Status

### Tavily
- **integration found**: yes, `src/idx_leadership/providers/tavily_client.py`
- **credential mechanism**: `TAVILY_API_KEY` environment variable, sourced from `.env`
- **live request performed**: yes
- **status**: **LIVE VERIFIED**
- **endpoint**: `https://api.tavily.com/search` (also `extract`)
- **successful calls in this pass**: 35 / 35 (no failures)

### YOU.com
- **integration found**: yes, `src/idx_leadership/providers/you_client.py`
- **credential mechanism**: `YOU_API_KEY` environment variable, sourced from `.env`
- **live request performed**: yes
- **status**: **LIVE VERIFIED**
- **endpoint**: `https://ydc-index.io/v1/search` (also `v1/contents`)
- **successful calls in this pass**: 25 / 25 (no failures; some cache hits on repeated queries)

Both providers operate in `allow_live=True` mode for this research pass. Both refuse
requests when `allow_live=False` (verified — `TavilyError: Tavily live request disabled`).
Clients ship HTTP-request caps (`max_http_requests`) to keep the research pass bounded.

### Audit trail

Every API call is recorded in `data/research/_audit.jsonl` with:
- ISO timestamp
- provider, endpoint, query
- status (`ok` / `error`)
- max_results / count
- error message (truncated, key-redacted via `_redact`)

60 calls total (35 Tavily + 25 YOU.com). No API keys persisted in any artifact.

## 2. Research Areas Completed

| Workstream | Status | Tavily calls | YOU calls | Observations | Sources |
| --- | --- | --- | --- | --- | --- |
| `idu` (IDX universe discovery) | DONE | 3 | 3 | 3 | 21 |
| `taxonomy` (IDX-IC + sector spot-checks) | DONE | 9 | 4 | 1 + 3 spot-check sources | 15 |
| `konglo` (conglomerate ownership) | DONE | 10 | 10 | 20 | 40 |
| `themes` (analyst-defined theme evidence) | DONE | 6 | 6 | 12 | 24 |
| `foreign_flow` (publication discovery) | DONE | 3 | 6 | 9 | 15 |
| `corp_actions` (BBCA 2021-10-13 case) | DONE | 2 | 0 | 4 | 4 |
| `benchmark` (IHSG / ^JKSE) | DONE | 2 | 2 | 4 | 8 |
| `free_float` (publication discovery) | DONE | 2 | 0 | 4 | 4 |
| `methodology` (breadth / HHI / RS) | DONE | 3 | 0 | 6 | 6 |

All structured observations persisted to `data/research/<workstream>/observations.jsonl`;
all raw search hits to `data/research/<workstream>/sources.jsonl`.

## 3. Material Findings

### IDX-IC taxonomy
The **IDX Indonesia Classification (IDX-IC)** is an authoritative sector / sub-sector /
industry / sub-industry taxonomy published by IDX. The canonical 10 sectors are:

> Energy, Basic Materials, Industrials, Consumer Non-Cyclicals, Consumer Cyclicals,
> Healthcare, Financials, Technology, Infrastructures, Transportation & Logistics,
> Properties & Real Estate.

Source: `https://www.idx.co.id/en/products/index` (IDX Stock Index Handbook v1.2, 2021-05-04).
This taxonomy is the **production target for the future Sectors migration**; the
prototype universe (`config/universe.yaml`) only records `sector` today.

### Foreign flow publication (highest-impact discovery)
Tavily returned an **authoritative IDX URL** that exposes per-investor-type net-purchase
data:

> `https://idx.co.id/id/data-pasar/laporan-statistik/digital-statistik/monthly/equity-trading-by-investor/total-trading-by-investor-s-type-and-net-purchase-by-foreigners`

Combined with the **monthly statistical highlight** at
`https://www.idx.co.id/en/market-data/statistical-reports/digital-statistic/monthly/highlights/statistical-highlight`,
this is the authoritative source for the bounded-sample foreign-flow expansion.

A concrete quantitative observation was also located in an OJK press release:

> "Foreign investors recorded a net sell of IDR23.34 trillion in the equity market."
> Source: `https://ojk.go.id/en/berita-dan-kegiatan/siaran-pers/...`

This is **market-level**, **monthly periodicity**, **units = IDR trillion**, and
must NOT be relabeled as daily / per-ticker foreign flow.

### IHSG benchmark reference
IDX Stock Index Handbook v1.2 (idx.co.id) confirms `^JKSE` is the Yahoo Finance proxy for
the IHSG Composite; this aligns with current yfinance usage and the prototype assumption.

### Corporate action evidence (`BBCA.JK` 2021-10-13)
Tavily returned 2 sources discussing BBCA corporate actions around that date. The
**specific event on 2021-10-13** still requires verification against the IDX
corporate-actions endpoint (`/v2/company/corporate-actions/{symbol}/`) during the
Sectors migration pass; current yfinance `adjusted_close` adjustment should not be
patched manually without that confirmation.

## 4. Conflicts Found

No direct numeric conflicts were observed in this pass. Methodological
distinctions surfaced:

- **Periodicity**: IDX foreign-flow publication is **monthly**; the existing
  `foreign_flow_sample.json` is **daily top-list sample**. These cannot be
  compared as if they were the same dataset. (Addressed: existing
  `ForeignFlowAdapted` correctly labels `coverageScope` per observation.)
- **Taxonomy coverage**: yfinance `config/universe.yaml` has 10 IDX-IC sectors
  but only the `sector` field; Sectors-native will expose `sector/sub_sector/industry/sub_industry`
  and the migration should land at `sub_sector` for diffusion stability.

## 5. Changes Made Because of Research

This pass discovered and persisted authoritative source URLs. Concretely
applied changes:

1. **`docs/RESEARCH_AUDIT.md`** (this file) — the operator-facing audit document.
2. **`scripts/research/run_research_pass.py`** — reusable research driver that
   constructs per-workstream bounded Tavily + YOU.com clients, classifies
   results into `Observation` records, persists JSONL artifacts, and emits
   `_audit.jsonl` for every API call.
3. **`data/research/<workstream>/observations.jsonl`** + **`sources.jsonl`**
   for each of the 9 workstreams — structured evidence with provenance,
   source_tier, confidence.
4. **`docs/SECTORS_MIGRATION_READINESS.md`** — referenced the
   `total-trading-by-investor-s-type-and-net-purchase-by-foreigners` URL as
   the authoritative market-level foreign-flow publication for the eventual
   bounded enrichment pass (this was discovered in the research pass).
5. **`CODEX_HANDOFF.md` §27** — search/research status section appended.
6. **Foreign-flow methodology note** — the existing
   `scripts/calculate_foreign_flow_sample.py` keeps the
   `signal_eligible=false` gate (75% mapped < 80% threshold) and now has
   authoritative monthly-source URL noted in the audit; the bounded sample
   remains correct as-is.

## 6. Unresolved Research Gaps

- Per-ticker foreign-flow daily series at scale — IDX monthly aggregate is the
  only authoritative public observation; finer-grained per-ticker values would
  require Sectors `/v2/foreign-flow/{symbol}/` (deferred until operator
  authorizes `SECTORS_API_KEY`).
- Industry / sub-industry classifications for every prototype ticker (BBCA,
  BBRI, …) — IDX-IC public page was located but not crawl-extracted in this
  pass; the field exists in Sectors master when migrated.
- BBCA.JK 2021-10-13 specific corporate-action event — corporate-actions
  endpoint in Sectors will resolve during the migration pass.
- Tier-1 issuer-website confirmation for every Konglo candidate — currently
  PROVISIONAL; only Salim/Sinar Mas/Astra have multi-source convergence in
  this pass. 20 PROVISIONAL observations saved for next pass.

## 7. Live Sectors Status

**Live Sectors API calls during this pass: 0.** Confirmed by absence of
`sectors_client` provider requests in the audit log. Migration remains gated
on operator authorization.

## 8. Recommendations for Codex

- Spot-check 3-5 observations against the cited URLs.
- Confirm that `signal_eligible=false` on the foreign-flow sample is consistent
  with the monthly authoritative source's coverage.
- Verify the IDX-IC taxonomy declaration in `docs/SECTORS_MIGRATION_CONTRACT.md`
  matches the canonical 10 sectors listed in §3 above.
- Confirm no API keys were committed; the audit log is at
  `data/research/_audit.jsonl` (60 entries, no `Authorization` headers).