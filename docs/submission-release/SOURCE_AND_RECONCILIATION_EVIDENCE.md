# Source and reconciliation evidence

## Offline release

- Target observation: 2 October 2026.
- Historical price replay: fixed current membership, common cohort and ordered comparison dates recorded in `historical_comparison.json`.
- Cohort hash and count, membership date, replay basis, weekly group measures, persistence, material-shift fields, and Q3 sector baskets are bound as one additional file in the release manifest.
- Official IDX Stock Summary is the source for daily close, change, value (IDR), volume (shares), frequency (trades), and foreign net buy/sell (shares). Ranking filters same-session traded observations and uses ticker as the final tie-break.
- The 102 subindustry names and memberships are the captured IDXIC hierarchy. The 22 Konglo groups are based on dated ownership or disclosure records. Evidence type and capture date remain distinct.
- Official IDX foreign flow remains the source used by the submission's default foreign-flow chart. The displayed period, daily source files, hashes, and session checks are carried in the foreign family.

## Sectors recording

The acquisition plan pins six names for each of 11 sectors by the selected release's captured market capitalization and ticker order. It records four bounded price windows, four native IHSG windows, recent stock flow, four YTD market-flow windows, corporate-action responses, and suspension pages. Every actual attempt is durably reserved before transport and remains under 450 requests and 450 estimated credits. The API key is read from the local environment only.

The Sectors `/v2/foreign-flow/IHSG/` series and official IDX series remain distinct. The Sectors endpoint returned 174 of 178 native IHSG sessions through 2 October. A targeted follow-up confirmed the four omitted dates remain absent: 27 March, 1 April, 15 April, and 22 April 2026. Those dates remain explicit in the acquisition record; no values are imputed. The partial Sectors sum is not compared with official full-period YTD.

The Sectors Q3 series from 1 July through 30 September covers all 64 native IHSG sessions. The official IDX Q3 daily sum is **−IDR 7.43236T**; the Sectors sum is **−IDR 20.0879538006T**; their retained difference is **−IDR 12.6555938006T**. Both date sets match exactly, while the source totals do not. Official IDX YTD remains **−IDR 82.55351T** through 2 October and is the default public foreign-flow view. Sectors returned 174 YTD observations whose known-value sum is −IDR 105.263560352T; because the four dates are unresolved, that sum is not compared with official full-period YTD and is disclosed only inside the recorded sample's Sources panel.

The recording receipt contains the pinned plan hash, request/credit reservation totals, raw-response hashes, validation state, and resume identity. A failed or over-budget acquisition leaves the active release pointer unchanged.

## Official provider documentation

- [Sectors daily transaction data](https://docs.sectors.app/api-references/v2/indonesia/transaction/daily) documents close/volume/market-cap observations, a maximum 90-calendar-day range, and one credit per request.
- [Sectors daily net foreign inflow](https://docs.sectors.app/api-references/v2/indonesia/brokers/foreign-flow-by-symbol) documents the `IHSG` market-wide option, daily net flow in IDR, up to 90 days per request, and one credit per request.

The recording uses the frozen 2 October 2026 session and 66 stocks (six per sector). Four daily-price windows, four IHSG price windows, 66 recent stock-flow histories, four market-flow windows, the targeted YTD date check, corporate-action checks, and suspension pagination are retained by response hash. The completed run reserved 433 requests and 433 estimated credits under its persistent 450 ceilings. Failed attempts remain in the same run ledger; the API key does not enter the response archive.

## Daily market breadth and activity

The release's 2 October daily breadth and per-stock traded values come from the Official IDX Stock Summary workbook. Its 829 traded rows reconcile to 332 advancing, 140 unchanged, and 357 declining; the categories sum to −25 net advances. The value-share denominator is Rp11.4141238555T across rows with comparable closes and reported values. The directional member ticker lists are carried in the manifest-bound `market_breadth` asset.

The workbook also sums to 115.507189B shares, 1.15507189B lots, Rp11.4141238555T value and 1,613,856 trades. The separate official IDX Daily Statistics PDFs cover total regular, cash and negotiated trading and publish rounded values. The matched 21-session PDF sequence from 4 September through 2 October yields Rp12.250T on the selected day and Rp14.18445T mean turnover over the preceding 20 sessions. These denominators are not interchangeable.

The daily foreign context is taken from the selected release's official IDX series: −Rp1.27293T on 2 October, an eleven-session selling streak, and Rp718.6285B mean absolute net over the preceding 20 observed sessions. The adjacent label retains the official all-markets scope.

The validated adjusted-close panel starts on 15 December 2025. It supports the 5D, 20D and 60D strict-break high/low lists and a 751-name complete-history net-advances cohort through 2 October (188 IHSG sessions). It cannot support the requested 52-calendar-week range from 1 September 2025. A public Yahoo history request failed at DNS resolution; no substitute or interpolated observations were inserted. The interface exposes the horizon limitation and omits the unavailable 52-week tab.

The historical-analysis and breadth assets include hashes for their market, ownership, rotation, membership, price and benchmark inputs. The 2 October active market-wide readings remain separate from the current-membership historical replay.
