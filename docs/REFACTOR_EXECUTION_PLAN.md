# IDX Leadership Diffusion — Refactor Execution Contract

## Outcome

The product has one coherent path from source discovery to interface:

`Search Agent (You.com / Tavily) → first-party source selection → Parser Agent (LlamaCloud) → deterministic reducer → persisted snapshot contract → UI display`

Search output is discovery evidence. It is never promoted directly to a numeric market or security observation.

## Work assignments

### 1. Universe and taxonomy agent

**Prompt**

> Inspect the provider security master and persist every uniquely discovered IDX listing in `security_master.json` and `listed_universe.csv`. Keep the full accessible listing separate from the bounded history sample. Use market-cap priority plus sector coverage only for the expensive history lane. Map sector, subsector, industry, and subindustry from provider fields. Map Konglo and Themes only from the explicit configuration files; leave memberships empty when no explicit row exists. Reject duplicate tickers and persist diagnostics for pagination, instrument classification, and taxonomy completeness.

**Acceptance**

- `listed_count == unique ticker count`.
- `persisted_count == discovered_count` before the snapshot is called a full accessible listing.
- `full_accessible_universe_listed` is true only after complete pagination and equal counts.
- `analysis_requested` and `analysis_status` are present for every row.
- A bounded demo never changes the full listing count.

### 2. Search agent: You.com and Tavily

**Prompt**

> Discover official IDX/OJK pages and dated releases for investor trading, foreign flow, daily statistics, broker summary, corporate actions, and taxonomy documentation. Return URLs, titles, dates, publisher, and retrieval status. Use no more than five search results and five crawl/extract candidates per bounded run. Prefer first-party domains. Do not provide a numeric value as quantitative evidence unless the selected source is subsequently downloaded or parsed by the parser agent.

**Acceptance**

- Search provenance records the provider, query, result count, selected URL, and failure reason.
- Dynamic-page discovery records only the candidate URL and retrieval state; an error or empty body never becomes a numeric observation.
- The official IDX investor-type page is a separate first-party source lane: its directly retrieved table cells are reduced by `parse_idx_monthly_investor_html`, not by a search snippet. Its dynamic-page discovery metadata remains non-quantitative.

### 3. Parser agent: LlamaCloud / LlamaParse

**Prompt**

> Parse only the selected official document and explicitly requested pages. Preserve the parser file/job id and normalized provenance as an audit sidecar; keep raw parser output local when the provider response is not suitable for the public bundle. Reduce only fields with a stable label, unit, date, and reconciliation check. Return a typed payload with parser job/file id, page range, source URL, parser version, checks, warnings, and limitations. Keep market-level flow separate from per-security flow.

**Acceptance**

- Target pages are bounded; no unbounded document parse is allowed.
- Numeric fields are rejected when labels or units are missing.
- LlamaCloud is used for selected official documents (for example, IDX Daily Statistics and OJK releases); it is not claimed as the parser for the official monthly IDX HTML table.
- The OJK June 2026 release is reduced to market context: IHSG 5,643.19, foreign equity flow net sell Rp19.63T, YTD equity flow -Rp73.61T, RNTH Rp24.19T, local ownership 59.41%, and market cap Rp9,897T.
- The parser payload explicitly says it is not per-ticker and not per-group.

### 4. Flow and transaction agent

**Prompt**

> Maintain three distinct flow lanes: the official IDX investor-type release for market totals, the bounded company-level sample for descriptive context, and any future full-universe transaction feed only after its denominator and reconciliation are proven. Preserve buy, sell, net, direction, unit, date, source locator, and mapping status. Never assign a market total to a security or group.

**Acceptance**

- Same-side investor trades remain in the gross totals.
- Net foreign equals `domestic_to_foreign - foreign_to_domestic` under the source definition. The code and reducer must not invert this direction.
- Company rows retain their original reported net value; missing buy/sell legs are not inferred.
- IDNFinancials/secondary rows retain their reported values for descriptive audit context but are emitted with `quantitative_use=false`.
- Flow context cannot alter leadership, breadth, diffusion, or concentration.

### 5. Product/interface agent

**Prompt**

> Render machine quality states as user-facing coverage language. Use “Not available”, “Ready · partial coverage”, “Outside current scope”, and “Not used by current method” where appropriate. Keep provenance visible beside official market cards, listing counts, taxonomy memberships, and sample flow. Do not expose internal enum names in the rendered UI or downloaded brief.

**Acceptance**

- The brief uses `Coverage Notes` as its display section.
- Streamlit, React, the static methodology deck, and the downloaded brief contain no legacy data-gap heading or raw status badge.
- Official market context is visibly marked market-level and separate from per-ticker/group confirmation.
- The listing registry exposes every persisted ticker with sector hierarchy and explicit Konglo/Theme membership.

## Operational gates

1. Run the live preflight before any Sectors request. The default demo plan is capped at 250 history symbols and 400 HTTP attempts.
2. Do not run the full-live path during a demo. It is a separate operator-approved path and must pass the projected-credit gate before any HTTP request.
3. Cache and reuse the bounded search/parser artifacts. A UI reload must never invoke a provider.
4. Verify the artifact chain with the offline test suite, TypeScript typecheck, production build, and a rendered-language scan.

## Current implementation boundary

The refactor is code-complete for the contracts above and includes bounded
You/Tavily discovery plus one bounded LlamaCloud parse. The legacy analytical
files inside the live bundle still contain the 500-name history sample, while
the exported `listing_registry` reads the validated 962-row capture and marks
the full accessible listing as complete. The next authorized bounded live
refresh should rewrite the native security-master sidecar with that full list,
while requesting history only for the demo sample.
