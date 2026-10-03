# VISUAL_QC — browser run completed

Environment: real Chromium-based **Google Chrome** driven by `playwright-core` (temp harness outside the repo, so no dependency was added to `app/web`).
Server: `npm run preview --prefix app/web` on `http://127.0.0.1:4319` (`--port 4319 --strictPort --host 127.0.0.1`).
Bundle: `snap_sectors_2026-08-27`, as of 27 Aug 2026, `complete=false`.
Theme: light **and** dark, at 1440×900 and 390×844 for the contrast pass.

> **Port trap (reproduce correctly):** `4173` is occupied on this machine by an unrelated app (`Pages I Kept for You`). `vite preview` then bound IPv6 only and the first pass silently tested the wrong application. Always confirm with `curl -s http://127.0.0.1:<port>/ | head` before trusting a run. The harness for this round ran on **4319**.

## Result

| Pass | Checks | Result |
| --- | --- | --- |
| Geometry (13 routes × 5 viewports) | 65 | **65 PASS / 0 FAIL** |
| Interaction (navigation, focus, search, filter, detail, rail, offline) | 13 | **12 PASS / 1 INFO / 0 FAIL** |
| Regression matrix | 13 | **13 PASS / 0 FAIL** |
| **WCAG contrast (19 routes × 2 themes × 2 viewports)** | 76 audits | **0 findings** |
| Console + page errors | — | **0** |
| Screenshots | 92 | written to the harness `shots/` directory |

## Geometry — routes

`/overview`, `/map?taxonomy=SECTOR`, `/map?taxonomy=KONGLO&mode=stocks`, `/groups?taxonomy=THEMES&view=heatmap`, `/groups?taxonomy=KONGLO`, `/themes`, `/konglo`, `/explorer?taxonomy=THEMES&group=THEME_COAL_ENERGY`, `/explorer?taxonomy=KONGLO&group=KONGLO_SALIM&compare=KONGLO_ASTRA&period=3M`, `/explorer?taxonomy=SECTOR&group=Energy`, `/explorer?taxonomy=SECTOR&group=Financials&compare=Energy`, `/ticker/AADI.JK`, `/methodology`.

## Geometry — viewports and measured widths

Every route at every viewport: `documentElement.scrollWidth === clientWidth` **and** workspace `scrollWidth === clientWidth`; zero-sized charts = 0. No page-level horizontal overflow, no hidden root overflow used to conceal data.

| Viewport | Routes | doc = ws (sample) | Workspace (sample) |
| --- | --- | --- | --- |
| 1440×900 | 13/13 PASS | `1440/1440` | `1232/1232` |
| 1368×858 | 13/13 PASS | `1368/1368` | `1160/1160` |
| 1291×858 | 13/13 PASS | `1291/1291` | `1083/1083` |
| 768×1024 | 13/13 PASS | `768/768` | tablet reflow, no overflow |
| 390×844 | 13/13 PASS | `390/390` | `390/390`, stacked single column |

## Chart and iframe bounds

| Route | 1440×900 | 1368×858 | 1291×858 | 768×1024 | 390×844 |
| --- | --- | --- | --- | --- | --- |
| `/explorer?…THEME_COAL_ENERGY` | 1114×212 | 1042×212 | 968×212 | 684×212 | fits container |
| `/explorer?…KONGLO_SALIM&compare=KONGLO_ASTRA` | 1114×212 | 1042×212 | 968×212 | 684×212 | fits container |
| `/explorer?taxonomy=SECTOR&group=Energy` | 1114×252 | 1042×252 | 968×252 | 684×252 | fits container |
| `/ticker/AADI.JK` | chart 1106×272, **TradingView iframe 1082×560** | chart 1062×…, iframe 1062×560 | chart 985×…, iframe 985×560 | iframe fits | iframe fits |

All measured bounds are non-zero and `≤ parent`, so the old 8-second timeout (which discarded already-visible charts) would no longer matter — the widget is still mounted **after 9 seconds** and fills its container exactly.

## Navigation / focus / search / filter / detail

| Check | Result | Evidence |
| --- | --- | --- |
| Catalog search | PASS | `filter=coal` → 1 row |
| Catalog URL state | PASS | `http://…/groups?taxonomy=THEMES&filter=coal` |
| Open detail from catalog | PASS | `KONGLO_ASTRA` → `h1 "Astra / Jardine ecosystem"` |
| Comparison selector | PASS | 6 options, 76 metric rows, `compare` written to URL |
| Period tabs disabled with reason | PASS | 5 disabled tabs; reason "Needs at least 180 days of history; this snapshot holds 90 days. Only persisted snapshot prices are used here — Sectors API refreshes are on hold…" |
| Focus restore on close (in-app back link) | PASS | `activeElement <A data-group-id=KONGLO_ASTRA>` |
| Focus restore on **browser Back** after keyboard Enter | PASS | `<A data-group-id=THEME_INFRASTRUCTURE>` |
| Header ticker/company search | PASS | combobox, 8 options for `BB`; Escape closes the list and keeps focus on the input |
| Rail expanded labels | PASS | 11 nav links, 11 visible labels |
| Rail collapsed tooltip | PASS | collapse → hover → tooltip `"Leadership Map"` |
| Rail collapse/expand | PASS | width 60 → 208 |
| Mobile nav | PASS | 11 rail links, 1 menu control at 390×844 |
| Offline data discipline | PASS | 4 XHR/fetch across 13 routes, **all under `/snapshots/` or `/idx/`**; 0 unexpected external hosts (fonts and the TradingView iframe are expected context) |
| Dark theme | INFO | body background `rgb(18, 22, 25)` — real tokens, no global inversion |

