# Hybrid Product Model

## Decision

The hackathon deliverable is a focused hybrid research product. It demonstrates
the core market-intelligence workflow with real persisted market observations,
then uses static research layers where a full live contract is not yet
available. This is a product boundary, not a hidden fallback.

The external hackathon rules remain authoritative. No event brief or judging
rubric is committed in this repository that requires a complete production
terminal, full IDX coverage, or a live provider for every section.

## Section contract

| Lane | Sections | What is real | What is static or bounded |
| --- | --- | --- | --- |
| Real snapshot | Overview, Sector heatmap, Leadership Map, Groups, Ticker Analysis, What Changed | Returns, breadth, leadership, concentration, constituents, quality, coverage, and provenance from the persisted snapshot | The current snapshot is still partial (`500/962` discovered securities) and has no compatible prior, so change comparison remains unavailable. |
| Source-backed sample | Foreign Flow | Six market dates and reported top-buy/top-sell company observations retained with source provenance | It is a top-list sample, not a full-universe feed; it is not eligible to confirm leadership or diffusion. |
| Static research lens | Konglo Map, Themes Map, Konglo/Themes detail, Themes Explorer | Aggregate performance and breadth are calculated from the current snapshot when available | Membership definitions come from analyst configuration, are not official IDX taxonomy, and remain static until the definition is reviewed and rebuilt. |
| Static context | Research Events, Tavily and You.com context | Source links and dated observations are retained in the snapshot | Context is descriptive only and cannot create or alter a quantitative signal. |
| Illustrative | Public Home and chart demo | Product interaction and information architecture | Visual examples and copy are illustrative, not market observations. |

## UI language

Every lane uses a visible evidence badge:

- `Real snapshot` means persisted quantitative market observations.
- `Source-backed sample` means real but bounded observations.
- `Static research lens` means analyst-defined configuration with snapshot aggregates where available.
- `Static context` means descriptive context frozen with the snapshot.

The product must not call the Konglo or Themes definitions live, official, or
fully verified. It must not display a sample foreign-flow observation as a
full-market confirmation signal. Data gaps and missing comparable history stay
visible.

## Demo narrative

1. Start on Overview: show the real Sector heatmap and its current coverage.
2. Open Leadership Map or a group detail: show the persisted quantitative path.
3. Open Foreign Flow: explain the bounded sample and its provenance.
4. Open Konglo or Themes: explain that these are static research lenses over current snapshot aggregates.
5. Open Methodology: use the evidence model and data-status tables to show exactly where the product is real, bounded, or static.

## Refresh boundary

The live Sectors refresh remains opt-in and fail-closed. If full-live preflight,
credentials, provider checks, or credit limits fail, no snapshot/export/index
is written. The current blocker and next action are recorded in
[`FULL_LIVE_RUNBOOK.md`](FULL_LIVE_RUNBOOK.md).
