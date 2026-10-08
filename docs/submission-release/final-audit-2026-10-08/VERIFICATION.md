# 0810 repair verification · 8 October 2026

**Local application verification: PASS. Public hosting: blocked.**

Tested source: `d1a223f212e69dce9cf5478f2cd2f67093746597`, containing the fixes
at `555a27a`. The handoff commit changes documentation and evidence only.
The production preview served the audited bundle byte for byte
(`index-CD9hhWfP.js`, SHA-256
`eae8a9149c447e910811fe03a01488a390cb14ace3876a9e9274d749b4ea0bdc`).
Open [the preview](http://localhost:4173/sectors).

## Fresh browser verification

[Browser receipt](browser-qa.json): 23 passing checks, including every one of
the readiness script's 21 required checks. All sixteen navigation routes were
fresh-loaded at 1036×799, 1369×799, 1440×900, and 390×844: **64 successful loads**.
No unexpected console errors, failed application-data requests, or page overflow
were observed. Sixteen screenshots have verified hashes and physical dimensions.

- Dashboard: eleven rankings, eleven map points (nine confirmed and two hollow
  descriptive marks), 21 daily dates, five weekly dates, and all 66 constituents
  inspected. Playback advances dates. Charts show genuine basket, constituent,
  and IHSG values through interactive inspection and comparison controls.
- Coverage & sources: all 66 stock links across both table pages; coverage is
  attributed to The Diffusion. The flow card says IDX Q3 market flow, with
  Sectors API shown separately as the source.
- Landing: working Dashboard preview and footer at all four sizes; no banned
  archival wording. The requested hero animation is preserved.
- Overview: IHSG 6,036.89, previous close 6,009.50, +27.386 points / +0.46%;
  daily history renders. TradingView technical analysis and advanced chart
  render as external context. Its heatmap renders stock cells and switches
  between daily and YTD performance.
- Weekly comparisons: summaries, sector participation and the selected group's
  replay agree. Transportation & Logistic shows 15/30 outperforming, 50.0%
  breadth, −13.3 pp change and Narrowing Firm on 2 October; the breadth curve
  and tooltip render.
- Context maps: 11 sector, 46 Konglo, 99 IDXIC and 15 theme points. Missing
  coordinates remain unplotted, and small groups retain descriptive styling.
  Both catalogue pages expose all 46 groups, including every one of the 34
  reference identifiers checked against the hash-bound catalogue asset.
- Ownership: issuer, investor, group, change and comparison views work.
  The 1% comparison retains 7,158 prior rows. BBRI's Employees Provident Fund
  position shows −47,249,400 shares and −0.03 pp. Unchanged positions can be
  included. The 5% population keeps its 1 October date and marks prior
  percentage comparisons unavailable. All 376 sourced group connections render.

[Supplemental ticker checks](ticker-qa.json) verify that source-table navigation
opens AMMN's raw Sectors history, preserves scope/date/cadence/horizon, and
changes the chart through weekly replay. SAME's broader IDX chart renders its
266 observed adjusted closes and an IHSG comparison with a working tooltip.

## Deliberate failures and recovery

An isolated copy of the current production bundle supplied delayed responses,
HTTP 503, absent analysis, missing selection evidence, corrupt analysis and
corrupt YTD evidence. The review preview and original inputs were untouched.
Loading, absent data and rejected data are distinct. Failed requests display
Retry; recovery restores the figures. Corruption blocks the primary workflow
and the landing preview, whose error text is sanitized. Its Retry also works.
Current points remain within the map domain with no prior history and no trails.

Stopping the isolated server produced `ERR_CONNECTION_REFUSED`; restarting it
and navigating afresh restored eleven rankings and map marks. The browser
allowed the initial error-page observation but blocked a subsequent screenshot
of its generated data URL. No error-page screenshot is claimed. Canvas-based
TradingView heatmap cells were checked visually, as its accessibility tree
describes the legend rather than individual cells.

## Calculations and reproduction

[Fresh readiness](readiness.json) is `VERIFIED_LOCAL_BUILD`, bound to the tested
source, active package and hashed browser receipt. It passes an exact offline
core rebuild, both independent calculation oracles with zero mismatches,
corporate-action exclusions, and 59 focused regressions covering the interfaces,
budget/retries, restart/concurrency and rejection before request 501.
[Four new audit regressions](audit-regressions.txt) were also rerun successfully:
ticker-set persistence, disjoint participation cohorts, the shared leadership
floor, and YTD-independent rotation continuity.

The handoff's [939-test Python run](python-checks.txt),
[frontend typecheck](frontend-typecheck.txt), [production build](frontend-build.txt),
[integer diffusion oracle](diffusion-count-oracle.txt), and
[clean-checkout reproduction](clean-reproduction.json) are retained at fix
commit `555a27a`. No application source changed during this verification.
The existing market-breadth price oracle remains applicable to unchanged inputs.

## Preservation and remaining launch gate

Active package: `rel-64026e36d49733009fec952086fc95a3121a86efbb196b1c68d00fd6317f33d2`.
Manifest SHA-256: `98e2c260c9afae07ce2b1cb5b5436cda8bbff9978a0239d809d909183ad36e4f`.
The new readiness receipt correctly names immediate rollback
`rel-fad218940fcc7e2492d97613681175b6cb2b2e38d387254737fafc0cadfa09dc`
and manifest hash `2defade3acf1688eb96e0e40d577189f390eafd03fea69a1175ce5e07aa1f11c`.
[Preservation check](preservation.json) finds zero changes in 616 protected files,
including the active pointer, prior packages and acquisition/budget evidence.

**Zero paid/provider calls were made. Acquisition remains on HOLD.**
The ledger remains 461 estimated reservations against 500; the reported 221
remaining calls are unused and still require reconciliation before acquisition.

[Source publication](publication.json) confirms an atomic fast-forward of both
`main` and `codex/final-diffusion-repair` to `10e8bd2`, containing the verified
source and fresh evidence. The prior main commit `8c34fed` remains in history
for source rollback. No application code changed after browser verification.

[The fresh Vercel launch attempt](launch.json), made after source publication,
returned HTTP 400: the GitHub integration must be installed before this
repository can be linked. No CLI fallback is installed. The earlier
[read-only check](launch-check.json) and all historical failures are preserved.
Connect repository access, then launch the verified `main` branch and check
fresh public loads. No public URL has been accepted. Videos, social publication
and final submission remain deferred; this receipt does not declare the
submission complete.