## Regression matrix (§7)

| Check | Result |
| --- | --- |
| No `null` / `undefined` / `NaN` / `Infinity` / `[object Object]` / provider-job text in rendered copy across **19** routes | PASS |
| AMMN 61/21 points for the same bundle/ranges (`Points: 61` on ALL, `Points: 21` on 1M) | PASS |
| TradingView mounted beyond the old timeout and fits its container (checked at 9s) | PASS |
| Partial / stale badge + expandable provenance + "Data as of" + no "Today" for old data | PASS |
| Flow 65% gate: `signal eligibility: Review` + all four per-criterion flags (`Market days`, `mapped coverage`, `Company rows`, `Regime diversity`) + Met/Review + coverage % | PASS |
| Top-3 0–100 formatting (`100%` present, no raw `null`) | PASS |
| Local profile persistence: open dialog → Escape closes → focus returns to the trigger | PASS |
| Keyboard detail navigation + focus restoration | PASS |
| **P2-2** sector ticker search — `?taxonomy=SECTOR&filter=BBCA` → 1 row `["Financials"]` | PASS |
| **P2-3** sector period URL — `?period=1M` restores; click 3M → `?period=3M`; click ALL → param removed | PASS |
| **P2-4** rotation diagnostic visibility — 1 checkbox `Toggle Not available`, circles 11 → 0 → 11 | PASS |
| **P2-1** dark header — `headerBg=rgb(26,32,38)`, `whiteHeader=false`, home link 13.94:1, separator 6.48:1 | PASS |
| No page/console errors | PASS |

## WCAG contrast audit — 0 findings

`contrast.js` walks every element with direct text and compares the foreground against the background a reader actually sees:

- SVG text uses `fill` as the foreground and the **smallest containing SVG shape** as the background (an ancestor walk alone reads the frame colour and reports white-on-white).
- `paint-order: stroke` is honoured — a halo's stroke colour becomes the effective background behind the letterforms.
- `background-clip: text` resolves to the **last gradient colour stop**, because the headline sweep ends `animation-fill-mode: forwards` at `background-position: 100%`. (Transient mid-sweep frames are recorded as a known issue in `HANDOFF.md`, not hidden.)
- Large text (≥24px, or ≥18.66px bold) uses the 3.0 threshold; everything else uses 4.5. `disabled` and `aria-disabled` are exempt per WCAG 1.4.3.

| Theme | 1440×900 | 390×844 |
| --- | --- | --- |
| Light | **0** | **0** |
| Dark | **0** | **0** |

Routes audited (19): `/`, `/what-changed`, `/overview`, `/map?taxonomy=SECTOR`, `/map?taxonomy=KONGLO&mode=stocks`, `/maps/konglo`, `/maps/themes`, `/groups?taxonomy=SECTOR`, `/groups?taxonomy=KONGLO`, `/groups?taxonomy=THEMES&view=heatmap`, `/themes`, `/konglo`, `/tickers`, `/chart-demo`, `/explorer?…Energy`, `/explorer?…THEME_COAL_ENERGY`, `/explorer?…KONGLO_SALIM&compare=KONGLO_ASTRA`, `/ticker/AMMN.JK`, `/methodology`.

Trajectory across passes: **4,100 → 272 → 76 → 8 → 0**.

## Reproduction

1. `npm run build --prefix app/web`
2. `npm run preview --prefix app/web -- --port 4319 --strictPort --host 127.0.0.1`
3. Confirm you are on the intended app: `curl -s http://127.0.0.1:4319/ | head -3`
4. Drive the routes/viewports above and record `documentElement.scrollWidth/clientWidth`, workspace widths, chart/iframe bounds, console errors, screenshots.
5. Re-run the interaction and regression checks listed above.
6. Run the contrast pass over all 19 routes in **both** themes at 1440×900 and 390×844; expect `{"total":0,"byTheme":{"light":0,"dark":0},"unique":0}`. Delete any `dark-contrast-*.png` left over from a failing pass — those are stale evidence.

## Caveat

Screenshots and geometry prove layout and interaction state, not a live feed, source licensing, financial correctness, or release readiness. The bundle remains `complete=false` with YTD unavailable, so every chart shown here is a persisted snapshot history.
