# Taxonomy Audit

> **Source:** the Sectors v2 documentation at `https://docs.sectors.app`
> (fetched 2026-08-27) and the fixture taxonomy in
> `tests/fixtures/taxonomy.csv`. The Sectors taxonomy is the
> authoritative one (`sector`, `sub_sector`, `industry`, `sub_industry`).

## 1. Layers in the Sectors v2 taxonomy

| Level | Slug | Field on `/v2/companies/` | Drilldown via | Documented example |
| --- | --- | --- | --- | --- |
| 1 | `sector` | `sector` | `/v2/free-float/?sector=…` | `Financials`, `Healthcare` |
| 2 | `sub_sector` | `sub_sector` | `/v2/free-float/?sub_sector=…` | `Banks`, `Food-Beverage` |
| 3 | `industry` | `industry` | `/v2/free-float/?industry=…` | `Oil-Gas`, `Banks` |
| 4 | `sub_industry` | `sub_industry` | `/v2/free-float/?sub_industry=…` | `Coal-Production`, `Gold` |

The free-float endpoint also accepts these slugs, which proves they
are valid identifiers; the screener returns them per-company.

## 2. Group-size observation

| Level | Median (this fixture, n=10) | Decision |
| --- | --- | --- |
| sector | ~3 stocks | too coarse on the prototype; on the **real IDX** the Sectors docs list `942` companies; sector-level grouping is meaningful at market scale. |
| sub_sector | ~3 | usable; on the real IDX, sub_sectors group ~10–40 names each. |
| industry | ~1 | **too fragmented on a 10-ticker fixture; usable on the real IDX but the engine must report the sample size.** |
| sub_industry | 1 | **too fragmented; do not use as the primary view even on the real IDX.** |

We commit to driving the **main view** from the **subsector level**
because: (a) it has enough constituents for the diffusion v2
group-size-aware rule to fire reliably; (b) it matches Sectors'
documented examples; and (c) the sector-level is preserved for the
`Overview` view, while subsector and finer are exposed under
`Group Explorer` only.

## 3. Why the `subindustry` level is unsuitable for the main view

A subsector with 2 stocks is too small for the diffusion rule.
The 5D / 20D / 60D breadth is dominated by one stock; the
`±10pp` rule is meaningless, and even the v2 group-size-aware rule
gives `BROADENING_FRAGILE` for every move. Documenting this is in
`docs/METHODOLOGY.md` §11.

## 4. Cross-validation with the prototype

The fixture `config/universe.yaml` already uses
`{sectors, sub_sectors}` — the prototype coarse taxonomy. The
Sectors fields `sector` and `sub_sector` are an **authoritative
refinement** of the same idea. The migration plan is:

1. Replace the prototype `sectors` field in `universe.yaml` with the
   Sectors `sector` slug.
2. Replace the prototype `sub_sectors` field with the Sectors
   `sub_sector` slug.
3. Map `industry` / `sub_industry` only when the Sectors dataset
   confirms a non-null value.

Until Sectors data is available live, the fixture drives the
prototype.

## 5. Open issues

| Issue | Action |
| --- | --- |
| Some Sectors tickers do not have `sub_industry` set. | Treat as missing; exclude from sub-industry-level analysis. |
| The same company may appear under multiple `tags` (analyst sentiment). | Keep tags as supplementary metadata; do not use them as a taxonomy level. |
| The screener's `where=…` filter is a SQL-like DSL — capability interfaces accept pre-parsed values. | The SectorsProvider normalizer only returns a single canonical `sector` per row, so the engine never needs to parse the DSL. |
