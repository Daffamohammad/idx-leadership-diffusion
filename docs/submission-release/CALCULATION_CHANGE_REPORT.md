# Calculation change report

## Activated immutable release

- Observation date: **2 October 2026**.
- Release: `rel-48500fc94300469fed51247a129a900cfbe9c541e2d679f7a55ef558212941e7`.
- Active manifest SHA-256: `2f025087c5973694dfd3141d62bb64049aad5e38096a3ea3e47482af05f01ecf`.
- Staged candidate manifest SHA-256 before publication finalization: `6ae5734661cb1051fba9cfcab897b808ae0059337862a20a7e39252dd684babb`.
- Analysis asset: `historical-comparison-v2`.
- Breadth asset: `market-breadth-v1`.
- No Sectors requests were made for this release.

## Matched historical replay

The release adds daily observations from **4 September through 2 October 2026** and retains weekly endpoints on **4, 11, 18, and 25 September and 2 October**. The label is **Historical price replay using current membership**: the dated membership records are held fixed across the historical price window; they are not historical membership evidence.

The common sector cohort contains **752 stocks**. Every stock in a group calculation must be signal-eligible in the selected release and have adjusted closes for every required price and benchmark endpoint in the replay. Each taxonomy and group records its membership date/version, sorted membership tickers, member count and hash, relationship-evidence hash, sorted common contributors and hash, and source panel hashes. The original strict snapshot-comparability check is unchanged.

For each dated observation, the builder calculates equal-weight stock returns minus the matching IHSG return over 5, 20, and 60 IDX sessions and from the last IHSG close on or before 31 December 2025. Breadth is the count of group constituents whose 20-session excess return is positive; percentage changes are derived from those unrounded counts and the same frozen group denominator. Diffusion v2 retains firm/fragile states and the existing constituent floor. Leadership continues to use the existing 5D-versus-60D acceleration rule. Rotation phase uses YTD excess and 20D-minus-60D excess. Concentration, persistence, weekly transitions and materiality use these same observations.

The daily replay contains **21 observations**. The sector basket chart contains **66 Q3 sessions**, uses the same fixed sector cohorts, and is rebased alongside IHSG at the first Q3 session. Current market-wide readings remain separate from the retrospective matched-cohort analysis.

The replay now covers:

- 11 IDX sectors;
- 22 dated Konglo portfolios;
- 102 IDXIC activities; and
- 15 separate curated themes.

The 22 existing portfolios were not inflated with candidate memberships lacking verified primary evidence. Nineteen have fewer than five common replay contributors; they remain in the catalog and inspector, while signal classifications respect the existing five-constituent floor.

## Official market breadth

For 2 October, the official workbook reports 332 advancing, 140 unchanged and 357 declining traded stocks: **−25 net advances**, an A/D ratio of **0.93**, and **48.2%** advancing among moving stocks. Directional traded-value shares are 64.0% advancing, 4.8% unchanged and 31.2% declining, using the **Rp11.414T** sum of comparable Stock Summary rows as the denominator. Searchable ticker links expose each directional constituent.

The same workbook provides Rp11.414T Stock Summary value, 115.507B shares, 1.155B lots and 1,613,856 trades across 829 rows. A separately labeled official IDX Daily Statistics series reports Rp12.250T across regular, cash and negotiated markets, with whole-billion precision. Its preceding 20-session average is Rp14.18445T, making 2 October **0.86×** that average. Those figures retain their different scopes.

Official foreign-flow context reports −Rp1.27293T on 2 October, eleven consecutive selling sessions, and Rp718.6285B mean absolute net flow over the preceding 20 sessions. The foreign flow is displayed with its all-markets source scope.

New highs/lows require a strict break of the previous adjusted-close range. The 5D counts are 86 highs and 182 lows among 829 eligible traded stocks; 20D counts are 29 and 149 among 829; 60D counts are 26 and 77 among 827. Each list is searchable and links to stock detail.

The fixed historical net-advances chart uses **751** release-eligible stocks with complete observations over the available validated panel: **15 December 2025–2 October 2026**, 188 benchmark sessions. Nine otherwise signal-eligible stocks lack a complete panel history and are excluded from that cohort.

## Coverage boundary

The requested public price vintage from 1 September 2025 was not available in the local cache. A public history request could not resolve Yahoo Finance's DNS host, so no new historical rows were acquired. The validated panel starts on 15 December 2025. The release therefore omits the 52-calendar-week high/low horizon and states this coverage limit in the interface; it does not extrapolate older prices. Five-, 20-, and 60-session calculations use only complete observed histories.

## Verification

- Offline candidate builder and five-family manifest validator: pass.
- Breadth boundary regressions: **4 passed**, covering direction/value reconciliation, zero denominators, strict high/low ties and incomplete histories.
- Complete Python suite: **880 passed**, with two existing Sectors-provider deprecation warnings.
- Frontend typecheck and production build: pass. The build retains the existing Vite configuration and bundle-size advisories.
