# The Diffusion · 8 October 2026

The Diffusion follows leadership beneath IHSG: which sectors outperform, whether
participation is widening, and which stocks account for each reading. Open the
Dashboard at `/sectors` to explore the replay, then follow any result back to its
stocks, dates, and source.

## Coverage and dates

The active sector release covers **132 stocks across 11 IDX sectors, 12 per
sector**, ranked by market capitalization on 2 October 2026. It is the
project's research universe, not every listed company.

Raw Sectors API closes, native IHSG closes, and corporate-action data support
the sector dashboard. The replay has **21 daily and five weekly dates from
4 September through 2 October 2026**; the price history runs from 9 June through
2 October. Splits, rights issues, dividends, and other mechanical events remove
affected windows. Missing prices remain missing.

Several readings have narrower coverage. Year-to-date and company-level flow
remain tied to the original **66 stocks**. There are **23 eligible YTD stock
readings** through 2 October; company-level flow covers the original set from
5 July through 2 October. No sector reaches the five-contributor YTD threshold.

The app uses different sources for different views:

- **Sectors API:** raw stock closes, native IHSG closes, corporate-action
  information, and company-level flow for the sector dashboard.
- **Official IDX Stock Summary:** Market Movers.
- **IDX Daily Statistics:** market-level foreign-flow totals.
- **Yahoo Finance, accessed with the `yfinance` Python client:** adjusted prices
  for broader market and group comparisons. These prices have a different basis
  and coverage from the Sectors dashboard.
- **IDX and KSEI disclosures:** dated ownership registers and sourced company
  relationships. Affiliation alone does not establish legal control.
- **IDX classifications and curated themes:** the wider group maps. These are
  research baskets, not official sector indices; their constituents are applied
  retrospectively.

## Calculations and exclusions

The default map compares 60-day excess return versus IHSG with 20-day minus
60-day excess momentum. Leadership uses 20-day excess and 5-day versus 60-day
acceleration. A confirmed signal requires at least five eligible contributors.
Breadth uses the same companies at both dates, and concentration uses the actual
20-day return contributors. Action-affected and incomplete windows stay out of
calculations; the app does not fill missing prices.

## Release and rollback

- Active release: `rel-f967a4e886c4f5efe9dd32b5940a49c765c8852b56a7223f8e8f610aabafcb61`
- Active manifest SHA-256: `0a7cf1d0fa72e852b099e03281bb061ca6f3b595e8456e0393ce1f11369e0f52`
- Immediate rollback (the prior 66-stock release): `rel-64026e36d49733009fec952086fc95a3121a86efbb196b1c68d00fd6317f33d2`
- Rollback manifest SHA-256: `98e2c260c9afae07ce2b1cb5b5436cda8bbff9978a0239d809d909183ad36e4f`

The active pointer is in `app/web/public/releases/active.json`. Both packages
are retained in the repository so a deployment can serve the expanded release
and still switch back to the prior release. The production build keeps these
two packages and omits older, unreferenced release folders.

## Acquisition accounting

The expansion ledger has a hard **221-credit ceiling**: 198 planned requests
and a 23-credit retry reserve. The ledger reserved 201 credits: 198 completed
responses for the 66 additions (two price-history windows and one
corporate-action check per stock), plus three estimated credits for a
DNS-failed request across its attempts. That leaves 20 credits unreserved.
Provider billing for the DNS failure is unknown from the local receipt. No
company-flow checks used this budget. The earlier YTD ledger remains at 461 of
its separate 500-credit limit.

The expansion plan, reservation ledger, and response hashes are kept under
`data/research/acquisitions/sectors-expansion-20261008-132/`. No API credential
is stored in the release.

## Verification and media

Independent close arithmetic and count-based diffusion checks found zero
mismatches across the expanded daily and weekly readings and the 66-stock
rollback. The original YTD values are unchanged. All four expansion regressions
pass; frontend typecheck and production build pass.

The production preview passed **64 fresh route loads**: all 16 routes at four
screen sizes. The home and source wording was checked at each size; the expanded
source page and the 66-stock Dashboard and source page were also checked at all
four sizes. No route overflow or reader-facing use of the terms flagged during
review appeared. See the [browser check and screenshots](final-audit-2026-10-08/expansion-browser-qa.json).

The final videos and their scripts, captions, and checksums are in
[`media/final-2026-10-08/`](media/final-2026-10-08/):

- [30-second vertical teaser](media/final-2026-10-08/teaser-vertical-2026-10-08.mp4)
- [Three-minute YouTube walkthrough](media/final-2026-10-08/walkthrough-youtube-2026-10-08.mp4)
- [Three-minute vertical walkthrough](media/final-2026-10-08/walkthrough-reels-2026-10-08.mp4)
- [Narration and on-screen copy](media/final-2026-10-08/VIDEO_SCRIPTS.md)
- [Social post draft](media/final-2026-10-08/SOCIAL_POST_DRAFT.md)
- [Media manifest](media/final-2026-10-08/video_manifest.json)

All three MP4s include AAC voice-over narration from the scripts, with VTT and
SRT captions supplied. Their durations, formats, audio tracks, and SHA-256
hashes were checked against the manifest.

## Delivery status

The expanded release is live at [idx-leadership-diffusion.vercel.app](https://idx-leadership-diffusion.vercel.app/).
Direct visits to `/sectors` and `/sources` were checked; the dashboard shows
132 stocks across 11 sectors, while YTD and company-level flow retain their
narrower coverage.

The implementation is in [pull request #3](https://github.com/Daffamohammad/idx-leadership-diffusion/pull/3),
which is open with its checks passing. The deployed site uses the connected
Vercel project, with the production domain assigned to the verified release.

Earlier audit reports and receipts remain dated records under
`final-audit-2026-10-08/`, `final-repair-2026-10-08/`, and
`repair-2026-10-08/`.
